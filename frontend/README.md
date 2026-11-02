# Frontend Dashboard (Week 11 Deliverable)

Real-time browser-based dashboard built with **React + Vite + Tailwind CSS**.

## Planned Features (SRS §8.7, FR-21):
- **Live Video Feed:** Real-time canvas/MJPEG or WebSocket video stream displaying overlays:
  - Tracked person bounding boxes + Track ID
  - Pose skeleton visualization
  - Activity label + confidence
  - PPE status (helmet/vest badges)
  - Active restricted zone boundary polygons
- **Live Safety Event Feed:** Chronological ticker of detected hazards (Falls, Missing PPE, Intrusion).
- **Incident Inspector Modal:** Detailed view of flagged events including keyframe snapshots and Gemini 1.5 Flash VLM explanations.
- **Site Risk Level Gauge:** Real-time site risk score (0–100) with color indicators (LOW, MEDIUM, HIGH, CRITICAL).
- **Zone Editor:** Interactive canvas tool to define or adjust restricted zone coordinates.

## Dev Setup (Upcoming):
```bash
cd frontend
npm install
npm run dev
```
Proxy configured to connect to `http://localhost:8000` (FastAPI backend).
