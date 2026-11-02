"""Profile end-to-end pipeline throughput through the running FastAPI service."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(url: str, method: str = "GET") -> dict:
    request = Request(url, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Request to {url} failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8010", help="FastAPI base URL")
    parser.add_argument("--source", help="Video path, webcam index, or RTSP URL; defaults to backend VIDEO_SOURCE")
    parser.add_argument("--seconds", type=int, default=60, help="Profile duration (10–3600 seconds)")
    args = parser.parse_args()
    if not 10 <= args.seconds <= 3600:
        parser.error("--seconds must be between 10 and 3600")

    base = args.api.rstrip("/")
    status_url = f"{base}/api/pipeline/status"
    before = request_json(status_url)
    if before.get("running"):
        raise RuntimeError("Pipeline is already running; stop it before profiling to avoid interrupting a session.")

    query = f"?{urlencode({'source': args.source})}" if args.source else ""
    started = False
    try:
        request_json(f"{base}/api/pipeline/start{query}", method="POST")
        started = True
        print(f"Profiling for {args.seconds}s; source={args.source or 'backend VIDEO_SOURCE'}")
        samples: list[tuple[float, int, float]] = []
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            sample = request_json(status_url)
            samples.append((time.monotonic(), int(sample.get("frame_count", 0)), float(sample.get("fps", 0))))
            if not sample.get("running"):
                raise RuntimeError("Pipeline stopped before the profiling window ended; check backend logs and video source.")
            time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))

        if len(samples) < 2:
            raise RuntimeError("Not enough pipeline status samples were collected.")
        elapsed = samples[-1][0] - samples[0][0]
        processed = max(0, samples[-1][1] - samples[0][1])
        measured_fps = processed / elapsed if elapsed > 0 else 0.0
        backend_fps = [fps for _, _, fps in samples if fps > 0]
        print("\nPipeline profile")
        print(f"  Source:             {args.source or before.get('video_source', 'configured source')}")
        print(f"  Window:             {elapsed:.1f}s")
        print(f"  Frames processed:   {processed}")
        print(f"  Measured throughput:{measured_fps:7.2f} FPS")
        if backend_fps:
            print(f"  Backend FPS median: {statistics.median(backend_fps):.2f}")
            print(f"  Backend FPS min/max:{min(backend_fps):.2f} / {max(backend_fps):.2f}")
        print("  Note: webcam and video-file runs have different source pacing; compare the same source and hardware.")
        return 0
    finally:
        if started:
            request_json(f"{base}/api/pipeline/stop", method="POST")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
