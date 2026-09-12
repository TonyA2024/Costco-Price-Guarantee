"""
This file pulls any new receipt photos sent via Taildrop and runs each one through the OCR
On Linux, (The Pi is a UNIX-based system) Taildrop files don't land in a normal folder automatically so
'tailscale file get' must be run to pull them out of the internal staging area. This script does that, then
processes whatever new image files have shown up.
"""

import os
import shutil
import subprocess
from pathlib import Path

from Backend.receipt_parser import parse_receipt
from Backend.save_to_dataset import write_to_database

INCOMING_DIR = Path(os.environ.get("RECEIPT_INCOMING_DIR", "-/receipts/incoming")).expanduser()
PROCESSED_DIR = INCOMING_DIR / "processed"
FAILED_DIR = INCOMING_DIR / "failed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

def pull_taildrop_files() -> None:
    """
    Pull any files waiting in Taildrop's staging area into INCOMING_DIR
    set to grab whatever is there and return rather than waiting until something arrives
    """

    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tailscale", "file", "get", "--wait=false", str(INCOMING_DIR)], check=True,
    )

def get_new_receipt_images() -> list[Path]:
    """
    Gets each new receipt image in the INCOMING_DIR
    """
    return [
        f for f in INCOMING_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]

def process_receipt_images() -> None:
    """
    Processes the images in the directory
    """
    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)
    api_key = os.environ["GOOGLE_VISION_API_KEY"]

    images = get_new_receipt_images()
    if not images:
        print("No new receipt images found")
        return

    for image_path in images:
        print(f"Processing {image_path.name}...")
        try:
            results = parse_receipt(str(image_path), api_key)
            write_to_database(results)
            shutil.move(str(image_path), str(PROCESSED_DIR / image_path.name))
            print(f"  --> saved {len(results)} item(s), moved to processed/")
        except Exception as e:
            # one bad photo shouldnt stop the rest from being processed
            print(f" --> Failed {e}")
            shutil.move(str(image_path), str(FAILED_DIR / image_path.name))

if __name__ == "__main__":
    pull_taildrop_files()
    process_receipt_images()