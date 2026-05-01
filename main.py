#!/usr/bin/env python3
"""
YouTube Mysteries Bot - Genera y sube un video diario de misterios antiguos.
Uso normal (cron):  python3 main.py
Solo generar video: python3 main.py --no-upload
Autenticar YouTube: python3 main.py --auth
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, OUTPUT_DIR, STATE_FILE, LOG_FILE, CHANNEL_NAME
from mysteries import MYSTERIES
from video_maker import make_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_state():
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text())
    return {"used": []}


def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2))


def pick_mystery(state):
    used = set(state["used"])
    available = [i for i in range(len(MYSTERIES)) if i not in used]
    if not available:
        log.info("Todos los misterios usados, reiniciando ciclo.")
        state["used"] = []
        available = list(range(len(MYSTERIES)))
    return available[0], MYSTERIES[available[0]]


def build_description(mystery):
    return (
        f"{mystery['script']}\n\n"
        f"--- {CHANNEL_NAME} ---\n"
        f"Misterios de la antigüedad sin resolver. Un video cada día.\n"
        f"#misterios #historia #arqueología #antiguedad #misteriossinresolver"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true", help="Solo genera el video, no sube")
    parser.add_argument("--auth", action="store_true", help="Autenticar con YouTube API")
    args = parser.parse_args()

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    if args.auth:
        from uploader import _get_credentials
        log.info("Iniciando autenticación con YouTube...")
        _get_credentials()
        log.info("Autenticación completada. token.json guardado.")
        return

    state = load_state()
    idx, mystery = pick_mystery(state)
    log.info(f"Misterio #{idx}: {mystery['title']}")

    try:
        log.info("Generando video...")
        video_path = make_video(mystery, OUTPUT_DIR)
        log.info(f"Video creado: {video_path}")

        if not args.no_upload:
            from uploader import upload_video
            log.info("Subiendo a YouTube...")
            description = build_description(mystery)
            video_id = upload_video(video_path, mystery["title"], description)
            log.info(f"Video subido: https://youtube.com/watch?v={video_id}")

        state["used"].append(idx)
        save_state(state)

        if not args.no_upload:
            video_path.unlink(missing_ok=True)
        log.info("Proceso completado.")

    except Exception as e:
        log.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
