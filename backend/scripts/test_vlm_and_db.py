"""
Test script for Week 9 (Multimodal VLM Integration) and Week 10 (SQLite Database & WebSocket).

Validates:
1. SQLite Incident Database (CRUD, snapshots, filtering, statistics, resolution)
2. Gemini 1.5 Flash VLM client (async execution, JSON explanation parsing, graceful deterministic fallback)
3. FastAPI REST endpoints (/api/incidents, /api/incidents/stats/summary, /snapshots/)
4. WebSocket ConnectionManager (frame and telemetry serialization)
"""
import asyncio
import os
import sys
import time
import numpy as np
import cv2


from fastapi.testclient import TestClient

# Ensure workspace root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.db.database import get_incident_db
from backend.app.db.models import SafetyIncidentRecord
from backend.app.vlm.gemini_client import get_vlm_client, VLMIncidentExplanation
from backend.app.api.websocket import get_connection_manager
from backend.app.main import app


def test_sqlite_incident_database():
    print("\n--- 1. Testing SQLite Incident Database & Snapshots ---")
    db = get_incident_db()

    # Generate test image
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(test_frame, "TEST INCIDENT FRAME", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

    # Save snapshot
    snapshot_path = db.save_snapshot(test_frame, incident_prefix="test_fall")
    assert os.path.exists(snapshot_path), f"Snapshot file not created at {snapshot_path}"
    print(f"✓ Snapshot successfully saved: {snapshot_path}")

    # Insert incident
    record = SafetyIncidentRecord(
        timestamp=time.time(),
        event_type="FALL",
        track_id=1,
        risk_score=92.5,
        risk_level="CRITICAL",
        activity="falling",
        snapshot_path=snapshot_path,
        contributing_factors=["Worker fell backwards near boundary", "Ground contact detected"],
        resolved=False,
    )
    incident_id = db.insert_incident(record)
    assert incident_id > 0, "Failed to insert incident into DB"
    print(f"✓ Incident record #{incident_id} inserted into SQLite.")

    # Retrieve incident
    fetched = db.get_incident(incident_id)
    assert fetched is not None, "Failed to fetch inserted incident"
    assert fetched.event_type == "FALL"
    assert fetched.risk_score == 92.5
    assert fetched.risk_level == "CRITICAL"
    print(f"✓ Incident record #{incident_id} retrieved with correct attributes.")

    # Filter incidents
    criticals = db.list_incidents(risk_level="CRITICAL", resolved=False)
    assert any(r.id == incident_id for r in criticals), "Incident filter by CRITICAL failed"
    print(f"✓ Filtered query verified: {len(criticals)} active CRITICAL incidents found.")

    # Update with VLM explanation
    dummy_vlm = VLMIncidentExplanation(
        incident_id=incident_id,
        summary="Worker observed fallen on floor with no immediate movement.",
        verified=True,
        incident_type="FALL",
        confidence=0.96,
        recommended_action="Dispatch immediate site medical assistance.",
    )
    db.update_vlm_explanation(incident_id, dummy_vlm)
    updated = db.get_incident(incident_id)
    assert updated.vlm_verified is True
    assert updated.vlm_summary == "Worker observed fallen on floor with no immediate movement."
    assert "Dispatch immediate site medical assistance" in updated.recommended_action
    print(f"✓ Incident #{incident_id} updated with VLM verification metadata.")


    # Mark resolved
    resolved_ok = db.resolve_incident(incident_id)
    assert resolved_ok is True
    resolved_rec = db.get_incident(incident_id)
    assert resolved_rec.resolved is True
    print(f"✓ Incident #{incident_id} marked resolved.")

    # Verify statistics
    stats = db.get_statistics()
    assert stats["total_incidents"] >= 1
    assert stats["resolved_incidents"] >= 1
    print(f"✓ DB Statistics verified: Total={stats['total_incidents']}, Critical={stats['by_severity'].get('CRITICAL', 0)}")


async def test_vlm_client():
    print("\n--- 2. Testing Multimodal VLM (Gemini 1.5 Flash + Fallback) ---")
    vlm_client = get_vlm_client()

    # Generate synthetic image for test
    test_frame = np.full((360, 640, 3), 50, dtype=np.uint8)
    cv2.circle(test_frame, (320, 180), 60, (0, 0, 255), -1)
    cv2.putText(test_frame, "ZONE BREACH", (220, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Test async verification
    explanation = await vlm_client.verify_incident_async(
        image_bgr=test_frame,
        event_type="ZONE_INTRUSION",
        track_id=3,
        risk_score=75.0,
        telemetry_context={
            "zone_name": "High-Voltage Transformer Bay",
            "speed": "1.4 m/s",
            "ppe": {"helmet": True, "vest": False},
        },
    )

    assert explanation is not None
    assert isinstance(explanation.summary, str) and len(explanation.summary) > 0
    assert explanation.confidence > 0.0
    assert len(explanation.recommendations) > 0
    print(f"✓ VLM Result:")
    print(f"   - Verified:       {explanation.verified}")
    print(f"   - Incident Type:  {explanation.incident_type}")
    print(f"   - Confidence:     {explanation.confidence:.2f}")
    print(f"   - Summary:        {explanation.summary}")
    print(f"   - Hazard Assess:  {explanation.hazard_assessment}")
    print(f"   - Recommended:    {explanation.recommended_action}")


def test_fastapi_endpoints():
    print("\n--- 3. Testing FastAPI REST Endpoints & Snapshots Serving ---")
    client = TestClient(app)

    # 1. Health check
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    print("✓ GET /api/health passed.")

    # 2. List incidents
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    incidents_list = resp.json()
    assert isinstance(incidents_list, list)
    print(f"✓ GET /api/incidents passed ({len(incidents_list)} records returned).")

    # 3. Incident stats
    resp = client.get("/api/incidents/stats/summary")
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_incidents" in stats
    print(f"✓ GET /api/incidents/stats/summary passed: {stats}")

    # 4. Pipeline status
    resp = client.get("/api/pipeline/status")
    assert resp.status_code == 200
    p_status = resp.json()
    assert "running" in p_status
    print(f"✓ GET /api/pipeline/status passed: {p_status}")

    # 5. Snapshots static serving
    if incidents_list and incidents_list[0].get("snapshot_path"):
        snap_path = incidents_list[0]["snapshot_path"]
        filename = os.path.basename(snap_path)
        resp = client.get(f"/snapshots/{filename}")
        assert resp.status_code == 200, f"Failed to retrieve snapshot image: {resp.status_code}"
        assert resp.headers["content-type"].startswith("image/")
        print(f"✓ GET /snapshots/{filename} verified static image serving.")



def test_websocket_manager():
    print("\n--- 4. Testing WebSocket Connection Manager Telemetry Encoding ---")
    ws_mgr = get_connection_manager()

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", frame)

    telemetry = {
        "timestamp": "2026-10-12T01:00:00Z",
        "fps": 12.0,
        "scene_risk": {"score": 25.0, "tier": "LOW"},
    }

    # Verify async broadcast without active clients handles gracefully
    asyncio.run(ws_mgr.broadcast_frame_and_telemetry(encoded.tobytes(), telemetry))
    print("✓ WebSocket broadcast_frame_and_telemetry executed cleanly.")


if __name__ == "__main__":
    print("============================================================")
    print("Week 9 & 10 Verification: VLM, SQLite DB & WebSocket Stream")
    print("============================================================")

    test_sqlite_incident_database()
    asyncio.run(test_vlm_client())
    test_fastapi_endpoints()
    test_websocket_manager()

    print("\n============================================================")
    print("ALL WEEK 9 & WEEK 10 TESTS PASSED SUCCESSFULLY!")
    print("============================================================")
