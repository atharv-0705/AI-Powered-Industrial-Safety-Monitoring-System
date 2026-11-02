"""
HAR Dataset Downloader — HMDB51 (Option 2: Public Datasets)

Downloads the HMDB51 dataset via HuggingFace Hub CDN (`Serrelab/hmdb51`) and extracts
only the 5 target classes mapped to our HAR categories:

    HMDB51 class    →  Our class
    ─────────────────────────────
    walk            →  walking
    run             →  running
    stand           →  standing
    sit             →  sitting
    climb_stairs    →  climbing

Reference:
  H. Kuehne, H. Jhuang, E. Garrote, T. Poggio, and T. Serre.
  "HMDB: A Large Human Motion Database." ICCV 2011.

Usage:
    python backend/scripts/download_har_data.py
    python backend/scripts/download_har_data.py --max-clips 50
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Class mapping: HMDB51 folder name → our target class name ──────────────
CLASS_MAP = {
    "walk":         "walking",
    "run":          "running",
    "stand":        "standing",
    "sit":          "sitting",
    "climb_stairs": "climbing",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DOWNLOADS_DIR = PROJECT_ROOT / "data" / "downloads"


def _find_extractor() -> str | None:
    """Locate a .rar extraction tool on the system."""
    # 0. Check local project tools directory
    local_candidates = [
        PROJECT_ROOT / "tools" / "7zip" / "full" / "7z.exe",
        PROJECT_ROOT / "tools" / "7zip" / "x64" / "7za.exe",
        PROJECT_ROOT / "tools" / "7zip" / "7za.exe",
    ]
    for cand in local_candidates:
        if cand.is_file():
            return str(cand)

    # 1. Check standard 7-Zip paths on Windows
    for candidate in [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate

    # 2. Check PATH
    for name in ("7z", "7z.exe", "7za", "7za.exe", "unrar", "unrar.exe"):
        path = shutil.which(name)
        if path:
            return path

    return None


def _extract_rar(rar_path: str, dest_dir: str, extractor: str, specific_files: list[str] | None = None) -> bool:
    """Extract a .rar archive using 7z or unrar."""
    tool_name = Path(extractor).stem.lower()
    if "7z" in tool_name or "7za" in tool_name:
        cmd = [extractor, "x", "-y", f"-o{dest_dir}", rar_path]
        if specific_files:
            cmd.extend(specific_files)
    else:  # unrar
        cmd = [extractor, "x", "-y", rar_path]
        if specific_files:
            cmd.extend(specific_files)
        cmd.append(dest_dir + os.sep)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[download_har_data] Extraction notice:\n{result.stderr[:400]}")
    return result.returncode == 0


def download_from_hf(dest_file: str) -> str:
    """Download HMDB51 archive from Hugging Face Hub."""
    from huggingface_hub import hf_hub_download
    print("[download_har_data] Downloading hmdb51_org.rar from HuggingFace (Serrelab/hmdb51) ...")
    path = hf_hub_download(
        repo_id="Serrelab/hmdb51",
        filename="hmdb51_org.rar",
        repo_type="dataset",
        local_dir=str(DOWNLOADS_DIR),
    )
    return path


def download_hmdb51(max_clips_per_class: int = 0):
    """Download HMDB51, extract only the 5 target classes, organize into data/raw/."""

    # ── Step 0: Find or install .rar extractor ──────────────────────────
    extractor = _find_extractor()
    if not extractor:
        print("[ERROR] Cannot extract .rar files. No 7-Zip or unrar found.")
        sys.exit(1)
    print(f"[download_har_data] Using extractor: {extractor}")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    rar_path = DOWNLOADS_DIR / "hmdb51_org.rar"

    # ── Step 1: Download the full HMDB51 archive (~2 GB) ────────────
    if not rar_path.exists() or rar_path.stat().st_size < 100_000_000:
        download_from_hf(str(rar_path))
    else:
        size_mb = rar_path.stat().st_size / (1024 * 1024)
        print(f"[download_har_data] Using cached archive: {rar_path} ({size_mb:.1f} MB)")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # ── Step 2: Extract only the 5 target class .rar files ──────────
        print("[download_har_data] Extracting target class archives from HMDB51 ...")
        target_rars = [f"{hmdb_name}.rar" for hmdb_name in CLASS_MAP.keys()]
        _extract_rar(str(rar_path), tmp_dir, extractor, target_rars)

        # ── Step 3: Extract each class .rar → AVI files → data/raw/ ────
        for hmdb_name, our_name in CLASS_MAP.items():
            class_rar = os.path.join(tmp_dir, f"{hmdb_name}.rar")
            if not os.path.isfile(class_rar):
                # Search recursively in case subdirectories exist
                found = list(Path(tmp_dir).glob(f"**/{hmdb_name}.rar"))
                if found:
                    class_rar = str(found[0])
                else:
                    print(f"[WARNING] {hmdb_name}.rar not found in archive — skipping '{our_name}'")
                    continue

            dest = RAW_DIR / our_name
            dest.mkdir(parents=True, exist_ok=True)

            # Extract into a temp sub-dir first
            class_tmp = os.path.join(tmp_dir, f"_extract_{hmdb_name}")
            os.makedirs(class_tmp, exist_ok=True)
            _extract_rar(class_rar, class_tmp, extractor)

            # Move .avi / .mp4 files to data/raw/<our_name>/
            moved = 0
            for root, _, files in os.walk(class_tmp):
                for fname in sorted(files):
                    if fname.lower().endswith((".avi", ".mp4")):
                        src = os.path.join(root, fname)
                        dst = dest / fname
                        if not dst.exists():
                            shutil.move(src, dst)
                            moved += 1
                            if max_clips_per_class > 0 and moved >= max_clips_per_class:
                                break
                if max_clips_per_class > 0 and moved >= max_clips_per_class:
                    break

            print(f"  {our_name:12s} ({hmdb_name:14s}): {moved} clips -> {dest}")

    # ── Step 4: Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("HMDB51 Dataset Download & Preparation Complete!")
    print("=" * 60)
    total = 0
    for our_name in CLASS_MAP.values():
        d = RAW_DIR / our_name
        count = len(list(d.glob("*.avi"))) + len(list(d.glob("*.mp4"))) if d.exists() else 0
        total += count
        status = "[OK]" if count >= 20 else "[LOW]"
        print(f"  {our_name:12s}: {count:4d} clips  {status}")
    print(f"  {'TOTAL':12s}: {total:4d} clips")
    print(f"\nRaw clips are ready at: {RAW_DIR}")
    print("Next step: Run feature extraction in notebooks/04_har_training.ipynb")


def main():
    parser = argparse.ArgumentParser(description="Download HMDB51 for HAR training")
    parser.add_argument(
        "--max-clips", type=int, default=0,
        help="Max clips per class (0 = all available, default: all)"
    )
    args = parser.parse_args()
    download_hmdb51(max_clips_per_class=args.max_clips)


if __name__ == "__main__":
    main()
