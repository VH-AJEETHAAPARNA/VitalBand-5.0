"""
Multi-Language Voice Alerts (Scan Machine speaker output)
=============================================================
Generates and plays spoken alerts in Tamil, Hindi, Kannada, and English
using gTTS (Google Text-to-Speech).

Requires internet the FIRST time each phrase is generated. After that,
generated .mp3 files are cached locally in voice/cache/ and reused
instantly -- no repeated internet calls during your actual demo.

Usage as a standalone test (no backend needed):
    python voice_alerts.py --test

Usage from other code:
    from voice_alerts import speak_alert
    speak_alert("FALL", patient_id="P001", lang="ta")
"""

import argparse
import threading
from pathlib import Path

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    from playsound import playsound
except ImportError:
    playsound = None

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MESSAGES = {
    "FALL": {
        "ta": "எச்சரிக்கை. ஒரு நோயாளி விழுந்துவிட்டார். உடனடி உதவி தேவை.",
        "hi": "चेतावनी। एक मरीज़ गिर गया है। तुरंत सहायता चाहिए।",
        "kn": "ಎಚ್ಚರಿಕೆ. ಒಬ್ಬ ರೋಗಿ ಬಿದ್ದಿದ್ದಾರೆ. ತಕ್ಷಣ ಸಹಾಯ ಬೇಕು.",
        "en": "Warning. A patient has fallen. Immediate help is needed.",
    },
    "SOS": {
        "ta": "எச்சரிக்கை. நோயாளி உதவி பொத்தானை அழுத்தியுள்ளார்.",
        "hi": "चेतावनी। मरीज़ ने सहायता बटन दबाया है।",
        "kn": "ಎಚ್ಚರಿಕೆ. ರೋಗಿ ಸಹಾಯ ಬಟನ್ ಒತ್ತಿದ್ದಾರೆ.",
        "en": "Warning. The patient has pressed the help button.",
    },
    "DISTRESS": {
        "ta": "நோயாளி சிரமப்படுவது போல் தெரிகிறது. தயவுசெய்து பரிசோதிக்கவும்.",
        "hi": "मरीज़ परेशान लग रहा है। कृपया जांच करें।",
        "kn": "ರೋಗಿ ತೊಂದರೆಯಲ್ಲಿ ಇರುವಂತೆ ಕಾಣಿಸುತ್ತಿದೆ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ.",
        "en": "The patient appears to be in distress. Please check on them.",
    },
    "ABNORMAL_VITALS": {
        "ta": "நோயாளியின் உடல்நல அளவீடுகள் இயல்பு நிலையில் இல்லை.",
        "hi": "मरीज़ के महत्वपूर्ण संकेत सामान्य नहीं हैं।",
        "kn": "ರೋಗಿಯ ಪ್ರಮುಖ ಚಿಹ್ನೆಗಳು ಸಾಮಾನ್ಯವಾಗಿಲ್ಲ.",
        "en": "The patient's vital signs are abnormal.",
    },
    "ALL_CLEAR": {
        "ta": "நீங்கள் நலமாக இருக்கிறீர்கள். கவலைப்பட வேண்டாம்.",
        "hi": "आप ठीक हैं। चिंता न करें।",
        "kn": "ನೀವು ಸುರಕ್ಷಿತವಾಗಿದ್ದೀರಿ. ಚಿಂತಿಸಬೇಡಿ.",
        "en": "You are fine. There is nothing to worry about.",
    },
}

LANGUAGE_NAMES = {"ta": "Tamil", "hi": "Hindi", "kn": "Kannada", "en": "English"}
DEFAULT_LANGUAGE = "ta"


def _cache_path(event_type, lang):
    return CACHE_DIR / f"{event_type}_{lang}.mp3"


def _generate_if_missing(event_type, lang):
    path = _cache_path(event_type, lang)
    if path.exists():
        return path

    if gTTS is None:
        print("gTTS not installed. Run: pip install gTTS playsound==1.2.2")
        return None

    text = MESSAGES.get(event_type, {}).get(lang)
    if not text:
        print(f"No message defined for event={event_type}, lang={lang}")
        return None

    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(str(path))
        return path
    except Exception as e:
        print(f"Could not generate speech (needs internet the first time): {e}")
        return None


def speak_alert(event_type, patient_id=None, lang=DEFAULT_LANGUAGE, blocking=False):
    def _play():
        path = _generate_if_missing(event_type, lang)
        if path is None:
            return
        if playsound is None:
            print("playsound not installed. Run: pip install playsound==1.2.2")
            print(f"(Would have played: {path})")
            return
        try:
            playsound(str(path))
        except Exception as e:
            print(f"Could not play audio: {e}")

    if blocking:
        _play()
    else:
        threading.Thread(target=_play, daemon=True).start()


def pregenerate_all():
    print("Pre-generating all voice alerts (needs internet)...\n")
    for event_type in MESSAGES:
        for lang in MESSAGES[event_type]:
            path = _generate_if_missing(event_type, lang)
            status = "OK" if path else "FAILED"
            print(f"  [{status}] {event_type} / {LANGUAGE_NAMES[lang]}")
    print(f"\nDone. Cached files are in {CACHE_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--pregenerate", action="store_true")
    parser.add_argument("--event", default="FALL", choices=list(MESSAGES.keys()))
    parser.add_argument("--lang", default=DEFAULT_LANGUAGE, choices=list(LANGUAGE_NAMES.keys()))
    args = parser.parse_args()

    if args.pregenerate:
        pregenerate_all()
    elif args.test:
        for lang in LANGUAGE_NAMES:
            print(f"Playing {args.event} alert in {LANGUAGE_NAMES[lang]}...")
            speak_alert(args.event, lang=lang, blocking=True)
    else:
        print(f"Playing {args.event} alert in {LANGUAGE_NAMES[args.lang]}...")
        speak_alert(args.event, lang=args.lang, blocking=True)