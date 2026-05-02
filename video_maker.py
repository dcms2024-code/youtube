import textwrap
import subprocess
import requests
import logging
import random
import time
from io import BytesIO
import numpy as np
from pathlib import Path
from gtts import gTTS
from moviepy import AudioFileClip, VideoClip, VideoFileClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
from urllib.parse import quote
from config import VIDEO_WIDTH, VIDEO_HEIGHT, FPS, LANG, TLD, AUDIO_SPEED

try:
    from config import HF_TOKEN
except Exception:
    HF_TOKEN = None

W, H = VIDEO_WIDTH, VIDEO_HEIGHT
KB_ZOOM = 1.25

FONT_PATHS_BOLD = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_PATHS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

VISUAL_KEYWORDS = {
    "cámara":       "hidden chamber underground interior stone",
    "cavidad":      "hidden cavity underground mysterious dark",
    "pasillo":      "ancient corridor underground passage stone",
    "interior":     "interior inside underground ancient chamber",
    "túnel":        "underground tunnel ancient mysterious",
    "piedras":      "massive stone blocks ancient construction",
    "bloques":      "giant stone blocks ancient megalith",
    "toneladas":    "enormous massive stones ancient construction",
    "pirámide":     "pyramid ancient egypt aerial view dramatic",
    "esfinge":      "sphinx ancient egypt dramatic desert",
    "desierto":     "vast desert dramatic sky ancient",
    "estrellas":    "night sky stars constellations ancient",
    "océano":       "dramatic ocean waves underwater ruins",
    "templo":       "ancient temple ruins dramatic lighting",
    "ruinas":       "ancient ruins overgrown mysterious dramatic",
    "ciudad":       "ancient city ruins aerial dramatic",
    "selva":        "dense jungle mysterious ancient ruins",
    "cueva":        "cave underground stalactites mysterious",
    "erosión":      "ancient stone water erosion mysterious",
    "mercurio":     "liquid mercury mysterious ancient chamber",
    "inscripción":  "ancient inscription hieroglyphs stone close-up",
    "mapa":         "ancient map parchment mysterious cartography",
    "soldado":      "dark military laboratory mysterious soviet",
    "experimento":  "dark science laboratory mysterious soviet cold war",
    "señal":        "radio antenna transmission mysterious night",
    "zumbido":      "mysterious sound waves dark atmosphere",
    "sueño":        "surreal dreamscape mysterious person sleeping",
    "rostro":       "mysterious portrait face dramatic dark",
    "teléfono":     "old phone ringing ghost spirit mysterious",
    "pueblo":       "abandoned village eerie overgrown mysterious",
    "desapareci":   "abandoned place eerie mysterious empty",
    "dimens":       "parallel dimension portal surreal mysterious",
    "invisible":    "invisible figure silhouette mysterious dramatic",
    "libro":        "ancient mysterious book candlelight dark gothic",
    "manuscrito":   "ancient manuscript mysterious medieval dark",
    "solsticio":    "sunrise solstice ancient stones light rays",
    "alineac":      "ancient stone alignment sunrise dramatic light",
}


def _chunk_to_prompt(base_prompt, chunk_text):
    additions = []
    text_lower = chunk_text.lower()
    for keyword, visual in VISUAL_KEYWORDS.items():
        if keyword in text_lower:
            additions.append(visual)
            if len(additions) >= 2:
                break
    return " ".join(additions) + " cinematic dramatic mysterious 8k" if additions else base_prompt


def _load_font(paths, size):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _dark_overlay(img_array, alpha=0.58):
    return (img_array * (1 - alpha)).astype(np.uint8)


def _create_text_overlay(title, subtitle, progress):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_title = _load_font(FONT_PATHS_BOLD, 52)
    font_body = _load_font(FONT_PATHS, 34)

    draw.line([(80, 108), (W - 80, 108)], fill=(210, 170, 50, 255), width=2)

    title_upper = title.upper()
    try:
        bbox = draw.textbbox((0, 0), title_upper, font=font_title)
        tw = bbox[2] - bbox[0]
    except AttributeError:
        tw, _ = draw.textsize(title_upper, font=font_title)
    tx = (W - tw) // 2
    draw.text((tx + 2, 34), title_upper, font=font_title, fill=(60, 40, 5, 200))
    draw.text((tx, 32), title_upper, font=font_title, fill=(240, 200, 70, 255))

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
        draw.text((lx + 2, ly + 2), line, font=font_body, fill=(0, 0, 0, 180))
        draw.text((lx, ly), line, font=font_body, fill=(240, 235, 225, 255))

    bar_y = H - 18
    bw = int((W - 160) * progress)
    draw.rectangle([80, bar_y, W - 80, bar_y + 6], fill=(25, 15, 40, 200))
    if bw > 0:
        draw.rectangle([80, bar_y, 80 + bw, bar_y + 6], fill=(210, 170, 50, 255))

    return np.array(overlay)


def _make_video_clip(bg_clip, title, subtitle, progress, duration):
    """Aplica overlay de texto sobre un VideoFileClip con loop si hace falta."""
    overlay = Image.fromarray(_create_text_overlay(title, subtitle, progress), "RGBA")
    clip_dur = bg_clip.duration

    def make_frame(t):
        frame = bg_clip.get_frame(t % clip_dur)
        if frame.shape[0] != H or frame.shape[1] != W:
            frame = np.array(Image.fromarray(frame).resize((W, H), Image.LANCZOS))
        frame = _dark_overlay(frame)
        frame_pil = Image.fromarray(frame).convert("RGBA")
        frame_pil.alpha_composite(overlay)
        return np.array(frame_pil.convert("RGB"))

    return VideoClip(make_frame, duration=duration)


def _make_animated_clip(bg_img, title, subtitle, progress, duration):
    """Ken Burns como fallback cuando no hay video IA."""
    big_w = int(W * KB_ZOOM)
    big_h = int(H * KB_ZOOM)
    img_big = np.array(Image.fromarray(bg_img).resize((big_w, big_h), Image.LANCZOS))
    max_x, max_y = big_w - W, big_h - H
    cx, cy = max_x // 2, max_y // 2
    effects = [
        ((0, cy, W, H), (max_x, cy, W, H)),
        ((max_x, cy, W, H), (0, cy, W, H)),
        ((cx, 0, W, H), (cx, max_y, W, H)),
        ((cx, max_y, W, H), (cx, 0, W, H)),
        ((0, 0, big_w, big_h), (cx, cy, W, H)),
        ((cx, cy, W, H), (0, 0, big_w, big_h)),
    ]
    (sx, sy, sw, sh), (ex, ey, ew, eh) = random.choice(effects)
    overlay = Image.fromarray(_create_text_overlay(title, subtitle, progress), "RGBA")

    def make_frame(t):
        p = t / duration
        p = p * p * (3 - 2 * p)
        cw = max(int(sw + (ew - sw) * p), 1)
        ch = max(int(sh + (eh - sh) * p), 1)
        x = max(0, min(int(sx + (ex - sx) * p), big_w - cw))
        y = max(0, min(int(sy + (ey - sy) * p), big_h - ch))
        crop = img_big[y:y + ch, x:x + cw]
        frame = crop.copy() if (cw == W and ch == H) else np.array(Image.fromarray(crop).resize((W, H), Image.LANCZOS))
        frame = _dark_overlay(frame)
        frame_pil = Image.fromarray(frame).convert("RGBA")
        frame_pil.alpha_composite(overlay)
        return np.array(frame_pil.convert("RGB"))

    return VideoClip(make_frame, duration=duration)


def _generate_hf_videos(prompts, hf_token, tmp_dir):
    """Genera clips de video con HuggingFace Wan2.2 (fal-ai)."""
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        logging.warning("huggingface_hub no instalado")
        return None

    client = InferenceClient(provider="fal-ai", api_key=hf_token)
    clips = []
    for i, prompt in enumerate(prompts):
        clip_path = tmp_dir / f"hf_{i}.mp4"
        for attempt in range(3):
            try:
                logging.info(f"HF video {i+1}/{len(prompts)}: {prompt[:60]}...")
                video_bytes = client.text_to_video(prompt, model="Wan-AI/Wan2.2-T2V-A14B")
                clip_path.write_bytes(video_bytes)
                clips.append(VideoFileClip(str(clip_path)))
                logging.info(f"HF clip {i+1} OK")
                break
            except Exception as e:
                logging.warning(f"HF clip {i+1} intento {attempt+1} fallido: {e}")
                if attempt < 2:
                    time.sleep(15)
        else:
            clips.append(None)
        time.sleep(3)

    return clips if any(c is not None for c in clips) else None


def _fetch_pollinations_image(prompt):
    """Descarga una imagen de Pollinations como fallback."""
    seeds = [42, 7, 137, 333, 999]
    for seed in seeds:
        try:
            url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=960&height=540&model=flux&nologo=true&seed={seed}"
            resp = requests.get(url, timeout=90)
            if resp.status_code == 429:
                time.sleep(30)
                continue
            resp.raise_for_status()
            if "image" not in resp.headers.get("content-type", ""):
                continue
            img = Image.open(BytesIO(resp.content)).convert("RGB").resize((W, H), Image.LANCZOS)
            return np.array(img)
        except Exception as e:
            logging.warning(f"Pollinations fallback fallido (seed={seed}): {e}")
    return None


def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _speed_audio(input_path, output_path, speed=AUDIO_SPEED):
    subprocess.run(
        [_get_ffmpeg(), "-y", "-i", str(input_path), "-filter:a", f"atempo={speed}", str(output_path)],
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

    img_prompt = mystery.get("img_prompt", title)

    # Generar 3 prompts visuales distintos (inicio, medio, final del script)
    n = len(chunks)
    sample_idx = [0, n // 2, n - 1]
    hf_prompts = list(dict.fromkeys([_chunk_to_prompt(img_prompt, chunks[i]) for i in sample_idx]))

    # Intentar HuggingFace primero
    hf_clips = None
    if HF_TOKEN:
        hf_clips = _generate_hf_videos(hf_prompts, HF_TOKEN, output_dir)

    clips = []
    for i, chunk in enumerate(chunks):
        progress = (i + 1) / len(chunks)
        if hf_clips:
            bg_clip = hf_clips[i % len(hf_clips)]
            if bg_clip:
                clip = _make_video_clip(bg_clip, title, chunk, progress, chunk_dur)
                clip = clip.with_start(i * chunk_dur)
                clips.append(clip)
                continue
        # Fallback: Pollinations + Ken Burns
        bg_img = _fetch_pollinations_image(_chunk_to_prompt(img_prompt, chunk))
        if bg_img is None:
            bg_img = _fallback_bg()
        clip = _make_animated_clip(bg_img, title, chunk, progress, chunk_dur)
        clip = clip.with_start(i * chunk_dur)
        clips.append(clip)

    video = CompositeVideoClip(clips, size=(W, H)).with_audio(audio)
    video.write_videofile(str(video_path), fps=FPS, codec="libx264", audio_codec="aac", logger=None)

    audio.close()
    audio_path.unlink(missing_ok=True)
    if hf_clips:
        for c in hf_clips:
            if c:
                c.close()
        for f in output_dir.glob("hf_*.mp4"):
            f.unlink(missing_ok=True)

    return video_path
