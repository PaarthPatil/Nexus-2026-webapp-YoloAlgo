from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
STORAGE_DIR = BASE_DIR / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
CHALLANS_DIR = STORAGE_DIR / "challans"
DATABASE_PATH = BASE_DIR / "nexustrace.db"
DEFAULT_MODEL_PATH = BASE_DIR / "yolov5su.pt"
ULTRALYTICS_SETTINGS_DIR = BASE_DIR / ".ultralytics"


def ensure_app_dirs() -> None:
    for path in (LOGS_DIR, STORAGE_DIR, VIDEOS_DIR, CHALLANS_DIR, ULTRALYTICS_SETTINGS_DIR):
        path.mkdir(parents=True, exist_ok=True)
