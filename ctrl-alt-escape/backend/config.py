import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    APP_NAME = os.getenv("APP_NAME", "CTRL_ALT_ESCAPE")
    APP_URL = os.getenv("APP_URL", "http://localhost:8000")

    # Firebase: service-account key file path (relative to ctrl-alt-escape/) or its JSON contents.
    # If neither is set, Google Application Default Credentials are used.
    FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "")
    FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
    FIRESTORE_COLLECTION_PREFIX = os.getenv("FIRESTORE_COLLECTION_PREFIX", "")

    PARTICIPANT_CSV_PATH = os.getenv("PARTICIPANT_CSV_PATH", "./data/Event_Registration.xlsx")
    PLACEHOLDER_NAME_PATTERN = os.getenv("PLACEHOLDER_NAME_PATTERN", r"^\d+$")

    # Required: set in .env (admin login is disabled until both are set)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    MIN_TEAM_SIZE = int(os.getenv("MIN_TEAM_SIZE", "3"))
    MAX_TEAM_SIZE = int(os.getenv("MAX_TEAM_SIZE", "4"))
    REQUEST_EXPIRY_SECONDS = int(os.getenv("REQUEST_EXPIRY_SECONDS", "180"))
    ONLINE_THRESHOLD_SECONDS = int(os.getenv("ONLINE_THRESHOLD_SECONDS", "15"))
    INITIAL_EVENT_PHASE = os.getenv("INITIAL_EVENT_PHASE", "REGISTRATION")

    MAX_WARNINGS = int(os.getenv("MAX_WARNINGS", "3"))
    LEVEL_TIMES = {
        1: int(os.getenv("LEVEL_1_TIME", "900")),
        2: int(os.getenv("LEVEL_2_TIME", "1080")),
        3: int(os.getenv("LEVEL_3_TIME", "1320")),
        4: int(os.getenv("LEVEL_4_TIME", "1320")),
        5: int(os.getenv("LEVEL_5_TIME", "1380")),
        6: int(os.getenv("LEVEL_6_TIME", "1200")),
    }
    MAX_CARRYOVER_SECONDS = int(os.getenv("MAX_CARRYOVER_SECONDS", "300"))

config = Config()
