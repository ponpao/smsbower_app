"""Shared constants: colors, models, prices and the two aspect-ratio lists.

IMPORTANT: image and video aspect-ratio lists are intentionally SEPARATE.
The video endpoint accepts only a subset of the image ratios; reusing the
image list in the video dropdown causes HTTP 400 on roughly half the options.
"""

# ---------------------------------------------------------------- visual ----
COLOR_BG = "#0F0F14"
COLOR_BG_ELEVATED = "#17171F"
COLOR_BG_INPUT = "#1C1C26"
COLOR_ACCENT = "#7C5CFF"
COLOR_ACCENT_HOVER = "#8F73FF"
COLOR_ACCENT_PRESSED = "#6A4BE8"
COLOR_TEXT = "#F2F2F5"
COLOR_TEXT_SECONDARY = "#9A9AA5"
COLOR_BORDER = "#2A2A36"
COLOR_ERROR = "#FF5C6C"
COLOR_SUCCESS = "#4CD97B"
COLOR_WARNING = "#FFB84C"

WINDOW_WIDTH = 420
WINDOW_HEIGHT = 720
SHADOW_MARGIN = 8          # transparent margin around the card for the shadow
CORNER_RADIUS = 12
SIDEBAR_WIDTH = 56
TAB_TRANSITION_MS = 150

FONT_FAMILY_PRIMARY = "Kantumruy Pro"
FONT_FAMILY_FALLBACK = "Segoe UI"

# ------------------------------------------------------------------- api ----
XAI_BASE_URL = "https://api.x.ai/v1"

CHAT_MODEL = "grok-4.3"

IMAGE_MODELS = {
    # model id -> {label, prices per image keyed by resolution}
    "grok-imagine-image": {"prices": {"1k": 0.02}},
    "grok-imagine-image-quality": {"prices": {"1k": 0.05, "2k": 0.07}},
}

VIDEO_MODEL = "grok-imagine-video"
VIDEO_PRICE_PER_MINUTE = 4.20  # USD; estimate = seconds / 60 * 4.20
VIDEO_POLL_INTERVAL_S = 5
VIDEO_MAX_REFERENCE_IMAGES = 7
VIDEO_DURATION_MIN_S = 1
VIDEO_DURATION_MAX_S = 15

TTS_VOICES = ["eve", "ara", "rex", "leo", "sal", "gork"]
TTS_LANGUAGES = ["en", "km", "es", "fr", "de", "ja", "ko", "zh", "hi", "pt", "ru"]

# Valid for /images/generations ONLY — do not use for video.
IMAGE_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
    "2:1", "1:2", "19.5:9", "9:19.5", "20:9", "9:20", "auto",
]

# Valid for /videos/generations ONLY — a strict subset, keep separate.
VIDEO_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
]

VIDEO_RESOLUTIONS = ["480p", "720p"]
IMAGE_RESOLUTIONS = ["1k", "2k"]

MAX_IMAGE_BATCH = 4
