"""
HAR Feature Extraction & Model Training Pipeline

Executes the full pipeline:
  1. Extract (32, 205) temporal pose+motion feature windows from raw video clips
  2. Cache extracted features as .npy files in data/features/<class>/
  3. Perform group-aware Train / Val / Test splitting
  4. Train the Small Temporal Transformer (HARSmallTemporalTransformer)
  5. Evaluate on the Test set (Accuracy, Macro-F1, Confusion Matrix)
  6. Save checkpoint to models/har_temporal_transformer.pt + reproducibility manifest

Usage:
  python backend/scripts/train_har.py
  python backend/scripts/train_har.py --max-clips-per-class 60 --epochs 40
  python backend/scripts/train_har.py --skip-extraction --epochs 50
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import classification_report, confusion_matrix

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import get_settings
from backend.pipeline.ingestion import VideoSource
from backend.pipeline.detector import PersonTracker
from backend.pipeline.pose import PoseEstimator
from backend.pipeline.features import TemporalFeatureManager, SEQUENCE_LENGTH
from backend.app.ml.har_model import build_model, ACTIVITY_CLASSES, NUM_CLASSES

settings = get_settings()
RAW_DIR = PROJECT_ROOT / "data" / "raw"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"
CHECKPOINT_PATH = PROJECT_ROOT / settings.HAR_CHECKPOINT_PATH


def extract_windows_from_video(
    video_path: Path,
    tracker: PersonTracker,
    pose_estimator: PoseEstimator,
    feature_manager: TemporalFeatureManager,
    stride: int = 8,
    max_windows_per_clip: int = 6,
) -> list[np.ndarray]:
    """Extract (32, 205) windows from a single video clip."""
    source = VideoSource(str(video_path), source_fps=30, processing_fps=12)
    if not source.open():
        return []

    feature_manager.reset()
    windows = []
    primary_track_id = None
    frame_i = 0

    while True:
        result = source.read()
        if not result.ok:
            break
        frame = result.frame
        h, w = frame.shape[:2]
        tracked = tracker.track_frame(frame)
        if not tracked:
            frame_i += 1
            continue

        if primary_track_id is None:
            primary_track_id = max(tracked, key=lambda p: p.confidence).track_id
        person = next((p for p in tracked if p.track_id == primary_track_id), None)
        if person is None:
            frame_i += 1
            continue

        x1, y1, x2, y2 = (max(0, int(v)) for v in person.bbox_xyxy)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 10 or y2 - y1 < 10:
            frame_i += 1
            continue

        crop = frame[y1:y2, x1:x2]
        pose = pose_estimator.estimate(crop)
        if pose is None:
            frame_i += 1
            continue

        buf = feature_manager.update(person.track_id, pose, person.bbox_xyxy, (w, h))
        if buf.is_full and frame_i % stride == 0:
            windows.append(buf.as_array().copy())
            if len(windows) >= max_windows_per_clip:
                break
        frame_i += 1

    source.release()
    return windows


def build_feature_cache(
    max_clips_per_class: int = 0,
    stride: int = 8,
    max_windows_per_clip: int = 6,
) -> dict[str, int]:
    """Extract and cache (32, 205) features for all available raw clips."""
    print("=" * 60)
    print("Step 1: Feature Extraction Pipeline (Detection -> Pose -> Temporal)")
    print("=" * 60)

    device = settings.DETECTOR_DEVICE
    print(f"Loading YOLO detector ({settings.DETECTOR_MODEL}) on {device} ...")
    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=device,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )
    print("Loading MediaPipe PoseEstimator ...")
    pose_estimator = PoseEstimator()
    feature_manager = TemporalFeatureManager()

    counts = defaultdict(int)

    for class_name in ACTIVITY_CLASSES:
        class_raw_dir = RAW_DIR / class_name
        class_feat_dir = FEATURES_DIR / class_name
        class_feat_dir.mkdir(parents=True, exist_ok=True)

        if not class_raw_dir.exists():
            print(f"[WARN] No raw folder for '{class_name}' at {class_raw_dir}")
            continue

        clips = sorted(class_raw_dir.glob("*.avi")) + sorted(class_raw_dir.glob("*.mp4"))
        if max_clips_per_class > 0:
            clips = clips[:max_clips_per_class]

        print(f"\nProcessing '{class_name}' ({len(clips)} clips)...")
        class_windows = 0
        for i, clip_path in enumerate(clips):
            # Check if features for this clip are already cached
            existing = list(class_feat_dir.glob(f"{clip_path.stem}_*.npy"))
            if existing:
                class_windows += len(existing)
                continue

            windows = extract_windows_from_video(
                clip_path, tracker, pose_estimator, feature_manager,
                stride=stride, max_windows_per_clip=max_windows_per_clip
            )
            for w_idx, w in enumerate(windows):
                out_path = class_feat_dir / f"{clip_path.stem}_{w_idx:02d}.npy"
                np.save(out_path, w)

            class_windows += len(windows)
            if (i + 1) % 10 == 0 or (i + 1) == len(clips):
                print(f"  [{i+1:3d}/{len(clips)}] clips processed -> {class_windows} total windows cached")

        counts[class_name] = class_windows

    pose_estimator.close()

    print("\n" + "=" * 60)
    print("Feature Extraction Summary:")
    print("=" * 60)
    for class_name in ACTIVITY_CLASSES:
        print(f"  {class_name:12s}: {counts[class_name]:4d} windows")
    print(f"  {'TOTAL':12s}: {sum(counts.values()):4d} windows")
    return counts


class ActivitySequenceDataset(Dataset):
    def __init__(self, file_paths: list[Path], labels: list[int]):
        self.file_paths = file_paths
        self.labels = labels

    def __len__(self):
        return len(self.file_paths)

    def __getitem__(self, idx):
        seq = np.load(self.file_paths[idx]).astype(np.float32)
        return torch.from_numpy(seq), self.labels[idx]


def load_cached_dataset(val_frac: float = 0.15, test_frac: float = 0.15, seed: int = 42):
    """Load cached features with group-aware splitting (preventing clip data leakage)."""
    rng = np.random.default_rng(seed)
    all_files, all_labels, all_groups = [], [], []

    for class_idx, class_name in enumerate(ACTIVITY_CLASSES):
        class_dir = FEATURES_DIR / class_name
        for f in sorted(class_dir.glob("*.npy")):
            all_files.append(f)
            all_labels.append(class_idx)
            all_groups.append(f.stem.rsplit("_", 1)[0])

    if not all_files:
        raise RuntimeError(f"No cached features found in {FEATURES_DIR}. Run extraction first!")

    groups = sorted(set(all_groups))
    rng.shuffle(groups)
    n_val = max(1, int(len(groups) * val_frac))
    n_test = max(1, int(len(groups) * test_frac))
    val_groups = set(groups[:n_val])
    test_groups = set(groups[n_val:n_val + n_test])
    train_groups = set(groups[n_val + n_test:])

    def subset(target_groups):
        files = [f for f, g in zip(all_files, all_groups) if g in target_groups]
        labels = [l for l, g in zip(all_labels, all_groups) if g in target_groups]
        return files, labels

    train_files, train_labels = subset(train_groups)
    val_files, val_labels = subset(val_groups)
    test_files, test_labels = subset(test_groups)

    print("\nDataset Split (Group-Aware by Clip):")
    print(f"  Train: {len(train_files)} windows ({len(train_groups)} clips)")
    print(f"  Val:   {len(val_files)} windows ({len(val_groups)} clips)")
    print(f"  Test:  {len(test_files)} windows ({len(test_groups)} clips)")

    print("\nTrain class balance:")
    for class_idx, class_name in enumerate(ACTIVITY_CLASSES):
        n = sum(1 for l in train_labels if l == class_idx)
        print(f"  {class_name:12s}: {n:4d}")

    return (
        ActivitySequenceDataset(train_files, train_labels),
        ActivitySequenceDataset(val_files, val_labels),
        ActivitySequenceDataset(test_files, test_labels),
    )


def compute_class_weights(train_ds: ActivitySequenceDataset) -> torch.Tensor:
    counts = np.bincount(train_ds.labels, minlength=NUM_CLASSES).astype(np.float32)
    counts = np.clip(counts, 1, None)
    weights = counts.sum() / (NUM_CLASSES * counts)
    return torch.tensor(weights, dtype=torch.float32)


def train_model(
    train_ds: ActivitySequenceDataset,
    val_ds: ActivitySequenceDataset,
    epochs: int = 50,
    batch_size: int = 32,
    lr: float = 3e-4,
    patience: int = 10,
):
    """Train HARSmallTemporalTransformer model."""
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print("\n" + "=" * 60)
    print(f"Step 2: Model Training on {device.upper()}")
    print("=" * 60)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=(len(train_ds) > batch_size))
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = build_model().to(device)
    class_weights = compute_class_weights(train_ds).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    best_val_loss = float("inf")
    epochs_without_improvement = 0
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * x.size(0)
        train_loss /= len(train_ds)

        model.eval()
        val_loss, correct = 0.0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item() * x.size(0)
                correct += (logits.argmax(dim=1) == y).sum().item()
        val_loss /= len(val_ds)
        val_acc = correct / len(val_ds)

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(f"Epoch {epoch+1:2d}/{epochs:2d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
            CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": model.state_dict(),
                "activity_classes": ACTIVITY_CLASSES,
                "val_accuracy": val_acc,
                "val_loss": val_loss,
                "epoch": epoch + 1,
            }, CHECKPOINT_PATH)
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"Early stopping at epoch {epoch+1} (patience={patience})")
                break

    print(f"\nBest checkpoint saved to: {CHECKPOINT_PATH} (Val Loss: {best_val_loss:.4f})")
    return model, history


def evaluate_model(checkpoint_path: Path, test_ds: ActivitySequenceDataset) -> dict:
    """Evaluate trained model on test set."""
    print("\n" + "=" * 60)
    print("Step 3: Test Set Evaluation & Metrics")
    print("=" * 60)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model = build_model().to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)
    all_preds, all_labels = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            logits = model(x)
            preds = logits.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds.tolist())
            all_labels.extend(y.numpy().tolist())

    report = classification_report(all_labels, all_preds, labels=list(range(NUM_CLASSES)), target_names=ACTIVITY_CLASSES, output_dict=True, zero_division=0)
    print(classification_report(all_labels, all_preds, labels=list(range(NUM_CLASSES)), target_names=ACTIVITY_CLASSES, zero_division=0))

    cm = confusion_matrix(all_labels, all_preds, labels=list(range(NUM_CLASSES)))
    print("Confusion Matrix:")
    print("      " + " ".join(f"{c[:4]:>6s}" for c in ACTIVITY_CLASSES))
    for i, row in enumerate(cm):
        print(f"{ACTIVITY_CLASSES[i][:5]:>5s} " + " ".join(f"{v:6d}" for v in row))

    return {
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "checkpoint_epoch": checkpoint.get("epoch"),
        "val_accuracy": checkpoint.get("val_accuracy"),
    }


def write_manifest(checkpoint_path: Path, feature_counts: dict, history: dict, eval_results: dict):
    manifest = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": {
            "architecture": "TemporalActivityTransformer",
            "d_model": 128, "nhead": 4, "num_layers": 2, "dim_feedforward": 256,
            "input_dim": 205, "sequence_length": 32,
        },
        "classes": ACTIVITY_CLASSES,
        "dataset": {
            "source": "HMDB51 dataset (5 mapped classes: walk, run, stand, sit, climb_stairs)",
            "per_class_window_counts": feature_counts,
        },
        "training": {
            "best_epoch": eval_results.get("checkpoint_epoch"),
            "val_accuracy": eval_results.get("val_accuracy"),
            "test_macro_f1": eval_results["classification_report"]["macro avg"]["f1-score"] if "macro avg" in eval_results.get("classification_report", {}) else None,
            "epochs_run": len(history.get("train_loss", [])),
        },
        "feature_schema_version": "week3-205dim-v1",
    }
    manifest_path = checkpoint_path.with_suffix(".manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nReproducibility manifest written to: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(description="HAR Feature Extraction & Model Training")
    parser.add_argument("--skip-extraction", action="store_true", help="Skip feature extraction and use existing data/features/")
    parser.add_argument("--max-clips-per-class", type=int, default=70, help="Max raw clips to process per class (default: 70 for fast balanced training)")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs (default: 40)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate (default: 3e-4)")
    args = parser.parse_args()

    if not args.skip_extraction:
        feature_counts = build_feature_cache(max_clips_per_class=args.max_clips_per_class)
    else:
        feature_counts = {c: len(list((FEATURES_DIR / c).glob("*.npy"))) for c in ACTIVITY_CLASSES}

    train_ds, val_ds, test_ds = load_cached_dataset()
    model, history = train_model(train_ds, val_ds, epochs=args.epochs, batch_size=args.batch_size, lr=args.lr)
    eval_results = evaluate_model(CHECKPOINT_PATH, test_ds)
    write_manifest(CHECKPOINT_PATH, feature_counts, history, eval_results)
    print("\n🎉 HAR Training Pipeline Completed Successfully!")


if __name__ == "__main__":
    main()
