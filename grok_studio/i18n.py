"""Tiny dictionary-based EN/KH translator.

Usage:  from grok_studio.i18n import tr
        tr("chat.send")  ->  current-language string

Default language is Khmer. Widgets implement `retranslate_ui()` and the main
window calls it on every tab when the language changes in Settings.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "kh"

_current = DEFAULT_LANGUAGE


def set_language(lang: str) -> None:
    global _current
    _current = "kh" if lang not in ("en", "kh") else lang


def current_language() -> str:
    return _current


def tr(key: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(_current) or entry.get("en") or key


_STRINGS: dict[str, dict[str, str]] = {
    # ---- generic -----------------------------------------------------------
    "app.title": {"en": "Grok Studio", "kh": "Grok Studio"},
    "generic.generate": {"en": "Generate", "kh": "បង្កើត"},
    "generic.cancel": {"en": "Cancel", "kh": "បោះបង់"},
    "generic.save": {"en": "Save", "kh": "រក្សាទុក"},
    "generic.save_as": {"en": "Save As…", "kh": "រក្សាទុកជា…"},
    "generic.copy": {"en": "Copy", "kh": "ចម្លង"},
    "generic.copied": {"en": "Copied!", "kh": "បានចម្លង!"},
    "generic.error": {"en": "Error", "kh": "កំហុស"},
    "generic.done": {"en": "Done", "kh": "រួចរាល់"},
    "generic.failed": {"en": "Failed", "kh": "បរាជ័យ"},
    "generic.expired": {"en": "Expired", "kh": "ផុតកំណត់"},
    "generic.queued": {"en": "Queued", "kh": "កំពុងរង់ចាំ"},
    "generic.rendering": {"en": "Rendering", "kh": "កំពុងបង្កើត"},
    "generic.saved_to": {"en": "Saved to", "kh": "បានរក្សាទុកនៅ"},
    "generic.retry_in": {"en": "Rate limited — retrying in {s}s…",
                         "kh": "លើសកំណត់ — ព្យាយាមម្ដងទៀតក្នុង {s} វិនាទី…"},
    "generic.no_api_key": {"en": "Add your xAI API key in Settings first.",
                           "kh": "សូមបញ្ចូល xAI API key នៅក្នុងការកំណត់ជាមុនសិន។"},
    "generic.network_error": {"en": "Network error", "kh": "បញ្ហាបណ្ដាញ"},
    "generic.moderation": {"en": "Request was rejected by moderation.",
                           "kh": "សំណើត្រូវបានបដិសេធដោយប្រព័ន្ធត្រួតពិនិត្យ។"},

    # ---- sidebar -----------------------------------------------------------
    "tab.chat": {"en": "Chat", "kh": "ជជែក"},
    "tab.image": {"en": "Image", "kh": "រូបភាព"},
    "tab.video": {"en": "Video", "kh": "វីដេអូ"},
    "tab.voice": {"en": "Voice", "kh": "សំឡេង"},
    "tab.settings": {"en": "Settings", "kh": "ការកំណត់"},

    # ---- chat --------------------------------------------------------------
    "chat.placeholder": {"en": "Message Grok…", "kh": "សរសេរសារទៅ Grok…"},
    "chat.send": {"en": "Send", "kh": "ផ្ញើ"},
    "chat.system_prompt": {"en": "System prompt", "kh": "System prompt"},
    "chat.system_placeholder": {
        "en": "Optional system prompt for this session…",
        "kh": "System prompt ស្រេចចិត្តសម្រាប់វគ្គនេះ…",
    },
    "chat.thinking": {"en": "Grok is typing…", "kh": "Grok កំពុងសរសេរ…"},
    "chat.clear": {"en": "Clear chat", "kh": "សម្អាតការជជែក"},

    # ---- image -------------------------------------------------------------
    "image.prompt_placeholder": {
        "en": "Describe the image you want…",
        "kh": "ពិពណ៌នារូបភាពដែលអ្នកចង់បាន…",
    },
    "image.model": {"en": "Model", "kh": "ម៉ូដែល"},
    "image.aspect": {"en": "Aspect ratio", "kh": "សមាមាត្រ"},
    "image.resolution": {"en": "Resolution", "kh": "គុណភាព"},
    "image.count": {"en": "Images", "kh": "ចំនួនរូប"},
    "image.estimate": {"en": "Est. cost", "kh": "តម្លៃប៉ាន់ស្មាន"},
    "image.send_to_video": {"en": "Send to Video", "kh": "បញ្ជូនទៅវីដេអូ"},
    "image.generating": {"en": "Generating images…", "kh": "កំពុងបង្កើតរូបភាព…"},

    # ---- video -------------------------------------------------------------
    "video.prompt_placeholder": {
        "en": "Describe the video you want…",
        "kh": "ពិពណ៌នាវីដេអូដែលអ្នកចង់បាន…",
    },
    "video.reference": {"en": "Reference images (drag & drop, up to 7)",
                        "kh": "រូបភាពយោង (អូសដាក់ រហូតដល់ ៧)"},
    "video.duration": {"en": "Duration", "kh": "រយៈពេល"},
    "video.seconds": {"en": "s", "kh": "វិ."},
    "video.estimate": {"en": "Est. cost", "kh": "តម្លៃប៉ាន់ស្មាន"},
    "video.download": {"en": "Download video", "kh": "ទាញយកវីដេអូ"},
    "video.cancel_tooltip": {
        "en": "Stops polling. The job may still complete on the server and be billed.",
        "kh": "បញ្ឈប់ការតាមដាន។ ការងារអាចនៅតែបញ្ចប់នៅលើម៉ាស៊ីនមេ ហើយអាចត្រូវគិតថ្លៃ។",
    },
    "video.elapsed": {"en": "elapsed", "kh": "កន្លងផុត"},
    "video.remaining": {"en": "est. remaining", "kh": "នៅសល់ប្រហែល"},
    "video.clear_refs": {"en": "Clear", "kh": "សម្អាត"},

    # ---- voice -------------------------------------------------------------
    "voice.placeholder": {"en": "Type text to speak…", "kh": "វាយអត្ថបទដើម្បីបំលែងជាសំឡេង…"},
    "voice.voice": {"en": "Voice", "kh": "សំឡេង"},
    "voice.language": {"en": "Language", "kh": "ភាសា"},
    "voice.chars": {"en": "characters", "kh": "តួអក្សរ"},
    "voice.play": {"en": "Play", "kh": "ចាក់"},
    "voice.pause": {"en": "Pause", "kh": "ផ្អាក"},

    # ---- settings ----------------------------------------------------------
    "settings.title": {"en": "Settings", "kh": "ការកំណត់"},
    "settings.api_key": {"en": "xAI API key", "kh": "xAI API key"},
    "settings.api_key_placeholder": {"en": "xai-…", "kh": "xai-…"},
    "settings.test": {"en": "Test Connection", "kh": "សាកល្បងការតភ្ជាប់"},
    "settings.testing": {"en": "Testing…", "kh": "កំពុងសាកល្បង…"},
    "settings.test_ok": {"en": "Key is valid — saved securely.",
                         "kh": "Key ត្រឹមត្រូវ — បានរក្សាទុកដោយសុវត្ថិភាព។"},
    "settings.test_fail": {"en": "Key validation failed", "kh": "ការផ្ទៀងផ្ទាត់ Key បរាជ័យ"},
    "settings.key_stored": {"en": "A key is stored in Windows Credential Manager.",
                            "kh": "Key ត្រូវបានរក្សាទុកក្នុង Windows Credential Manager។"},
    "settings.key_missing": {"en": "No API key stored yet.",
                             "kh": "មិនទាន់មាន API key ត្រូវបានរក្សាទុកទេ។"},
    "settings.key_required_banner": {
        "en": "Add and validate your xAI API key to unlock the app.",
        "kh": "បញ្ចូល និងផ្ទៀងផ្ទាត់ xAI API key របស់អ្នក ដើម្បីប្រើកម្មវិធី។",
    },
    "settings.language": {"en": "Language / ភាសា", "kh": "ភាសា / Language"},
    "settings.lang_en": {"en": "English", "kh": "English"},
    "settings.lang_kh": {"en": "ខ្មែរ (Khmer)", "kh": "ខ្មែរ"},
    "settings.default_image_ratio": {"en": "Default image ratio", "kh": "សមាមាត្ររូបភាពលំនាំដើម"},
    "settings.default_video_ratio": {"en": "Default video ratio", "kh": "សមាមាត្រវីដេអូលំនាំដើម"},
    "settings.output_folder": {"en": "Output folder", "kh": "ថតរក្សាទុក"},
    "settings.browse": {"en": "Browse…", "kh": "រកមើល…"},
    "settings.clear_cache": {"en": "Clear cache", "kh": "សម្អាតឃ្លាំងសម្ងាត់"},
    "settings.reset_app": {"en": "Reset app", "kh": "កំណត់កម្មវិធីឡើងវិញ"},
    "settings.reset_confirm": {
        "en": "Reset all settings and remove the stored API key?",
        "kh": "កំណត់ការកំណត់ទាំងអស់ឡើងវិញ និងលុប API key ដែលបានរក្សាទុក?",
    },
    "settings.cache_cleared": {"en": "Cache cleared.", "kh": "បានសម្អាតឃ្លាំងសម្ងាត់។"},
    "settings.reset_done": {"en": "App reset. Restart to apply.",
                            "kh": "បានកំណត់ឡើងវិញ។ សូមបើកកម្មវិធីម្ដងទៀត។"},
}
