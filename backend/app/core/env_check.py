"""
Environment diagnostic: Python, OpenCV, FFmpeg, Torch/CUDA/GPU.

Run standalone:  python -m backend.app.core.env_check
Also imported by backend/app/api/routes/health.py so /api/health can report the
same information at runtime (NFR-12: reproducibility — model/runtime info
should be inspectable, not guessed).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict


@dataclass
class EnvReport:
    python_version: str
    opencv_version: str | None
    opencv_ok: bool
    ffmpeg_found: bool
    ffmpeg_path: str | None
    torch_installed: bool
    torch_version: str | None
    cuda_available: bool
    gpu_name: str | None
    gpu_vram_gb: float | None


def _check_opencv() -> tuple[str | None, bool]:
    try:
        import cv2  # noqa: WPS433 (intentional local import for isolated check)

        return cv2.__version__, True
    except Exception:
        return None, False


def _check_ffmpeg() -> tuple[bool, str | None]:
    path = shutil.which("ffmpeg")
    if path is None:
        return False, None
    try:
        subprocess.run(
            [path, "-version"], capture_output=True, check=True, timeout=5
        )
        return True, path
    except Exception:
        return False, path


def _check_torch_cuda() -> tuple[bool, str | None, bool, str | None, float | None]:
    try:
        import torch  # noqa: WPS433

        torch_installed = True
        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
        gpu_name = None
        gpu_vram_gb = None
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            gpu_vram_gb = round(props.total_memory / (1024**3), 2)
        return torch_installed, torch_version, cuda_available, gpu_name, gpu_vram_gb
    except Exception:
        return False, None, False, None, None


def run_env_check() -> EnvReport:
    opencv_version, opencv_ok = _check_opencv()
    ffmpeg_found, ffmpeg_path = _check_ffmpeg()
    torch_installed, torch_version, cuda_available, gpu_name, gpu_vram_gb = (
        _check_torch_cuda()
    )

    return EnvReport(
        python_version=sys.version.split()[0],
        opencv_version=opencv_version,
        opencv_ok=opencv_ok,
        ffmpeg_found=ffmpeg_found,
        ffmpeg_path=ffmpeg_path,
        torch_installed=torch_installed,
        torch_version=torch_version,
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
    )


def _print_report(report: EnvReport) -> None:
    print("=== Environment / GPU Check ===")
    print(f"Python:        {report.python_version}")
    print(f"OpenCV:        {report.opencv_version or 'NOT FOUND'} (ok={report.opencv_ok})")
    print(f"FFmpeg:        {'found at ' + report.ffmpeg_path if report.ffmpeg_found else 'NOT FOUND'}")
    print(f"Torch:         {report.torch_version or 'NOT INSTALLED'}")
    print(f"CUDA available:{report.cuda_available}")
    if report.cuda_available:
        print(f"GPU:           {report.gpu_name}")
        print(f"VRAM:          {report.gpu_vram_gb} GB")
    else:
        print("GPU:           none detected — pipeline will run in degraded/CPU mode")

    warnings = []
    if not report.opencv_ok:
        warnings.append("OpenCV missing — video ingestion (FR-01) will fail.")
    if not report.ffmpeg_found:
        warnings.append("FFmpeg missing — some video codecs/containers may fail to open.")
    if not report.cuda_available:
        warnings.append(
            "No CUDA GPU detected — YOLO11n/HAR (Week 2+) will run on CPU and miss "
            "the 10-15 FPS target (NFR-01)."
        )
    if warnings:
        print("\n--- Warnings ---")
        for w in warnings:
            print(f"  - {w}")


if __name__ == "__main__":
    _print_report(run_env_check())
