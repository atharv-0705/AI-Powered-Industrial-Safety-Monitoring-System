# DECISIONS.md — Multimodal Safety AI Monitor

> **Project:** Real-Time Multimodal Vision-Language Edge Safety Monitoring System  
> **Target Deployment:** Lenovo LOQ Gen 12-class (NVIDIA RTX 3050 6GB VRAM, 16 GB RAM, Windows 11 / WSL2)  
> **Status:** Living Document — Updated for Recommended Architecture Blueprint (Weeks 1–12 Scope)  
> **Guiding Principle (SRS §17):** Always maintain continuous alignment with the Risk Register and Resource Budgets.

---

## 1. System Architecture & Philosophy

The Multimodal Safety AI Monitor is architected as a **hybrid edge-first system**:
1. **Real-Time Deterministic Core (Local GPU/CPU):** Video ingestion, person detection, ByteTrack multi-object tracking, MediaPipe pose extraction, temporal feature buffering, Human Activity Recognition (HAR), PPE verification, safety rule evaluation, and numerical risk scoring all execute locally with zero internet dependency, guaranteeing consistent 10–15 FPS throughput and sub-500ms alert latency.
2. **Asynchronous Cognitive Layer (Cloud VLM):** Google Gemini 1.5 Flash is invoked strictly out-of-band as an asynchronous second opinion on high-risk incidents for natural-language explanation, audit logging, and operator Q&A. The core CV pipeline never blocks on network I/O.
3. **Decoupled Client-Server:** The FastAPI backend exposes RESTful endpoints for health/telemetry and bidirectional WebSockets for low-latency video and event streaming to the modern React + Vite frontend dashboard.

```
                           +-------------------------------------------------+
                           |             VIDEO INPUT SOURCE                  |
                           |   (Webcam RTSP / USB 0 or Local Video File)     |
                           +-------------------------------------------------+
                                                    |
                                                    v
                                  [backend/pipeline/ingestion.py]
                                  OpenCV VideoCapture + FFmpeg
                                    (12 FPS skip-sampling, bounded)
                                                    |
                                                    v
                                  [backend/pipeline/detector.py]
                                   YOLO11n + ByteTrack (FP16)
                                 (Tracked Person Bboxes + IDs)
                                                    |
                                       +------------+------------+
                                       |                         |
                                       v                         v
                         [backend/pipeline/ppe.py]   [backend/pipeline/pose.py]
                            YOLO11n Custom PPE          MediaPipe Pose (CPU)
                         (Helmet / Vest detection)     (33 Keypoints per crop)
                                       |                         |
                                       |                         v
                                       |             [backend/pipeline/features.py]
                                       |               32-frame Temporal Buffer
                                       |                  (205-dim feature vector)
                                       |                         |
                                       |                         v
                                       |               [backend/pipeline/har.py]
                                       |             Small Temporal Transformer
                                       |            (walking, running, climbing...)
                                       |                         |
                                       +------------+------------+
                                                    |
                                                    v
                                   [backend/pipeline/safety_engine.py]
                                   Deterministic Safety Rules Engine
                               (Fall, No-Helmet, Zone Intrusion, Climb)
                                                    |
                                                    v
                                   [backend/pipeline/risk_engine.py]
                                     Deterministic Risk Scoring
                                       (0 - 100 Risk Metric)
                                                    |
                               +--------------------+--------------------+
                               |                                         |
                               v                                         v
                 [backend/app/api/websocket.py]              [backend/app/vlm/gemini_client.py]
                   FastAPI WebSocket Server                   Gemini 1.5 Flash API (Async)
                               |                                 (Keyframe + Telemetry)
                               v                                         |
                     [frontend/ Dashboard]                               v
                    React + Vite + Tailwind                   [backend/app/db/models.py]
                     (Live alerts, overlays)                    SQLite / PostgreSQL DB
```

---

## 2. Complete Project Structure Blueprint

```
Development of a Multimodal Vision-Language/
├── configs/
│   └── config.yaml                     # Externalized pipeline thresholds, models, and zone configs
├── backend/
│   ├── __init__.py
│   ├── app/                            # Application & service layer
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI server entrypoint (CORS, router mounting, lifespan)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py               # Pydantic BaseSettings (reads .env & overrides)
│   │   │   └── env_check.py            # Hardware/GPU/CUDA/FFmpeg diagnostic tool
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── websocket.py            # Low-latency streaming connection manager & endpoint
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── health.py           # GET /api/health watchdog and component status
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   └── har_model.py            # PyTorch Small Temporal Transformer architecture definition
│   │   ├── vlm/
│   │   │   ├── __init__.py
│   │   │   └── gemini_client.py        # Asynchronous Gemini 1.5 Flash client with fallback
│   │   └── db/
│   │       ├── __init__.py
│   │       └── models.py               # Incident record schema (SQLite / PostgreSQL)
│   ├── pipeline/                       # Modular computer vision & inference pipeline
│   │   ├── __init__.py
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
│       └── __init__.py
├── frontend/                           # React + Vite + Tailwind CSS Web Dashboard (Week 11)
│   └── README.md                       # Setup, UI layout specs, and WebSocket client architecture
├── notebooks/                          # Jupyter Notebooks for all model training (Strict Rule)
│   ├── 04_har_training.ipynb           # Week 4: HAR dataset prep, training & evaluation
│   └── 05_ppe_training.ipynb           # Week 5: PPE dataset prep, YOLO11n fine-tuning & eval
├── data/                               # Dataset storage (Gitignored)
│   ├── raw/<class>/                    # Raw input MP4/AVI clips for HAR & PPE
│   ├── features/<class>/               # Pre-extracted (32, 205) feature tensors
│   └── ppe/                            # YOLO-formatted images and annotation labels
├── models/                             # Saved model checkpoints and manifests (Gitignored)
│   ├── har_temporal_transformer.pt
│   ├── har_temporal_transformer.manifest.json
│   └── ppe_yolo11n.pt
├── .env.example                        # Environment variable blueprint
├── .gitignore                          # Git exclusion rules (large binaries, checkpoints, venvs)
├── requirements.txt                    # Python package dependencies with pinned versions
├── DECISIONS.md                        # This comprehensive architecture and decisions document
└── README.md                           # System startup guide, run commands, and weekly roadmaps
```

---

## 3. Technology Decisions & Component Matrix

| # | Component | Technology Selected | Pretrained vs. Trained? | Dataset Used | Justification & Architectural Rationale |
|---|---|---|---|---|---|
| **1** | **Video Ingestion** | OpenCV `VideoCapture` + FFmpeg backend | **N/A (Algorithmic)** | None | Explicitly mandated by SRS §8.1. Normalizes webcam streams (DirectShow/V4L2) and file containers (MP4, MKV, AVI) into uniform BGR arrays. Includes deterministic frame-skipping (30 FPS source -> 12 FPS processing) to cap downstream compute load. |
| **2** | **Backend Server** | FastAPI + Uvicorn + WebSockets | **N/A (Framework)** | None | Async-native ASGI framework. Provides Pydantic data validation, high-throughput WebSockets for live video/telemetry frames, and OpenAPI documentation. Guarantees UI serving never blocks video processing threads (NFR-02). |
| **3** | **Person Detector** | **YOLO11n** (`yolo11n.pt`, Ultralytics) | **Pretrained on COCO** (Class 0: `person`) | Off-the-shelf COCO (80 classes) | Nano variant selected per SRS §8.2 baseline. Consumes only ~2.6M parameters and ~1.2 GB VRAM in FP16 mode. Preserves crucial GPU memory and compute headroom for downstream temporal and PPE models on the 6GB RTX 3050. YOLO11s upgrade is deferred until comprehensive profiling. |
| **4** | **Multi-Person Tracker** | **ByteTrack** (`bytetrack.yaml`) | **N/A (Algorithmic)** | None | SRS §7.2 mandate. Uses low-confidence detection matching with a Kalman filter to maintain identity persistence through occlusions without introducing additional neural network weights or VRAM consumption. |
| **5** | **Pose Estimator** | **MediaPipe Pose** (BlazePose GHUM) | **Pretrained** (Google MediaPipe package) | Off-the-shelf BlazePose | Runs on CPU with `model_complexity=1`. Emits 33 3D anatomical keypoints per person crop. Running pose estimation on CPU offloads the RTX 3050 GPU, balancing system utilization (SRS §8.3). |
| **6** | **Activity Recognition (HAR)** | **Small Temporal Transformer** (`backend/app/ml/har_model.py`) | **Trained From Scratch** | **UCF101 Subset + Custom Clips** (See §4) | Mandated by SRS §8.4 over full 3D RGB video transformers (e.g., SlowFast, VideoMAE). Consumes a 32-frame sequence of 205-dimensional geometric features instead of raw video frames, keeping parameter count < 350K and execution time < 5ms. |
| **7** | **PPE Detector** | **YOLO11n-PPE** (`models/ppe_yolo11n.pt`) | **Fine-Tuned / Trained** (Transfer Learning) | **Roboflow Hard Hat Workers / CHVK-PPE** (See §4) | Custom-trained on 4 classes: `helmet`, `no-helmet`, `vest`, `no-vest`. YOLO11n backbone preserves inference speed while achieving >85% mAP@0.5 on worker safety apparel (Week 5). |
| **8** | **Safety Rules Engine** | Deterministic Python Rule Evaluator | **N/A (Algorithmic / Heuristic)** | Domain rules & geometry | Combines pose geometry (torso angle, hip-to-ankle aspect ratio), downward bounding box velocity, and spatial Point-in-Polygon (PIP) testing for restricted work zones. Zero stochastic hallucination risk. |
| **9** | **Risk Scoring Engine** | Deterministic Multi-Factor Composite Scorer | **N/A (Mathematical Formula)** | Calibrated weights | Calculates an objective 0–100 risk score based on rule violations, activity severity, zone proximity, and violation persistence over time. Categorized into LOW, MEDIUM, HIGH, CRITICAL. |
| **10** | **Vision-Language Model (VLM)** | **Google Gemini 1.5 Flash API** | **Pretrained Foundation Model** (Cloud API) | Hosted by Google Cloud | Chosen per SRS §8.5 for rapid multimodal reasoning (1M token context, sub-2s API response). Invoked strictly out-of-band for second-opinion scene audit and natural-language incident summaries. Implements graceful fallback when offline (FR-20). |
| **11** | **Database** | **SQLite (MVP) / PostgreSQL (Prod)** | **N/A (Relational DB)** | Relational schema | Zero-configuration local file storage for MVP development; schema compatible with PostgreSQL via SQLAlchemy/SQLModel for multi-camera scalability and structured incident query retention. |
| **12** | **Frontend Dashboard** | **React + Vite + Tailwind CSS** | **N/A (Web UI)** | Web standards | High-performance SPA. Uses HTML5 Canvas for real-time video playback and interactive polygon zone configuration. Communicates with backend over WebSocket and REST. |

---

## 4. Datasets & Model Training Deep-Dive

Per project standing rules, any component requiring model training must have its dataset documented here and its complete training pipeline implemented in a Jupyter notebook (`notebooks/*.ipynb`).

### 4.1. Human Activity Recognition (HAR) — Temporal Transformer

- **Target Classes (5):** `walking`, `running`, `standing`, `sitting`, `climbing`
- **Input Feature Vector:** `(32, 205)` tensor representing 32 frames of:
  - 33 landmarks $\times$ $(x, y, z, \text{visibility})$ = 132 dims (normalized to person bbox)
  - 33 landmarks $\times$ $(\Delta x, \Delta y)$ velocity = 66 dims
  - Average elbow angle & knee angle normalized = 2 dims
  - Shoulder line body orientation angle = 1 dim
  - Bounding box normalized width & height = 2 dims
  - Bounding box center velocity $(\Delta cx, \Delta cy)$ = 2 dims
  - **Total: 205 dimensions per timestep**
- **Training Architecture:** `TemporalActivityTransformer` (2 Transformer encoder layers, 4 attention heads, $d_{\text{model}}=128$, feedforward dimension 256, GeLU activation, sinusoidal positional encoding).
- **The Dataset Coverage Gap (Identified & Resolved):**
  SRS §12.1 specifies "UCF101 subset + custom project clips." Direct verification of the official UCF101 dataset classes revealed that UCF101 only covers 2 of the 5 classes:
  1. `climbing`: Fully covered by `RockClimbingIndoor` (~200 clips).
  2. `walking`: Weakly covered by `WalkingWithDog` (contains dogs causing visual/bounding box occlusions).
  3. `running`: **0 clips** in UCF101 (UCF101 is sports-centric without a clean running category).
  4. `standing`: **0 clips** in UCF101 (no idle/standing posture clips).
  5. `sitting`: **0 clips** in UCF101.
- **Actionable Dataset Strategy:**
  - **Primary Custom Collection:** Minimum 40 clips per class (3–5 seconds each) recorded using standard workplace webcams (matching real deployment lens characteristics, per SRS §17).
  - **Group-Aware Splitting:** Clips are chopped into overlapping 32-frame sliding windows (stride = 8). Train/Validation/Test splits are strictly partitioned by *source video file ID* (never random window slicing), preventing data leakage where frames of the same video appear in both train and test sets.
  - **Class Weighting:** Cross-entropy loss is weighted inversely by class frequency to counteract imbalance caused by UCF101 climbing volume.
- **Training Execution:** `notebooks/04_har_training.ipynb`

### 4.2. Personal Protective Equipment (PPE) Detection — YOLO11n-PPE

- **Target Classes (4):** `helmet`, `no-helmet`, `vest`, `no-vest`
- **Dataset Candidates:**
  1. **Roboflow Hard Hat Workers Dataset:** ~5,000 annotated images covering construction environments with diverse lighting, worker orientations, and camera angles.
  2. **CHVK-PPE / Pictor-v3 Dataset:** Public safety dataset annotated with both safety helmets and high-visibility vests.
- **Annotation Format:** Standard YOLO format (`<class_id> <x_center> <y_center> <width> <height>` normalized 0–1).
- **Transfer Learning Strategy:** Fine-tuning the pretrained `yolo11n.pt` backbone. Freezing backbone layers for the initial 10 epochs, then unfreezing for 40 epochs with cosine learning rate decay and Mosaic augmentation disabled in the final 10 epochs.
- **Evaluation Metrics (SRS §12.3):** Precision, Recall, and mAP@0.5 (>85% target threshold).
- **Training Execution:** `notebooks/05_ppe_training.ipynb`

---

## 5. Architectural Design Decisions & Nuances

### 5.1. MediaPipe `static_image_mode=True` vs. Tracking Mode
MediaPipe Pose has a video tracking mode (`static_image_mode=False`) that reuses keypoints from frame $t-1$ to predict frame $t$. However, this assumes a static camera and a persistent ROI. In our pipeline, MediaPipe is fed **per-person crops sliced from YOLO11n + ByteTrack bounding boxes**. Because bounding box boundaries fluctuate dynamically as people move or bounding boxes expand/contract, feeding these crops into video mode causes MediaPipe's internal tracker to smooth across incongruent ROIs, leading to landmark drift. Setting `static_image_mode=True` treats each crop as an independent, clean detection, eliminating inter-frame artifact drift.

### 5.2. Asynchronous Decoupling of the VLM
Under no circumstances may a network call to the Gemini API occur within the video processing loop. A cloud network call takes 800ms–2500ms; running it synchronously would collapse the pipeline from 12 FPS to < 1 FPS. Instead, when the Safety Engine registers a high-risk event, it writes a keyframe JPEG and metadata payload to an in-memory queue. An asynchronous background task worker consumes the queue, calls Gemini 1.5 Flash, and publishes the explanation back to the database and WebSocket client.

### 5.3. Memory Bounding & Stale Track Pruning
Under continuous operation, ByteTrack assigns incremental track IDs as people enter and exit. If feature buffers were stored indefinitely, Python dictionary memory would grow unbounded, violating SRS NFR-04. The `TemporalFeatureManager` implements active pruning: any track ID not present in the current frame's detections increments a `frames_since_update` counter. Once this exceeds `STALE_TRACK_FRAMES` (60 frames $\approx$ 5 seconds), the buffer is purged from RAM.

---

## 6. Hardware Budget & Resource Allocation (Lenovo LOQ)

Target Machine: **NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM)**, 16 GB DDR5 RAM, Intel Core i5/i7 12th/13th Gen.

| Subsystem | Execution Target | VRAM Allocation | RAM Allocation | Target Latency / FPS |
|---|---|---|---|---|
| **YOLO11n Person Tracker** | CUDA (FP16) | ~1,200 MB | ~300 MB | 18–25 ms (~45 FPS standalone) |
| **YOLO11n PPE Detector** | CUDA (FP16) | ~1,100 MB | ~250 MB | 18–25 ms |
| **MediaPipe Pose (BlazePose)** | CPU (Multi-threaded) | 0 MB (CPU) | ~400 MB | 25–35 ms per person crop |
| **Feature Buffers + HAR** | CUDA / CPU | ~200 MB | ~150 MB | < 5 ms per inference |
| **FastAPI Backend + Stream** | CPU (Async IO) | 0 MB | ~250 MB | < 5 ms broadcast latency |
| **Operating System & PyTorch Context** | System | ~800 MB | ~4,000 MB | N/A |
| **Total Consumption** | **Hybrid** | **~3,300 MB** | **~5,350 MB** | **System Pipeline: 12–15 FPS** |
| **Headroom Available** | **Remaining** | **~2,700 MB (45%)** | **~10,650 MB (66%)** | **Safe from OOM** |

---

## 7. SRS §17 Complete Risk Register & Active Mitigations

This matrix is continuously audited and enforced across all project phases.

| Risk ID | SRS §17 Risk Description | Probability & Impact | Phase Affected | Concrete Mitigation Implemented in Code | Verification Metric / Test |
|---|---|---|---|---|---|
| **R-01** | **GPU Out of Memory (OOM)** | High Prob / Fatal Impact | Weeks 2, 4, 5 | 1. Model sizes strictly constrained to YOLO11n (nano, ~2.6M parameters).<br>2. Precision forced to FP16 half-precision on CUDA.<br>3. MediaPipe Pose offloaded to CPU.<br>4. HAR Transformer kept ultra-lightweight ($d_{\text{model}}=128$, 2 layers). | `backend/app/core/env_check.py` and `nvidia-smi` profile shows total VRAM < 3.8 GB under multi-person load. |
| **R-02** | **Inference Pipeline Low FPS (<10 FPS)** | Med Prob / High Impact | Weeks 2, 3, 4 | 1. Video ingestion decouples source capture (30 FPS) from processing (12 FPS skip-sampling).<br>2. Resolution locked to 640-class.<br>3. Separate rolling timers for ingestion FPS vs. model inference FPS to isolate bottlenecks. | `backend/scripts/test_tracking.py` reports `inference_fps >= 12.0` on target hardware. |
| **R-03** | **16 GB System RAM Pressure / Leaks** | Med Prob / High Impact | Weeks 3, 4, 10 | 1. Max queue depth strictly bounded (`maxlen=2` on ingestion, `maxlen=32` on temporal deques).<br>2. Stale track buffers automatically pruned after 60 frames of inactivity.<br>3. Never buffer full raw videos in system RAM. | Long-duration test (30 mins) with memory profiling showing stable heap footprint. |
| **R-04** | **Project Over-Scoping / Schedule Slip** | High Prob / High Impact | All Weeks | 1. Strict modular phase blueprint.<br>2. Placeholders created with explicit interfaces ahead of implementation.<br>3. Weeks 1–4 working core preserved without unnecessary rewrites. | Weekly deliverable exit criteria strictly mapped to SRS §16. |
| **R-05** | **Dataset Mismatch (Lab vs. Site)** | High Prob / High Impact | Weeks 4, 5 | 1. Identified UCF101 gap early before wasting training runs.<br>2. Mandated custom clips captured with deployment-grade webcams.<br>3. Class-weighted cross entropy in `04_har_training.ipynb`. | Evaluation confusion matrix shows balanced recall across all 5 classes. |
| **R-06** | **False Fall Alerts (Bounding Box Aspect Ratio Jitter)** | High Prob / Med Impact | Weeks 6, 7 | 1. Multi-frame persistence confirmation window (requires 6 consecutive frames of collapsed aspect ratio).<br>2. Multi-modal fusion: combines aspect ratio with landmark vertical velocity and hip-shoulder orientation. | Test clips of tying shoes or bending over do not trigger false positive fall alarms. |
| **R-07** | **Helmet & PPE Association Mismatch** | High Prob / Med Impact | Weeks 5, 7 | 1. Rather than whole-frame unbound detection, helmet detection evaluates Intersection-over-Union (IoU) with the upper 25% region of the tracked person's bounding box.<br>2. Person ID persistence handles transient occlusions. | Person standing behind railing retains correct helmet association. |
| **R-08** | **Boundary Jitter in Restricted Zones** | Med Prob / Low Impact | Weeks 6, 7 | 1. Point-in-Polygon (PIP) calculated on the center of the person's base (between feet landmarks 27 & 28), not the bounding box center.<br>2. Temporal hysteresis filter (person must be inside polygon for $\ge 3$ consecutive frames). | Worker walking immediately adjacent to zone perimeter does not trigger boundary flicker alerts. |
| **R-09** | **VLM API Failure / Quota Exceeded / Latency Spike** | High Prob / Med Impact | Week 9 | 1. VLM calls are completely decoupled from real-time loop.<br>2. Asynchronous client with configurable rate-limiting (default 10s cooldown per event).<br>3. Full graceful fallback (FR-20): system continues detecting and alerting if VLM is disabled or API key is absent. | Disconnecting network connection during alert generation results in clean warning log while CV pipeline maintains 12 FPS. |
| **R-10** | **Lighting & Low-Light Occlusion Variations** | Med Prob / Med Impact | Weeks 2, 5 | 1. YOLO11 training includes extensive photometric augmentations (HSV hue/saturation variations, brightness jitter).<br>2. MediaPipe visibility score thresholding ($>0.5$). | System tested against varied ambient lighting conditions. |

---

## 8. Summary of Project Restructure

The repository structure has been reorganized from the early prototype flat layout (`app/services/*`) into the **Recommended Blueprint**:
1. **Isolated Application (`backend/app/`):** Contains the FastAPI entrypoint (`main.py`), externalized configuration (`core/config.py`), system diagnostics (`core/env_check.py`), health checks (`api/routes/health.py`), ML architectures (`ml/har_model.py`), and future VLM/DB/WebSocket modules.
2. **Modular Inference Pipeline (`backend/pipeline/`):** Contains pure, testable stage processors: `ingestion.py`, `detector.py`, `pose.py`, `features.py`, and `har.py`, along with scaffolding for upcoming `ppe.py`, `safety_engine.py`, and `risk_engine.py`.
3. **Dedicated Configuration (`configs/config.yaml`):** Human-readable threshold and geometry configuration satisfying SRS NFR-08.
4. **Client Dashboard Foundation (`frontend/`):** Clean separation ready for Week 11 React + Vite UI integration.
5. **Preserved Artifacts (`notebooks/`, `data/`, `models/`):** All existing research notebooks and weights remain at repository root with updated import bindings.
