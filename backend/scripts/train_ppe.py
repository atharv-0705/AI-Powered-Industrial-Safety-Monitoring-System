"""
PPE Detector Training Pipeline (Week 5 Deliverable)

Fine-tunes YOLO11n on the Roboflow PPE dataset (helmets, vests, boots, gloves, persons)
on the local NVIDIA GPU (RTX 3050), evaluates mAP metrics, copies the best checkpoint
to models/ppe_yolo11n.pt, and produces a reproducibility manifest.

Usage:
    python backend/scripts/train_ppe.py
    python backend/scripts/train_ppe.py --epochs 30 --batch 16
    python backend/scripts/train_ppe.py --eval-only
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_YAML = PROJECT_ROOT / "data" / "ppe" / "data_local.yaml"
OUTPUT_MODEL_PATH = PROJECT_ROOT / "models" / "ppe_yolo11n.pt"
MANIFEST_PATH = PROJECT_ROOT / "models" / "ppe_yolo11n.manifest.json"


def train_ppe(
    data_yaml: Path = DATA_YAML,
    base_model: str = "yolo11n.pt",
    epochs: int = 25,
    batch_size: int = 16,
    img_size: int = 640,
    device: str | int = 0,
) -> tuple[YOLO, dict]:
    """Train/Fine-tune YOLO11n for PPE detection."""
    print("=" * 65)
    print("Week 5: Personal Protective Equipment (PPE) Detector Training")
    print("=" * 65)

    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset config not found at: {data_yaml}")

    # Determine device
    if isinstance(device, str) and device.lower() in ("cpu", "auto"):
        device_arg = 0 if torch.cuda.is_available() else "cpu"
    else:
        device_arg = 0 if torch.cuda.is_available() else "cpu"

    print(f"Dataset config: {data_yaml}")
    print(f"Base model:     {base_model}")
    print(f"Device:         {device_arg} ({'CUDA GPU' if device_arg == 0 else 'CPU'})")
    print(f"Epochs:         {epochs} | Batch size: {batch_size} | Image size: {img_size}")

    model = YOLO(base_model)

    print("\nStarting YOLO training loop...")
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch_size,
        imgsz=img_size,
        device=device_arg,
        workers=2,
        project=str(PROJECT_ROOT / "runs" / "ppe"),
        name="train_run",
        exist_ok=True,
        save=True,
        verbose=True,
    )

    # Best weights path from training run
    best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"
    if not best_weights.exists():
        best_weights = Path(model.trainer.save_dir) / "weights" / "last.pt"

    print(f"\nTraining complete! Best weights at: {best_weights}")

    # Evaluate validation metrics
    print("\nEvaluating validation metrics...")
    val_model = YOLO(str(best_weights))
    val_results = val_model.val(data=str(data_yaml), device=device_arg, verbose=False)

    map50 = float(val_results.box.map50) if hasattr(val_results.box, "map50") else 0.0
    map_all = float(val_results.box.map) if hasattr(val_results.box, "map") else 0.0
    mp = float(val_results.box.mp) if hasattr(val_results.box, "mp") else 0.0
    mr = float(val_results.box.mr) if hasattr(val_results.box, "mr") else 0.0

    print("-" * 50)
    print(f"mAP@0.5:      {map50:.4f}")
    print(f"mAP@0.5:0.95: {map_all:.4f}")
    print(f"Precision:    {mp:.4f}")
    print(f"Recall:       {mr:.4f}")
    print("-" * 50)

    # Copy to destination models/ppe_yolo11n.pt
    OUTPUT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, OUTPUT_MODEL_PATH)
    print(f"Checkpoint copied to: {OUTPUT_MODEL_PATH} ({OUTPUT_MODEL_PATH.stat().st_size / 1e6:.2f} MB)")

    metrics_dict = {
        "mAP50": map50,
        "mAP50_95": map_all,
        "precision": mp,
        "recall": mr,
        "epochs": epochs,
    }

    # Write reproducibility manifest
    write_manifest(val_model, metrics_dict, data_yaml)
    return val_model, metrics_dict


def write_manifest(model: YOLO, metrics: dict, data_yaml: Path):
    """Write NFR-12 reproducibility manifest."""
    manifest = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": {
            "architecture": "YOLO11n-PPE",
            "base_checkpoint": "yolo11n.pt",
            "task": "detect",
            "classes": model.names,
            "num_classes": len(model.names),
        },
        "dataset": {
            "source": "Roboflow PPE Dataset v3",
            "config_path": str(data_yaml),
            "annotated_categories": list(model.names.values()),
        },
        "metrics": metrics,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to: {MANIFEST_PATH}")


def evaluate_existing(checkpoint_path: Path = OUTPUT_MODEL_PATH, data_yaml: Path = DATA_YAML):
    """Evaluate already trained checkpoint."""
    print(f"Evaluating checkpoint: {checkpoint_path}")
    if not checkpoint_path.exists():
        print(f"Checkpoint not found at: {checkpoint_path}")
        return

    device_arg = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(str(checkpoint_path))
    val_results = model.val(data=str(data_yaml), device=device_arg, verbose=True)

    map50 = float(val_results.box.map50)
    map_all = float(val_results.box.map)
    mp = float(val_results.box.mp)
    mr = float(val_results.box.mr)

    print("\n" + "=" * 50)
    print(f"Checkpoint mAP@0.5:      {map50:.4f}")
    print(f"Checkpoint mAP@0.5:0.95: {map_all:.4f}")
    print(f"Checkpoint Precision:    {mp:.4f}")
    print(f"Checkpoint Recall:       {mr:.4f}")
    print("=" * 50)

    write_manifest(model, {
        "mAP50": map50, "mAP50_95": map_all, "precision": mp, "recall": mr
    }, data_yaml)


def main():
    parser = argparse.ArgumentParser(description="PPE Detector Training & Evaluation")
    parser.add_argument("--epochs", type=int, default=25, help="Number of training epochs (default: 25)")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size (default: 640)")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate existing checkpoint")
    args = parser.parse_args()

    if args.eval_only:
        evaluate_existing()
    else:
        train_ppe(epochs=args.epochs, batch_size=args.batch, img_size=args.imgsz)


if __name__ == "__main__":
    main()
