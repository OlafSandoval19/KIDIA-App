from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def patient_folder(patient_id: int) -> Path:
    ensure_dirs()
    p = UPLOAD_DIR / f"patient_{patient_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_patient_csv(patient_id: int, filename: str, file_bytes: bytes) -> Path:
    folder = patient_folder(patient_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = folder / f"{ts}_{filename}"
    out.write_bytes(file_bytes)
    return out

def list_patient_csvs(patient_id: int):
    folder = patient_folder(patient_id)
    return sorted(folder.glob("*.csv"), reverse=True)
