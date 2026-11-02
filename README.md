# Multimodal Vision-Language Safety Monitoring System — MVP

A real-time, edge-first AI safety monitoring system designed for industrial and construction environments. Combines local real-time computer vision (person tracking, pose estimation, temporal activity recognition, PPE verification, safety rule evaluation) with an asynchronous Vision-Language Model (Gemini 1.5 Flash) for intelligent incident audit and alerting.

> **Target Hardware (SRS §13):** Lenovo LOQ Gen 12-class (NVIDIA RTX 3050 6GB VRAM, 16 GB RAM, Windows 11 / WSL2).  
> **Key Architecture Decision:** See [`DECISIONS.md`](file:///c:/Users/athar/Downloads/Development%20of%20a%20Multimodal%20Vision-Language/DECISIONS.md) for full technology selection rationale, dataset analysis, and the SRS §17 Risk Register.

---

## 1. Project Directory Blueprint

The project follows a modular, industry-standard decoupled architecture:

```
Development of a Multimodal Vision-Language/
├── configs/
│   └── config.yaml                     # Externalized pipeline thresholds, models, and zone configs
├── backend/
│   ├── app/                            # Application & service layer
│   │   ├── main.py                     # FastAPI server entrypoint (CORS, router mounting, lifespan)
│   │   ├── core/
│   │   │   ├── config.py               # Pydantic BaseSettings (reads .env & overrides)
│   │   │   └── env_check.py            # Hardware/GPU/CUDA/FFmpeg diagnostic tool
│   │   ├── api/
│   │   │   ├── websocket.py            # Low-latency streaming connection manager & endpoint
│   │   │   └── routes/
│   │   │       └── health.py           # GET /api/health watchdog and component status
│   │   ├── ml/
│   │   │   └── har_model.py            # PyTorch Small Temporal Transformer architecture definition
│   │   ├── vlm/
│   │   │   └── gemini_client.py        # Asynchronous Gemini 1.5 Flash client with fallback
│   │   └── db/
│   │       └── models.py               # Incident record schema (SQLite / PostgreSQL)
│   ├── pipeline/                       # Modular computer vision & inference pipeline
│   │   ├── ingestion.py                # OpenCV/FFmpeg stream ingestion with frame skipping
│   │   ├── detector.py                 # YOLO11n person detector + ByteTrack association
│   │   ├── pose.py                     # MediaPipe BlazePose estimation on per-person crops
│   │   ├── features.py                 # 205-dim feature extraction & 32-frame deque buffer
│   │   ├── har.py                      # Temporal Transformer inference wrapper (activity classifier)
│   │   ├── ppe.py                      # Custom YOLO11n PPE detector (helmet, vest)
│   │   ├── safety_engine.py            # Rule engine (fall, missing PPE, zone intrusion)
│   │   └── risk_engine.py              # Composite deterministic risk scoring (0-100)
│   ├── scripts/                        # Automated & manual exit-criteria verification scripts
│   │   ├── test_video_source.py        # Week 1: Video source ingestion & FPS benchmark
│   │   ├── test_tracking.py            # Week 2: YOLO11n + ByteTrack person tracking benchmark
│   │   ├── test_pose.py                # Week 3: Pose landmark extraction & buffer verification
│   │   └── test_activity_recognition.py# Week 4: End-to-end HAR inference test
│   └── tests/                          # Automated pytest suite (Week 12 deliverable)
├── frontend/                           # React + Vite + Tailwind CSS Web Dashboard (Week 11)
├── notebooks/                          # Jupyter Notebooks for all model training (Strict Rule)
│   ├── 04_har_training.ipynb           # Week 4: HAR dataset prep, training & evaluation
│   └── 05_ppe_training.ipynb           # Week 5: PPE dataset prep, YOLO11n fine-tuning & eval
├── data/                               # Dataset storage (Gitignored)
│   ├── raw/<class>/                    # Raw input MP4/AVI clips for HAR & PPE
│   ├── features/<class>/               # Pre-extracted (32, 205) feature tensors
│   └── ppe/                            # YOLO-formatted images and annotation labels
├── source/                             # Uploaded .mp4 videos for testing (climbing, CCTV, etc.)
├── models/                             # Saved model checkpoints and manifests (Gitignored)
├── .env.example                        # Environment variable blueprint
├── requirements.txt                    # Python package dependencies
├── DECISIONS.md                        # Architecture, dataset, and risk documentation
└── README.md                           # This startup guide
```

---

## 2. Setup & Installation

### Windows 11 (PowerShell)
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install standard dependencies
pip install -r requirements.txt

# 3. Install CUDA-enabled PyTorch (for RTX 3050 - CUDA 12.1 build)
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 4. Install FFmpeg (system dependency for OpenCV video decoding)
winget install --id=Gyan.FFmpeg -e
```

### WSL2 / Ubuntu
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cu121
sudo apt update && sudo apt install -y ffmpeg
```

### Configuration (.env)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
- For live webcam testing: set `VIDEO_SOURCE=0`
- For recorded video file testing: set `VIDEO_SOURCE=data/sample.mp4`

---

## 3. Quickstart & Verification

### Step 1: Run Environment Diagnostic
```bash
python -m backend.app.core.env_check
```
Verifies Python, OpenCV, FFmpeg on PATH, and CUDA GPU availability on your RTX 3050.

### Step 2: Start the FastAPI Backend
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8010
```
- Open health endpoint: [http://localhost:8010/api/health](http://localhost:8010/api/health)
- API docs: [http://localhost:8010/docs](http://localhost:8010/docs)

---

## 4. Pipeline Component Testing

### Week 1 — Video Ingestion & Throughput Test
```bash
python backend/scripts/test_video_source.py
# Headless mode:
python backend/scripts/test_video_source.py --no-display --seconds 15
```
Measures source ingestion FPS, checks frame skip ratio, and logs dropped frames.

### Week 2 — Person Detection & Tracking (YOLO11n + ByteTrack)
```bash
python backend/scripts/test_tracking.py
```
- First run automatically downloads `yolo11n.pt` off-the-shelf COCO weights.
- Displays bounding box overlays with persistent ByteTrack IDs.
- Separately prints `ingestion_fps` and `inference_fps` (target: 10–15 FPS).

### Week 3 — Pose Landmark Extraction & Feature Buffering (MediaPipe Pose)
```bash
python backend/scripts/test_pose.py
# Or verify and dump a completed (32, 205) feature vector:
python backend/scripts/test_pose.py --save-buffer 40
```
- Runs MediaPipe Pose on per-person crops (`model_complexity=1`, CPU-bound to preserve GPU VRAM).
- Fills a 32-frame deque with 205-dimensional geometric features per tracked individual.

### Week 4 — Human Activity Recognition (HAR)
1. **Train Model:** Open and execute `notebooks/04_har_training.ipynb` (trains `TemporalActivityTransformer` on UCF101 climbing subset + custom webcam clips).
2. **Run Live Inference on Webcam (Default):**
```bash
python backend/scripts/test_activity_recognition.py
```
- **Webcam Mode:** Predicts strictly between `standing`, `sitting`, and `walking`. If a person moves along the $x$, $y$, or $z$ axis, predicts `walking`; otherwise evaluates posture to predict `standing` or `sitting`. `climbing` and `running` are zeroed out in live webcam mode.
3. **Run on Uploaded `.mp4` Videos (from `source/` folder):**
```bash
python backend/scripts/test_activity_recognition.py --source source/Alone-man-climbing-SnapYT.App.mp4
```
- **Video Mode:** Evaluates all 5 classes (`walking`, `running`, `standing`, `sitting`, `climbing`).

### Week 5 — PPE Detection (Helmets, Vests, Persons)
1. **Train / Fine-Tune Model:** Open and execute `notebooks/05_ppe_training.ipynb` or run:
```bash
python backend/scripts/train_ppe.py --epochs 25
```
2. **Run Live PPE Verification:**
```bash
python backend/scripts/test_ppe.py
```
- Real-time overlay associating helmets (head upper-30% IoU) and vests (torso 20-70% IoU) with tracked person IDs.
- Reports live compliance status: `[HELMET OK]`, `[NO HELMET]`, `[VEST OK]`, `[NO VEST]`.

### Weeks 6 & 7 — Safety Rules: Fall Detection, PPE Compliance & Zone Intrusion

Run live safety rules pipeline test:
```bash
python backend/scripts/test_safety.py
```
- **Rule 1 (Fall Detection):** Fuses bounding box aspect ratio collapse (< 1.0), downward vertical velocity, and shoulder orientation angle (> 40°).
- **Rule 2 (PPE Compliance):** Detects missing helmets (HIGH) and missing high-visibility vests (MEDIUM) for active workers.
- **Rule 3 (Restricted Zone Intrusion):** Point-in-Polygon check on ankle landmarks (MediaPipe #27, #28) or bbox bottom center. Press **`z`** on the display window to interactively draw polygons with mouse clicks, or **`c`** to clear.
- **Rule 4 (Dangerous Climbing):** Flags climbing activity without hardhat / head protection (CRITICAL).

### Week 8 — Risk Scoring Engine (Composite Threat Metric)
Run the automated mathematical tests and live visual threat HUD:
```bash
# Automated formula & persistence unit test suite:
python backend/scripts/test_risk_engine.py --unit-tests

# Live camera pipeline with risk gauge & worker risk badges:
python backend/scripts/test_risk_engine.py
```
- **Composite Deterministic Metric ($0 - 100$):** Combines rule violation severity ($w_1$), activity risk ($w_2$), zone proximity ($w_3$), and violation persistence escalation ($+2\text{ pts/sec}$ unresolved non-compliance).
- **Severity Levels:** `LOW` ($0-29$), `MEDIUM` ($30-59$), `HIGH` ($60-79$), `CRITICAL` ($80-100$).
- **Scene Threat Gauge:** Dynamic scene-level aggregate threat assessment with exponential decay smoothing on violation resolution to eliminate flickering.

---

## 5. Implementation Roadmap (Weeks 5–12)

| Week | Component | Status | Deliverable |
|---|---|---|---|
| **Week 1** | Ingestion & Environment Check | **Complete** | OpenCV/FFmpeg video source, FastAPI skeleton, health endpoint |
| **Week 2** | Person Detection & Tracking | **Complete** | YOLO11n + ByteTrack, persistent tracking, inference FPS benchmarking |
| **Week 3** | Pose & Feature Extraction | **Complete** | MediaPipe BlazePose, 205-dim feature extractor, 32-frame bounded buffer |
| **Week 4** | Human Activity Recognition (HAR) | **Complete** | Small Temporal Transformer architecture, training notebook, inference module |
| **Week 5** | PPE Detection (Helmets, Vests) | **Complete** | Fine-tuned YOLO11n PPE detector, `notebooks/05_ppe_training.ipynb`, `backend/pipeline/ppe.py` |
| **Week 6** | Safety Rules: Fall Detection | **Complete** | Aspect ratio collapse + vertical velocity + pose orientation fusion in `safety_engine.py` |
| **Week 7** | Safety Rules: PPE & Zone Intrusion | **Complete** | Ankle Point-in-Polygon zone checks, interactive zone polygon GUI, dangerous climbing rule |
| **Week 8** | Risk Scoring Engine | **Complete** | Multi-factor deterministic risk formula (0–100 score: LOW/MED/HIGH/CRIT), `risk_engine.py` |
| **Week 9** | Multimodal VLM Integration | **Complete** | Gemini 1.5 Flash async verification, incident summaries, graceful fallback (`gemini_client.py`) |
| **Week 10**| WebSocket Streaming & Database | **Complete** | Low-latency binary/JSON streaming, SQLite incident & snapshot storage (`database.py`, `websocket.py`) |
| **Week 11**| Frontend Web Dashboard | **Complete** | React 18 + TypeScript + Vite + Tailwind dark industrial dashboard (`frontend/`) |
| **Week 12**| System Integration & Profiling | In progress | Repeatable regression tests, pipeline throughput profiler, demo and deployment documentation; hardware soak test remains |

### Running the System (Backend + Frontend)

#### 1. Start the FastAPI Backend (WebSocket & REST API):
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload
```

#### 2. Start the Frontend Industrial Safety Dashboard:
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser. The frontend includes:
- **Live Mode:** Real-time canvas stream, ByteTrack bounding boxes, pose, HAR, PPE badges, and SQLite incident log.
- **Demo Mode:** Fully simulated industrial multi-camera feeds, interactive hazard zones, and realistic risk timeline.

### Running Week 9 & 10 Verification

To verify the SQLite incident database, asynchronous Gemini 1.5 Flash VLM client with fallback, static snapshot serving, and WebSocket telemetry streaming:

```bash
python backend/scripts/test_vlm_and_db.py
```

To run the FastAPI server with live streaming and incident REST endpoints:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8010 --reload
```

---

## 6. Week 12: Profiling, Testing & Demo Hardening

### Automated regression checks

From the repository root, after installing `requirements.txt`:

```bash
pytest backend/tests -q
```

The Week 12 tests cover webcam-versus-file source classification, uploaded-video validation/history, and persistence of a video link on an incident record. The existing scripts under `backend/scripts/` remain useful for manual model and hardware checks.

### End-to-end throughput profile

Start the backend first, then run this in another terminal. The profiler starts the pipeline, samples frame count and backend FPS for one minute, prints measured throughput and backend FPS range, then stops the pipeline.

```bash
python backend/scripts/profile_pipeline.py --seconds 60
python backend/scripts/profile_pipeline.py --source data/videos/sample.mp4 --seconds 120
```

Use the same clip, model weights, resolution, and device when comparing results. The script profiles throughput; it does not replace the longer hardware soak test. Week 12 exit checks should also include a 30-minute run while watching RAM/VRAM, dropped frames, reconnects, database growth, and camera/model recovery after disconnects.

### Local app run

```bash
# Terminal 1, repository root
uvicorn backend.app.main:app --host 0.0.0.0 --port 8010

# Terminal 2
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend must be running for live mode, upload, camera enumeration, saved video history, and live incidents. The Vercel deployment only hosts the frontend; deploy FastAPI separately on a machine with the required model files, camera access, and persistent storage.

---

## 7. Demo Mode vs Live Mode

The top-bar mode switch controls the dashboard data source. **Demo Mode** is a frontend simulation with mock cameras, synthetic scene art, and generated telemetry; it does not run YOLO, pose, HAR, PPE, or the backend safety pipeline. Use it to present and navigate the UI without camera hardware or model files. **Live Mode** connects the frontend to FastAPI and its WebSocket. It displays frames and telemetry produced by the backend pipeline and writes incidents to the local SQLite database.

### A. Upload a video and see detections

1. Start FastAPI and the Vite frontend using the commands above; switch the top bar to **LIVE MODE**.
2. Open **Live Monitoring**. Under **Custom Video Source**, choose a video from your computer (MP4 is the safest choice; the backend also accepts MOV, AVI, MKV, WebM, MPEG, and MPG, up to 500 MB).
3. The backend saves the file under `data/videos/`, adds it to **Video history**, and starts pipeline processing. The source can be selected again from the history list.
4. Enable **Boxes**, **IDs & HAR**, **PPE Badges**, and **Hazard Zones** in the overlay controls. Bounding boxes and track IDs come from the detector/tracker; HAR labels appear when the trained checkpoint is present; hazard overlays come from configured zones.
5. Open **Events & Incidents** and select an incident. When it was generated while an uploaded video was active, **Recorded Video Evidence** plays that uploaded source. The video is linked to the incident, while the captured keyframe remains in `data/snapshots/` as fallback evidence.

### B. Use a webcam

1. Connect a webcam to the computer running the **backend**. OpenCV device `0` is the default; set `VIDEO_SOURCE=0` in the root `.env` or select **Default Webcam 0** in Live Monitoring.
2. Run the app and select **LIVE MODE**. Click **Start Processing**. The browser only displays the backend's stream; it does not grant webcam access to the backend. If FastAPI runs on another server, that server needs its own attached camera or an RTSP source.
3. Enable the same overlays. The live HAR mode is calibrated to `walking`, `standing`, and `sitting`; the recorded-video mode allows `walking`, `running`, `standing`, `sitting`, and `climbing`.
4. For reliable HAR output, train and place `models/har_temporal_transformer.pt`. If the checkpoint is missing, the activity recognizer reports not ready and HAR predictions are unavailable. Confirm detector/PPE weights and device availability in `/api/health` and backend logs.

**Bounding boxes, IDs, PPE, HAR, and hazard zones require Live Mode plus a working backend pipeline and model assets.** Demo Mode's simulated overlays are illustrative and are not model predictions.

---

## 8. Deploy the frontend to Vercel

The repository is a monorepo. Deploy the `frontend` directory as the Vercel project root; FastAPI, WebSocket streaming, computer-side video upload, model inference, and persistent video storage must run separately. Vercel documents automatic Vite support and recommends an SPA rewrite for deep links such as `/events/4` ([Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite), [rewrites](https://vercel.com/docs/routing/rewrites)).

1. Push the repository to GitHub. In Vercel, choose **Add New → Project**, import `AI-Powered-Industrial-Safety-Monitoring-System`, and set **Root Directory** to `frontend`.
2. Use the Vite defaults: **Framework Preset:** Vite, **Build Command:** `npm run build`, **Output Directory:** `dist`, **Install Command:** `npm install`. The checked-in `frontend/vercel.json` sends client-side routes back to `index.html`.
3. Deploy the FastAPI backend separately to a host that can run the needed models and preserve `data/safety_monitor.db`, `data/videos/`, and `data/snapshots/`. Ensure the backend is reachable over HTTPS/WSS and accepts requests from the Vercel domain.
   Set the backend's `CORS_ORIGINS` to a comma-separated allowlist containing your Vercel production domain (and any preview domain you use), for example `https://your-project.vercel.app`.
4. In Vercel → **Project Settings → Environment Variables**, add these for Preview and Production, replacing the example host with the backend's public HTTPS hostname:

   ```text
   VITE_API_BASE_URL=https://your-backend.example.com
   VITE_WS_URL=wss://your-backend.example.com/ws/stream
   ```

   Vite exposes `VITE_` variables in the browser bundle, so put only public URLs here—never `GEMINI_API_KEY` or other secrets. Vercel applies environment changes to new deployments, so redeploy after editing them ([Vercel environment variables](https://vercel.com/docs/environment-variables)).

5. Trigger a deployment and verify the homepage, a deep link such as `/events/1`, `/api/health` through the configured backend, WebSocket status, and media playback. For a UI-only demo, leave the app in **Demo Mode**; Live Mode needs the separately hosted backend and its camera/model/storage prerequisites.

For local Vite development, copy `frontend/.env.example` to `frontend/.env.local` and keep the backend running on `localhost:8010`.



