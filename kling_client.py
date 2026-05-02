import jwt
import time
import base64
import logging
import requests
from io import BytesIO
from PIL import Image
import numpy as np

KLING_API_BASE = "https://api.klingai.com"


def _token(access_key, secret_key):
    now = int(time.time())
    payload = {"iss": access_key, "iat": now, "exp": now + 300, "nbf": now - 5}
    return jwt.encode(payload, secret_key, algorithm="HS256")


def _headers(access_key, secret_key):
    return {
        "Authorization": f"Bearer {_token(access_key, secret_key)}",
        "Content-Type": "application/json",
    }


def image_to_video_bytes(img_array, prompt, access_key, secret_key, duration=5):
    """Anima una imagen numpy con Kling y devuelve los bytes del MP4."""
    buf = BytesIO()
    Image.fromarray(img_array).save(buf, format="JPEG", quality=90)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    body = {
        "image": img_b64,
        "prompt": prompt + ", cinematic motion, dramatic atmosphere",
        "duration": duration,
        "aspect_ratio": "16:9",
        "model_name": "kling-v1",
        "mode": "std",
    }

    resp = requests.post(
        f"{KLING_API_BASE}/v1/videos/image2video",
        headers=_headers(access_key, secret_key),
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"Kling error: {data.get('message')}")
    task_id = data["data"]["task_id"]
    logging.info(f"Kling task {task_id} enviado")

    for attempt in range(72):  # max 12 minutos
        time.sleep(10)
        poll = requests.get(
            f"{KLING_API_BASE}/v1/videos/image2video/{task_id}",
            headers=_headers(access_key, secret_key),
            timeout=30,
        )
        poll.raise_for_status()
        d = poll.json()["data"]
        status = d["task_status"]
        logging.info(f"Kling task {task_id}: {status} ({attempt*10}s)")

        if status == "succeed":
            video_url = d["task_result"]["videos"][0]["url"]
            video_bytes = requests.get(video_url, timeout=120).content
            logging.info(f"Kling clip descargado ({len(video_bytes)//1024} KB)")
            return video_bytes
        elif status == "failed":
            raise RuntimeError(f"Kling task fallida: {d.get('task_status_msg', '?')}")

    raise TimeoutError(f"Kling task {task_id} no terminó en 12 minutos")
