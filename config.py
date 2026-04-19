import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

MAX_CONTEXT_MESSAGES = int(os.getenv("MAX_CONTEXT_MESSAGES", "10"))
MAX_RETRIEVAL_CHUNKS = int(os.getenv("MAX_RETRIEVAL_CHUNKS", "5"))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))

DATA_DIR = os.getenv("DATA_DIR", "./data")
DB_PATH = os.path.join(DATA_DIR, "bot.db")
VECTOR_STORE_DIR = os.path.join(DATA_DIR, "vector_stores")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MAX_FILE_SIZE_MB = 50

ANSWER_MODES = ["auto", "qa", "solver", "circuit", "hint"]
EXPLANATION_DEPTHS = ["simple", "normal", "deep", "exam"]

for directory in [DATA_DIR, VECTOR_STORE_DIR, UPLOADS_DIR]:
    os.makedirs(directory, exist_ok=True)
