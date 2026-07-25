# -*- coding: utf-8 -*-
"""Bilingual Khmer / English labels.

Every user-facing string in the master UI goes through here. `t()` returns
the Khmer label with the English in parentheses, which is the convention the
existing TRAVKOD dialogs already use.
"""

STRINGS = {
    # window / chrome
    "app_title":     ("Pulse Rail Lyric Studio", "Pulse Rail Lyric Studio"),
    "app_sub":       ("ស្ទូឌីយោវីដេអូទំនុកច្រៀង", "Lyric video studio"),
    "minimize":      ("បង្រួម", "Minimize"),
    "maximize":      ("ពង្រីក", "Maximize"),
    "restore":       ("ត្រឡប់", "Restore"),
    "close":         ("បិទ", "Close"),

    # navigation
    "nav_workspace": ("កន្លែងធ្វើការ", "WORKSPACE"),
    "nav_output":    ("លទ្ធផល", "OUTPUT"),
    "nav_files":     ("ឯកសារ", "Files"),
    "nav_template":  ("ទម្រង់", "Template"),
    "nav_lyrics":    ("ទំនុកច្រៀង", "Lyrics"),
    "nav_export":    ("នាំចេញ", "Export"),

    # files page
    "files_title":   ("ឯកសារចូល", "Input files"),
    "drop_audio":    ("ទម្លាក់ឯកសារសំឡេង", "Drop audio here"),
    "drop_audio_h":  ("WAV · MP3 · FLAC · M4A", "WAV · MP3 · FLAC · M4A"),
    "drop_image":    ("ទម្លាក់រូបគម្រប", "Drop cover art here"),
    "drop_image_h":  ("PNG · JPG — យ៉ាងតិច ១៤៤០px", "PNG · JPG — 1440px or larger"),
    "browse":        ("រកមើល", "Browse"),
    "track_title":   ("ចំណងជើងបទ", "Track title"),
    "artist":        ("សិល្បករ", "Artist"),

    # template page
    "tpl_title":     ("ជ្រើសរើសទម្រង់", "Choose template"),
    "tpl_hint":      ("ទម្រង់នីមួយៗសម្រាប់ប្រភេទបទផ្សេងគ្នា",
                      "Each template targets a different music niche"),

    # lyrics page
    "lyr_title":     ("ទំនុកច្រៀង និងពេលវេលា", "Lyrics & timing"),
    "lyr_import":    ("នាំចូល LRC / SRT", "Import LRC / SRT"),
    "lyr_hint":      ("គាំទ្រ ខ្មែរ ថៃ កូរ៉េ ហិណ្ឌី តាមីល អង់គ្លេស",
                      "Khmer, Thai, Korean, Hindi, Tamil, English"),
    "lyr_cues":      ("ចំនួនបន្ទាត់", "Cues"),

    # export page
    "exp_title":     ("ការកំណត់នាំចេញ", "Export settings"),
    "resolution":    ("គុណភាព", "Resolution"),
    "fps":           ("Frame rate", "Frame rate"),
    "quality":       ("គុណភាពរូបភាព", "Quality"),
    "export_now":    ("នាំចេញឥឡូវ", "Export now"),
    "cancel":        ("បោះបង់", "Cancel"),

    # preview
    "preview":       ("មើលជាមុន", "Preview"),
    "play":          ("ចាក់", "Play"),
    "pause":         ("ផ្អាក", "Pause"),

    # status
    "ready":         ("រួចរាល់", "Ready"),
    "no_audio":      ("មិនទាន់មានសំឡេង", "No audio loaded"),
}


def t(key: str) -> str:
    """Khmer (English) — the bilingual label used on screen."""
    km, en = STRINGS.get(key, (key, key))
    return km if km == en else f"{km} ({en})"


def km(key: str) -> str:
    return STRINGS.get(key, (key, key))[0]


def en(key: str) -> str:
    return STRINGS.get(key, (key, key))[1]
