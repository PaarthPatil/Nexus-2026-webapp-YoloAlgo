import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
STORAGE_DIR = BASE_DIR / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
CHALLANS_DIR = STORAGE_DIR / "challans"
DATABASE_PATH = BASE_DIR / "nexustrace.db"
DEFAULT_MODEL_PATH = BASE_DIR / "yolov5su.pt"
ULTRALYTICS_SETTINGS_DIR = BASE_DIR / ".ultralytics"
COMPANY_NAME = os.getenv("NEXUSTRACE_COMPANY_NAME", "NexusTrace Logistics Pvt. Ltd.")
COMPANY_ADDRESS = os.getenv("NEXUSTRACE_COMPANY_ADDRESS", "Warehouse Zone, Industrial Area, City")
COMPANY_CONTACT = os.getenv("NEXUSTRACE_COMPANY_CONTACT", "+91-90000-00000 | ops@nexustrace.local")
COMPANY_GST_ID = os.getenv("NEXUSTRACE_COMPANY_GST_ID", "GSTIN: 00AAAAA0000A1Z5")
COMPANY_LOGO_PATH = os.getenv("NEXUSTRACE_COMPANY_LOGO_PATH", "").strip()


def ensure_app_dirs() -> None:
    for path in (LOGS_DIR, STORAGE_DIR, VIDEOS_DIR, CHALLANS_DIR, ULTRALYTICS_SETTINGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
