"""
Multimodal Vision-Language Model (VLM) Integration (SRS §8.5, FR-16..FR-20, Week 9).

Integrates Google Gemini 1.5 Flash API for asynchronous incident verification,
natural-language situation summaries, and operator action recommendations.

Design Decisions (SRS §8.5 & NFR-02):
  1. Asynchronous & Non-Blocking: VLM queries execute in background tasks,
     never interrupting or throttling the 10-15 FPS real-time local CV pipeline.
  2. Structured Prompting: Keyframe image + structured telemetry (Worker ID,
     Rule violated, Risk score, Activity, PPE status) sent as multimodal input.
  3. Graceful Degradation (FR-20): If GEMINI_API_KEY is not configured or network
     calls fail, generates high-quality deterministic fallback audit summaries.
  4. Rate Limiting: Minimum interval between requests (default 8s) to respect quotas.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("safety-ai-mvp.vlm")


@dataclass
class VLMIncidentExplanation:
    """Structured VLM audit response for an incident."""
    summary: str
    risk_level: str = "HIGH"
    recommended_action: str = ""
    confidence: float = 0.90
    verified: bool = True
    incident_type: str = ""
    incident_id: Optional[int] = None
    hazard_assessment: str = ""
    raw_response: str = ""
    timestamp: float = field(default_factory=time.time)
    model_used: str = "gemini-1.5-flash"
    recommendations_list: list[str] = field(default_factory=list)

    @property
    def recommendations(self) -> list[str]:
        if self.recommendations_list:
            return self.recommendations_list
        return [self.recommended_action] if self.recommended_action else []

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type,
            "summary": self.summary,
            "risk_level": self.risk_level,
            "recommended_action": self.recommended_action,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "verified": self.verified,
            "hazard_assessment": self.hazard_assessment,
            "timestamp": self.timestamp,
            "model_used": self.model_used,
        }


class GeminiVLMClient:
    """Asynchronous Gemini 1.5 Flash client with rate-limiting and graceful fallback."""

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-1.5-flash",
        enabled: bool = True,
        rate_limit_seconds: float = 8.0,
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.enabled = enabled and bool(self.api_key)
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds

        self._last_call_timestamp: float = 0.0
        self.is_ready = bool(self.api_key)

        # Check if google.generativeai SDK is available
        self._sdk_available = False
        if self.is_ready:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai = genai
                self._model = genai.GenerativeModel(self.model_name)
                self._sdk_available = True
                logger.info(f"Gemini VLM initialized with SDK ({self.model_name})")
            except Exception as e:
                logger.info(f"Using direct REST endpoint for Gemini VLM ({e})")

        if not self.is_ready:
            logger.info("Gemini VLM running in Degraded/Fallback mode (no API key).")

    def can_query(self) -> bool:
        """Returns True if rate limiter permits an API call."""
        if not self.is_ready:
            return False
        return (time.time() - self._last_call_timestamp) >= self.rate_limit_seconds

    def _generate_fallback_explanation(
        self,
        event_metadata: dict[str, Any],
    ) -> VLMIncidentExplanation:
        """Deterministic, rule-based fallback summary when VLM is offline or rate-limited."""
        event_type = event_metadata.get("event_type", "SAFETY_VIOLATION").upper()
        track_id = event_metadata.get("track_id", "Unknown")
        risk_level = event_metadata.get("risk_level", "MEDIUM")
        risk_score = event_metadata.get("risk_score", 50.0)
        activity = event_metadata.get("activity", "active")
        factors = event_metadata.get("contributing_factors", [])

        # Formulate contextual action recommendations
        if "FALL" in event_type:
            summary = f"FALL INCIDENT: Worker #{track_id} collapsed to horizontal posture."
            action = "Dispatch immediate medical emergency response. Check worker consciousness and vital signs."
            hazard = "Sudden loss of vertical posture, possible slip, trip, medical event, or impact."
        elif "CLIMB" in event_type:
            summary = f"DANGEROUS CLIMB: Worker #{track_id} climbing without safety helmet."
            action = "Order immediate halt to climbing activity. Require safety helmet and fall arrest harness before resuming."
            hazard = "Elevated working height with unprotected head and potential fall hazard."
        elif "ZONE" in event_type or "RESTRICTED" in event_type:
            summary = f"RESTRICTED ZONE INTRUSION: Worker #{track_id} entered designated hazard zone."
            action = "Instruct worker to evacuate restricted perimeter immediately. Verify safety clearance credentials."
            hazard = "Unauthorized presence in designated dangerous machinery or electrical zone."
        elif "HELMET" in event_type:
            summary = f"PPE NON-COMPLIANCE: Worker #{track_id} missing safety helmet while {activity}."
            action = "Issue verbal warning and provide approved hard hat before continuing active work."
            hazard = "Vulnerability to falling objects and head trauma in active workplace."
        elif "VEST" in event_type:
            summary = f"PPE NON-COMPLIANCE: Worker #{track_id} missing high-visibility vest while {activity}."
            action = "Ensure worker dons reflective safety vest to maintain operational visibility."
            hazard = "Low visibility to vehicle operators and industrial machinery."
        else:
            summary = f"SAFETY ALERT: Worker #{track_id} triggered {event_type} (Risk: {risk_score:.0f})."
            action = "Supervisory review required. Correct non-compliant condition."
            hazard = ", ".join(factors) if factors else "Operational safety policy violation."

        return VLMIncidentExplanation(
            summary=summary,
            risk_level=risk_level,
            recommended_action=action,
            confidence=0.85,
            verified=True,
            hazard_assessment=hazard,
            raw_response="[LOCAL DETERMINISTIC AUDIT ENGINE - DEGRADED MODE]",
            model_used="local-deterministic-fallback",
        )

    async def explain_incident(
        self,
        frame_jpeg_bytes: bytes,
        event_metadata: dict[str, Any],
    ) -> VLMIncidentExplanation:
        """Asynchronously audits safety incident with Gemini 1.5 Flash.

        If VLM is disabled, rate-limited, or API fails, returns deterministic fallback.
        """
        if not self.is_ready or not self.can_query():
            return self._generate_fallback_explanation(event_metadata)

        # Update rate limit timer
        self._last_call_timestamp = time.time()

        # Build prompt
        prompt = (
            "You are an expert industrial and construction safety audit AI. "
            "Analyze the attached surveillance image and event telemetry:\n\n"
            f"- Event Type: {event_metadata.get('event_type')}\n"
            f"- Worker ID: #{event_metadata.get('track_id')}\n"
            f"- Assessed Risk Level: {event_metadata.get('risk_level')} ({event_metadata.get('risk_score', 0):.0f}/100)\n"
            f"- Activity: {event_metadata.get('activity')}\n"
            f"- Contributing Factors: {event_metadata.get('contributing_factors', [])}\n\n"
            "Respond ONLY with a valid JSON object in this exact schema:\n"
            "{\n"
            '  "verified": true or false,\n'
            '  "summary": "1-2 sentence description of what is happening in the scene",\n'
            '  "hazard_assessment": "Specific physical hazards visible in the environment",\n'
            '  "recommended_action": "Immediate corrective safety procedure for supervisors",\n'
            '  "confidence": float between 0.0 and 1.0\n'
            "}"
        )

        try:
            # Run in thread pool to avoid blocking async event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._call_gemini_api_sync, frame_jpeg_bytes, prompt
            )
            if result:
                return result
        except Exception as e:
            logger.warning(f"Gemini API request failed: {e}. Falling back to deterministic audit.")

        return self._generate_fallback_explanation(event_metadata)

    def _call_gemini_api_sync(
        self,
        frame_jpeg_bytes: bytes,
        prompt: str,
    ) -> Optional[VLMIncidentExplanation]:
        """Synchronous network call to Gemini 1.5 Flash."""
        # Method A: Use google.generativeai SDK if available
        if self._sdk_available:
            try:
                import PIL.Image
                import io

                image = PIL.Image.open(io.BytesIO(frame_jpeg_bytes))
                response = self._model.generate_content([prompt, image])
                text = response.text.strip()
                return self._parse_gemini_json_response(text)
            except Exception as e:
                logger.debug(f"SDK call error: {e}, attempting direct REST call...")

        # Method B: Direct REST API via urllib (zero external dependency)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        b64_image = base64.b64encode(frame_jpeg_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0]["content"]["parts"][0]["text"].strip()
                return self._parse_gemini_json_response(text)

        return None

    def _parse_gemini_json_response(self, text: str) -> Optional[VLMIncidentExplanation]:
        """Parses JSON response from Gemini output."""
        try:
            # Clean markdown codeblocks if present
            cleaned = text
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())

            return VLMIncidentExplanation(
                summary=parsed.get("summary", "Incident observed."),
                risk_level="HIGH" if parsed.get("verified", True) else "LOW",
                recommended_action=parsed.get("recommended_action", "Supervisory check required."),
                confidence=float(parsed.get("confidence", 0.90)),
                verified=bool(parsed.get("verified", True)),
                hazard_assessment=parsed.get("hazard_assessment", ""),
                raw_response=text,
                model_used=self.model_name,
            )
        except Exception as e:
            logger.debug(f"Could not parse Gemini JSON response: {e}")
            return VLMIncidentExplanation(
                summary=text[:200],
                risk_level="MEDIUM",
                recommended_action="Review camera footage.",
                confidence=0.75,
                verified=True,
                raw_response=text,
                model_used=self.model_name,
            )

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "is_ready": self.is_ready,
            "model_name": self.model_name,
            "sdk_available": self._sdk_available,
            "rate_limit_seconds": self.rate_limit_seconds,
            "seconds_since_last_call": round(time.time() - self._last_call_timestamp, 1) if self._last_call_timestamp > 0 else None,
        }

    async def verify_incident_async(
        self,
        image_bgr: Any = None,
        event_type: str = "SAFETY_ALERT",
        track_id: int = 0,
        risk_score: float = 50.0,
        telemetry_context: Optional[dict[str, Any]] = None,
        frame_jpeg_bytes: Optional[bytes] = None,
    ) -> VLMIncidentExplanation:
        """High-level async verification method accepting BGR frames or pre-encoded JPEG bytes."""
        if frame_jpeg_bytes is None and image_bgr is not None:
            import cv2
            success, enc = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if success:
                frame_jpeg_bytes = enc.tobytes()
            else:
                frame_jpeg_bytes = b""
        elif frame_jpeg_bytes is None:
            frame_jpeg_bytes = b""

        ctx = telemetry_context or {}
        risk_level = "CRITICAL" if risk_score >= 80 else "HIGH" if risk_score >= 60 else "MEDIUM"
        event_meta = {
            "event_type": event_type,
            "track_id": track_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "activity": ctx.get("activity", "active"),
            "contributing_factors": ctx.get("contributing_factors", [event_type]),
        }

        explanation = await self.explain_incident(frame_jpeg_bytes, event_meta)
        explanation.incident_type = event_type
        if "recommendations" in ctx and isinstance(ctx["recommendations"], list):
            explanation.recommendations_list = ctx["recommendations"]
        return explanation


_vlm_client_instance: Optional[GeminiVLMClient] = None


def get_vlm_client() -> GeminiVLMClient:
    """Returns singleton Gemini VLM client instance initialized from settings."""
    global _vlm_client_instance
    if _vlm_client_instance is None:
        try:
            from backend.app.core.config import get_settings
            settings = get_settings()
            _vlm_client_instance = GeminiVLMClient(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL,
                enabled=settings.VLM_ENABLED,
                rate_limit_seconds=float(settings.VLM_RATE_LIMIT_SECONDS),
            )
        except Exception:
            _vlm_client_instance = GeminiVLMClient()
    return _vlm_client_instance

