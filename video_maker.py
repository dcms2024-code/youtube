import textwrap
import numpy as np
from pathlib import Path
from gtts import gTTS
from moviepy import AudioFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, LANG, TLD

W, H = VIDEO_WIDTH, VIDEO_HEIGHT

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_PATHS_REGULAR = [
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


def _create_frame(title, subtitle, progress):
    img = Image.new("RGB", (W, H), (5, 3, 18))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(5 + 20 * (1 - t))
        g = int(3 + 8 * (1 - t))
        b = int(18 + 40 * (1 - t))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    np_img = np.array(img, dtype=np.float32)
    cy, cx = H / 2, W / 2
    Y, X = np.ogrid[:H, :W]
    dist = np.sqrt(((X - cx) / (W * 0.6)) ** 2 + ((Y - cy) / (H * 0.6)) ** 2)
    vignette = np.clip(1 - dist * 0.8, 0.2, 1.0)
    np_img *= vignette[:, :, np.newaxis]
    img = Image.fromarray(np_img.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    rng = np.random.default_rng(42)
    stars_x = rng.integers(0, W, 120)
    stars_y = rng.integers(0, H, 120)
    for sx, sy in zip(stars_x, stars_y):
        brightness = rng.integers(100, 220)
        draw.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(brightness, brightness, brightness))

    font_title = _load_font(FONT_PATHS, 56)
    font_body = _load_font(FONT_PATHS_REGULAR, 36)

    separator_y = 110
    draw.line([(80, separator_y), (W - 80, separator_y)], fill=(180, 140, 60), width=2)

    title_upper = title.upper()
    try:
        bbox = draw.textbbox((0, 0), title_upper, font=font_title)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw = draw.textsize(title_upper, font=font_title)[0]
    tx = (W - tw) // 2
    for ox, oy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
        draw.text((tx + ox, 35 + oy), title_upper, font=font_title, fill=(120, 90, 20))
    draw.text((tx, 35), title_upper, font=font_title, fill=(230, 195, 90))

    wrapped = textwrap.fill(subtitle, width=52)
    lines = wrapped.split("\n")
    line_height = 50
    total_text_h = len(lines) * line_height
    start_y = (H - total_text_h) // 2 + 20

    for i, line in enumerate(lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=font_body)
            lw = bbox[2] - bbox[0]
        except AttributeError:
            lw = draw.textsize(line, font=font_body)[0]
        lx = (W - lw) // 2
        ly = start_y + i * line_height
        draw.text((lx + 1, ly + 1), line, font=font_body, fill=(30, 20, 50))
        draw.text((lx, ly), line, font=font_body, fill=(220, 215, 230))

    bar_y = H - 18
    bar_w = int((W - 160) * progress)
    draw.rectangle([80, bar_y, W - 80, bar_y + 6], fill=(40, 30, 70))
    if bar_w > 0:
        draw.rectangle([80, bar_y, 80 + bar_w, bar_y + 6], fill=(180, 140, 60))

    return np.array(img)


def make_video(mystery, output_dir: Path) -> Path:
    title = mystery["title"]
    script = mystery["script"]

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title)[:40].strip()
    audio_path = output_dir / f"{safe_title}.mp3"
    video_path = output_dir / f"{safe_title}.mp4"

    tts = gTTS(text=script, lang=LANG, tld=TLD, slow=False)
    tts.save(str(audio_path))

    audio = AudioFileClip(str(audio_path))
    duration = audio.duration

    words = script.split()
    chunk_size = 14
    chunks = [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]
    chunk_dur = duration / len(chunks)

    clips = []
    for i, chunk in enumerate(chunks):
        progress = (i + 1) / len(chunks)
        frame = _create_frame(title, chunk, progress)
        clip = (
            ImageClip(frame)
            .with_duration(chunk_dur)
            .with_start(i * chunk_dur)
        )
        clips.append(clip)

    video = CompositeVideoClip(clips, size=(W, H)).with_audio(audio)
    video.write_videofile(
        str(video_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    audio.close()
    audio_path.unlink(missing_ok=True)

    return video_path
