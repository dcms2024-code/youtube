from pathlib import Path

BASE_DIR = Path("/home/andreu/youtube_bot")
OUTPUT_DIR = BASE_DIR / "output"
STATE_FILE = BASE_DIR / "state.json"
CREDENTIALS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"
LOG_FILE = BASE_DIR / "bot.log"

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 24
LANG = "es"
TLD = "es"

CHANNEL_NAME = "Misterios de la Antigüedad"
VIDEO_TAGS = ["misterios", "antigüedad", "historia", "arqueología", "misterios sin resolver", "arqueología antigua"]
VIDEO_CATEGORY_ID = "27"  # Education
