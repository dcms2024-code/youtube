import textwrap
import subprocess
import requests
import random
from io import BytesIO
import numpy as np
from pathlib import Path
from gtts import gTTS
from moviepy import AudioFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, LANG, TLD, PEXELS_API_KEY, AUDIO_SPEED

W, H = VIDEO_WIDTH, VIDEO_HEIGHT

FONT_PATHS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _load_font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _fetch_pexels_images(query, num=6):
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "per_page": num + 2, "orientation": "landscape"}
        resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        photos = resp.json().get("photos", [])[:num]
        if not photos:
            return None
        images = []
        for photo in photos:
            url = photo["src"].get("large2x") or photo["src"]["large"]
            img_resp = requests.get(url, timeout=20)
            img = Image.open(BytesIO(img_resp.content)).convert("RGB")
            img_ratio = img.width / img.height
            out_ratio = W / H
            if img_ratio > out_ratio:
                new_h, new_w = H, int(H * img_ratio)
            else:
                new_w, new_h = W, int(W / img_ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            x, y = (new_w - W) // 2, (new_h - H) // 2
            img = img.crop((x, y, x + W, y + H))
            images.append(np.array(img))
        return images or None
    except Exception:
        return None


def _dark_overlay(img_array, alpha=0.58):
    return (img_array * (1 - alpha)).astype(np.uint8)


def _create_frame(bg_img, title, subtitle, progress):
    base = _dark_overlay(bg_img)
    img = Image.fromarray(base)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_PATHS_BOLD, 52)
    font_body = _load_font(FONT_PATHS, 34)

    # Gold separator
    draw.line([(80, 108), (W - 80, 108)], fill=(210, 170, 50), width=2)

    # Title
    title_upper = title.upper()
    try:
        bbox = draw.textbbox((0, 0), title_upper, font=font_title)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(title_upper, font=font_title)
    tx = (W - tw) // 2
    draw.text((tx + 2, 34), title_upper, font=font_title, fill=(60, 40, 5))
    draw.text((tx, 32), title_upper, font=font_title, fill=(240, 200, 70))

    # Subtitle
    wrapped = textwrap.fill(subtitle, width=54)
    lines = wrapped.split("\n")
    line_h = 50
    total_h = len(lines) * line_h
    start_y = (H - total_h) // 2 + 30

    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font_body)
            lw = bbox[2] - bbox[0]
        except AttributeError:
            lw, _ = draw.textsize(line, font=font_body)
        lx = (W - lw) // 2
        ly = start_y + i * line_h
        draw.text((lx + 2, ly + 2), line, font=font_body, fill=(0, 0, 0))
        draw.text((lx, ly), line, font=font_body, fill=(240, 235, 225))

    # Progress bar
    bar_y = H - 18
    bw = int((W - 160) * progress)
    draw.rectangle([80, bar_y, W - 80, bar_y + 6], fill=(25, 15, 40))
    if bw > 0:
        draw.rectangle([80, bar_y, 80 + bw, bar_y + 6], fill=(210, 170, 50))

    return np.array(img)


def _speed_audio(input_path, output_path, speed=AUDIO_SPEED):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-filter:a", f"atempo={speed}", str(output_path)],
        capture_output=True, check=True,
    )


def _fallback_bg():
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y / H
        bg[y, :] = [int(8 + 25 * (1 - t)), int(4 + 10 * (1 - t)), int(20 + 50 * (1 - t))]
    return bg


def make_video(mystery, output_dir: Path) -> Path:
    title = mystery["title"]
    script = mystery["script"]

    output_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:40].strip()
    audio_raw = output_dir / f"{safe}_raw.mp3"
    audio_path = output_dir / f"{safe}.mp3"
    video_path = output_dir / f"{safe}.mp4"

    tts = gTTS(text=script, lang=LANG, tld=TLD, slow=False)
    tts.save(str(audio_raw))
    _speed_audio(audio_raw, audio_path)
    audio_raw.unlink(missing_ok=True)

    audio = AudioFileClip(str(audio_path))
    duration = audio.duration

    words = script.split()
    chunk_size = 14
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    chunk_dur = duration / len(chunks)

    images = _fetch_pexels_images(title, num=len(chunks))

    clips = []
    for i, chunk in enumerate(chunks):
        progress = (i + 1) / len(chunks)
        bg = images[i % len(images)] if images else _fallback_bg()
        frame = _create_frame(bg, title, chunk, progress)
        clip = ImageClip(frame).with_duration(chunk_dur).with_start(i * chunk_dur)
        clips.append(clip)

    video = CompositeVideoClip(clips, size=(W, H)).with_audio(audio)
    video.write_videofile(str(video_path), fps=FPS, codec="libx264", audio_codec="aac", logger=None)

    audio.close()
    audio_path.unlink(missing_ok=True)

    return video_path
