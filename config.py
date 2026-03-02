import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    DB_PATH = os.path.join(BASE_DIR, "data", "finance.db")
    IMPORT_FOLDER = os.path.expanduser("~/Downloads/spend_tracker")
    PROCESSED_FOLDER = os.path.expanduser("~/Downloads/spend_tracker/processed")
    SECRET_KEY = "dev-local-only"
