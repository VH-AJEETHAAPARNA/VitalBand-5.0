"""
VitalBand Voice Alert Audio (/api/voice/...)
============================================
Serves pre-rendered gTTS audio for spoken alerts in Tamil, Hindi, Kannada
and English.

Why this exists: the browser's built-in speechSynthesis can only speak a
language if the operating system has a voice pack installed for it, and
Indian-language packs are absent on most Windows machines. Rather than let
Tamil silently fail, the dashboard falls back to this endpoint, which streams
real audio the project already generated.

Cache-first by design: every clip is read from voice/cache/ and only
regenerated through gTTS when a file is genuinely missing. A demo therefore
needs no internet, because the cache is committed with the project.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

logger = logging.getLogger("vitalband.voice")

router = APIRouter(tags=["Voice"])

# backend/routers/voice.py -> backend/routers -> backend -> project root
VOICE_DIR = Path(__file__).resolve().parents[2] / "voice"
CACHE_DIR = VOICE_DIR / "cache"

SUPPORTED_LANGS = {"ta", "hi", "kn", "en"}
SUPPORTED_EVENTS = {"FALL", "SOS", "DISTRESS", "ABNORMAL_VITALS", "ALL_CLEAR"}

# Maps the dashboard's event names onto the five cached clips.
EVENT_ALIASES = {
    "FALL (CAMERA)": "FALL",
    "FALL_CAMERA": "FALL",
    "DISTRESS (CAMERA)": "DISTRESS",
    "DISTRESS_CAMERA": "DISTRESS",
    "ABNORMAL VITALS": "ABNORMAL_VITALS",
    "VITALS": "ABNORMAL_VITALS",
    "ALERT": "ABNORMAL_VITALS",
}


def _normalise_event(event_type: str) -> str:
    key = (event_type or "").strip().upper()
    key = EVENT_ALIASES.get(key, key)
    if key in SUPPORTED_EVENTS:
        return key
    # Substring match so "FALL (camera)" and similar variants still resolve.
    for known in SUPPORTED_EVENTS:
        if known in key:
            return known
    return "ABNORMAL_VITALS"


def _generate_if_missing(event_type: str, lang: str) -> Path | None:
    path = CACHE_DIR / f"{event_type}_{lang}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path

    # Only reached when the cache is incomplete; needs internet once.
    try:
        from gtts import gTTS
    except ImportError:
        logger.warning("gTTS not installed and %s is not cached", path.name)
        return None

    try:
        import sys
        sys.path.insert(0, str(VOICE_DIR))
        from voice_alerts import MESSAGES  # type: ignore

        text = MESSAGES.get(event_type, {}).get(lang)
        if not text:
            return None

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        gTTS(text=text, lang=lang).save(str(path))
        logger.info("Generated missing voice clip %s", path.name)
        return path
    except Exception as e:
        logger.warning("Could not generate %s: %s", path.name, e)
        return None


@router.get("/voice/status")
async def voice_status():
    """Which clips are available offline — lets the UI show honest capability."""
    available: dict[str, list[str]] = {}
    for lang in sorted(SUPPORTED_LANGS):
        clips = [
            ev for ev in sorted(SUPPORTED_EVENTS)
            if (CACHE_DIR / f"{ev}_{lang}.mp3").exists()
        ]
        available[lang] = clips

    return {
        "cache_dir": str(CACHE_DIR),
        "languages": available,
        "fully_cached": [
            lang for lang, clips in available.items()
            if len(clips) == len(SUPPORTED_EVENTS)
        ],
    }


@router.get("/voice/{event_type}/{lang}")
async def get_voice_clip(event_type: str, lang: str):
    """Stream the cached MP3 for this event in this language."""
    lang = (lang or "").lower()
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{lang}'. Supported: {sorted(SUPPORTED_LANGS)}",
        )

    event_key = _normalise_event(event_type)
    path = _generate_if_missing(event_key, lang)

    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audio available for {event_key} in '{lang}'.",
        )

    return FileResponse(
        path,
        media_type="audio/mpeg",
        # Clips are immutable once generated, so let the browser keep them.
        headers={"Cache-Control": "public, max-age=86400"},
        filename=path.name,
    )
