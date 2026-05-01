"""
Bot de Telegram para aprobacion de videos.
Uso: python3 telegram_bot.py
Escucha /aprobar o /rechazar despues de enviar el video para revision.
"""
import time
import requests
from pathlib import Path
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(text):
    requests.post(f"{BASE_URL}/sendMessage", data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=15)


def send_video(video_path: Path, caption: str):
    with open(video_path, "rb") as f:
        requests.post(f"{BASE_URL}/sendVideo", data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }, files={"video": f}, timeout=120)


def wait_for_approval(timeout=3600) -> bool:
    """Espera /aprobar o /rechazar. Devuelve True si aprobado."""
    offset = None
    deadline = time.time() + timeout

    while time.time() < deadline:
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        try:
            resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=40)
            updates = resp.json().get("result", [])
        except Exception:
            continue

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            chat = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "").strip().lower()

            if chat != TELEGRAM_CHAT_ID:
                continue
            if text in ("/aprobar", "aprobar", "si", "sí", "ok"):
                send_message("Video <b>aprobado</b>. Subiendo a YouTube...")
                return True
            if text in ("/rechazar", "rechazar", "no", "cancelar"):
                send_message("Video <b>rechazado</b>. No se sube.")
                return False

    send_message("Tiempo de espera agotado. Video no subido.")
    return False
