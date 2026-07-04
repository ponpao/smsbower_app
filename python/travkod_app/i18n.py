"""Lightweight i18n for TRAVKOD: English / Khmer (ខ្មែរ).

Usage:
    from .i18n import tr, I18N, set_lang
    label.setText(tr("btn.files"))
    I18N.changed.connect(self._retranslate)   # rebuild text on language switch

Khmer text renders in **Kantumruy Pro**, bundled under resources/fonts and
registered by ``load_fonts()``. Latin text also renders fine in that font, so in
Khmer mode the whole UI uses it.
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFontDatabase

KH_FONT = "Kantumruy Pro"
EN_FONT_STACK = "'Inter','Segoe UI','Noto Sans',sans-serif"
_FONT_FILE = "KantumruyPro-VariableFont_wght.ttf"


def _font_dirs():
    """Candidate resources/fonts locations for dev runs and PyInstaller bundles."""
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        # repo root: <root>/resources/fonts  (i18n.py is python/travkod_app/i18n.py)
        os.path.join(os.path.dirname(os.path.dirname(here)), "resources", "fonts"),
    ]
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller unpack dir
    if base:
        dirs.append(os.path.join(base, "resources", "fonts"))
    return dirs


def load_fonts() -> None:
    """Register bundled fonts (Kantumruy Pro). Safe to call once at startup."""
    for d in _font_dirs():
        path = os.path.join(d, _FONT_FILE)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
            return


def font_stack(lang: str) -> str:
    """CSS font-family stack for the given language."""
    if lang == "kh":
        return f"'{KH_FONT}','Noto Sans',sans-serif"
    return EN_FONT_STACK


# key -> (en, kh)
STRINGS = {
    "app.subtitle": ("honest master & humanize", "ធ្វើ master ដោយស្មោះត្រង់"),
    "lang.name": ("EN", "ខ្មែរ"),

    # Batch queue
    "queue.title": ("BATCH QUEUE", "ជួរដំណើរការ"),
    "btn.files": ("+ Files", "+ ឯកសារ"),
    "btn.folder": ("+ Folder", "+ ថត"),
    "btn.startExport": ("Start Export", "ចាប់ផ្តើមនាំចេញ"),
    "btn.stop": ("Stop", "បញ្ឈប់"),
    "col.no": ("No", "ល.រ"),
    "col.filename": ("Filename", "ឈ្មោះឯកសារ"),
    "col.duration": ("Duration", "រយៈពេល"),
    "col.type": ("Type", "ប្រភេទ"),
    "col.key": ("Key/Major", "តូន/មេ"),
    "col.samplerate": ("Sample Rate / Bits", "អត្រា / Bits"),
    "col.loudness": ("Loudness", "កម្រិតសំឡេង"),
    "col.truepeak": ("True Peak", "True Peak"),
    "col.channels": ("Channels", "ឆានែល"),
    "col.status": ("Status", "ស្ថានភាព"),
    "empty.hint": ("Drop audio here, or use “+ Files” / “+ Folder”. Right-click for the menu.",
                   "ទម្លាក់ឯកសារសំឡេងនៅទីនេះ ឬប្រើ “+ ឯកសារ” / “+ ថត”។ ចុចស្តាំដើម្បីបើកម៉ឺនុយ។"),

    # Statuses
    "status.Idle": ("Idle", "ទំនេរ"),
    "status.Queued": ("Queued", "រង់ចាំ"),
    "status.Processing": ("Processing", "កំពុងដំណើរការ"),
    "status.Done": ("Done", "រួចរាល់"),
    "status.Error": ("Error", "កំហុស"),
    "status.Paused": ("Paused", "ផ្អាក"),

    # Context menu
    "menu.selectAll": ("Select all", "ជ្រើសទាំងអស់"),
    "menu.addFiles": ("Add files…", "បញ្ចូលឯកសារ…"),
    "menu.addFolder": ("Add folder…", "បញ្ចូលថត…"),
    "menu.remove": ("Remove selected", "លុបដែលបានជ្រើស"),
    "menu.clear": ("Clear all", "សម្អាតទាំងអស់"),
    "menu.analyze": ("Analyze file", "វិភាគឯកសារ"),
    "menu.startExport": ("Start export", "ចាប់ផ្តើមនាំចេញ"),
    "menu.stopExport": ("Stop export", "បញ្ឈប់ការនាំចេញ"),
    "menu.openOutput": ("Open output folder", "បើកថតលទ្ធផល"),

    # Console
    "console.template": ("Template", "ទម្រង់"),
    "console.presets": ("Presets", "ការកំណត់"),
    "console.quickEq": ("Quick EQ", "EQ រហ័ស"),
    "console.masteringStrip": ("MASTERING STRIP", "ម៉ាស្ទ័រ"),
    "console.humanize": ("Humanize", "ធ្វើឲ្យធម្មជាតិ"),
    "console.eq": ("EQ · 10-BAND", "EQ · ១០ ក្រុម"),
    "console.humanizeMaster": ("Humanize & Master", "Humanize & Master"),
    "console.auto": ("Auto", "ស្វ័យ"),
    "console.manual": ("Manual", "ដោយដៃ"),
    "console.analyzeAi": ("☆ Analyze AI", "☆ វិភាគ AI"),
    "console.export": ("Export…", "នាំចេញ…"),
    "console.savePreset": ("＋ Save current…", "＋ រក្សាទុកបច្ចុប្បន្ន…"),
    "console.noPresets": ("No saved presets", "គ្មានការកំណត់ដែលបានរក្សាទុក"),
    "console.presetName": ("Preset name:", "ឈ្មោះការកំណត់៖"),
    "console.savePresetTitle": ("Save preset", "រក្សាទុកការកំណត់"),

    # Transport
    "transport.effect": ("Effect", "បែបផែន"),
    "transport.processed": ("Processed", "កែច្នៃ"),
    "transport.original": ("Original", "ដើម"),
    "transport.releaseCheck": ("Release Check", "ត្រួតពិនិត្យការចេញផ្សាយ"),
    "transport.noAudio": ("Audio playback unavailable on this system",
                          "ការចាក់សំឡេងមិនអាចប្រើបានលើប្រព័ន្ធនេះ"),

    # Status bar
    "sbar.status": ("Status:", "ស្ថានភាព៖"),
    "sbar.idle": ("Idle", "ទំនេរ"),
    "sbar.ready": ("Ready", "រួចរាល់"),
    "sbar.processing": ("Processing", "កំពុងដំណើរការ"),
    "sbar.queue": ("Queue:", "ជួរ៖"),
    "sbar.local": ("All processing runs locally", "ដំណើរការទាំងអស់នៅលើម៉ាស៊ីនរបស់អ្នក"),

    # Export dialog
    "exp.title": ("Export Settings", "ការកំណត់នាំចេញ"),
    "exp.format": ("Format", "ទ្រង់ទ្រាយ"),
    "exp.sampleRate": ("Sample rate", "អត្រាគំរូ"),
    "exp.keepSource": ("Keep source", "រក្សាដើម"),
    "exp.bitDepth": ("Bit depth", "ជម្រៅ Bit"),
    "exp.mp3Bitrate": ("MP3 bitrate (kbps)", "អត្រា MP3 (kbps)"),
    "exp.threads": ("Threads", "ខ្សែស្រឡាយ"),
    "exp.threadsHint": ("Parallel worker threads (1–8)", "ខ្សែស្រឡាយស្របគ្នា (១–៨)"),
    "exp.lufs": ("Mastering target (LUFS)", "គោលដៅ (LUFS)"),
    "exp.lufsOff": ("Off", "បិទ"),
    "exp.lufsStream": ("-14 (streaming)", "-14 (streaming)"),
    "exp.lufsLoud": ("-9 (loud)", "-9 (ខ្លាំង)"),
    "exp.lufsCustom": ("Custom", "ផ្ទាល់ខ្លួន"),
    "exp.customLufs": ("Custom LUFS", "LUFS ផ្ទាល់ខ្លួន"),
    "exp.autotune": ("Autotune (vocal)", "Autotune (សំឡេង)"),
    "exp.autotuneHint": ("Gentle correction, off by default", "កែតម្រូវ​ស្រាល បិទតាមលំនាំដើម"),
    "exp.merge": ("Merge → one file", "បញ្ចូល → ឯកសារតែមួយ"),
    "exp.mergeHint": ("Concatenate the batch into one export", "ភ្ជាប់ទាំងអស់ជាឯកសារតែមួយ"),
    "exp.outFolder": ("Output folder", "ថតលទ្ធផល"),
    "exp.choose": ("Choose…", "ជ្រើស…"),
    "exp.close": ("Close", "បិទ"),
    "exp.start": ("Start Export", "ចាប់ផ្តើមនាំចេញ"),

    # Release dialog
    "rel.title": ("Release Readiness Check", "ត្រួតពិនិត្យការត្រៀមចេញផ្សាយ"),
    "rel.selectFirst": ("Select and analyze a track first.", "សូមជ្រើស និងវិភាគបទជាមុនសិន។"),
    "rel.note": ("This checklist reports objective facts about your master. It never tells "
                 "you how to “pass” a distributor check. Where a release requires AI "
                 "disclosure, disclose it.",
                 "បញ្ជីនេះរាយការណ៍ការពិតអំពី master របស់អ្នក។ វាមិនប្រាប់អ្នកពីរបៀប “ឆ្លងកាត់” "
                 "ការត្រួតពិនិត្យរបស់អ្នកចែកចាយឡើយ។ ពេលការចេញផ្សាយត្រូវការបង្ហាញ AI សូមបង្ហាញវា។"),
    "rel.close": ("Close", "បិទ"),

    # Authenticity dialog
    "auth.title": ("Authenticity Report", "របាយការណ៍ភាពពិត"),
    "auth.beta": ("BETA — experimental, may be wrong", "សាកល្បង — អាចខុស"),
    "auth.caption": ("Estimated probability this track is AI-generated",
                     "ប្រូបាប៊ីលីតេប៉ាន់ស្មានថាបទនេះបង្កើតដោយ AI"),
    "auth.range": ("range", "ចន្លោះ"),
    "auth.human": ("0% (human)", "0% (មនុស្ស)"),
    "auth.ai": ("100% (AI)", "100% (AI)"),
    "auth.markQ": ("Mark this source as AI-generated?", "សម្គាល់ប្រភពនេះថាបង្កើតដោយ AI?"),
    "auth.marked": ("Marked AI ✓", "បានសម្គាល់ AI ✓"),
    "auth.mark": ("Mark as AI", "សម្គាល់ជា AI"),
    "auth.markHint": ("Marking a source AI-generated turns on the disclosure reminder in the "
                      "Release Check — so you disclose where your distributor requires it.",
                      "ការសម្គាល់ថាបង្កើតដោយ AI នឹងបើកការរំលឹកឲ្យបង្ហាញ នៅក្នុងការត្រួតពិនិត្យ "
                      "ការចេញផ្សាយ — ដើម្បីឲ្យអ្នកបង្ហាញនៅកន្លែងដែលអ្នកចែកចាយត្រូវការ។"),
    "auth.close": ("Close", "បិទ"),
    "auth.selectFirst": ("Select a track first.", "សូមជ្រើសបទជាមុនសិន។"),

    # First-run notice
    "fr.title": ("Welcome to TRAVKOD", "សូមស្វាគមន៍មកកាន់ TRAVKOD"),
    "fr.p1": ("TRAVKOD improves audio quality — it makes finished tracks warmer, less "
              "brittle and release-ready, then batch-exports them.",
              "TRAVKOD បង្កើនគុណភាពសំឡេង — ធ្វើឲ្យបទកក់ក្តៅ ស្រួលស្តាប់ និងត្រៀមចេញផ្សាយ "
              "រួចនាំចេញជាបាច់។"),
    "fr.p2": ("If your track uses AI, disclose it where your distributor requires. TRAVKOD "
              "does not help you hide AI use or defeat any detection — the Authenticity "
              "Report is an experimental, informational estimate only.",
              "បើបទរបស់អ្នកប្រើ AI សូមបង្ហាញវានៅកន្លែងដែលអ្នកចែកចាយត្រូវការ។ TRAVKOD មិនជួយ "
              "អ្នកលាក់ការប្រើ AI ឬបំបាត់ការរកឃើញឡើយ — របាយការណ៍ភាពពិតគ្រាន់តែជាការប៉ាន់ស្មាន។"),
    "fr.p3": ("All processing runs locally on your machine by default. Nothing is uploaded.",
              "ដំណើរការទាំងអស់ធ្វើនៅលើម៉ាស៊ីនរបស់អ្នក។ គ្មានអ្វីត្រូវបានផ្ទុកឡើងទេ។"),
    "fr.ok": ("Got it", "យល់ព្រម"),
}


class _I18N(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.lang = "en"

    def set_lang(self, lang: str):
        if lang not in ("en", "kh") or lang == self.lang:
            return
        self.lang = lang
        self.changed.emit()

    def toggle(self):
        self.set_lang("kh" if self.lang == "en" else "en")


I18N = _I18N()


def tr(key: str) -> str:
    en, kh = STRINGS.get(key, (key, key))
    return kh if I18N.lang == "kh" else en


def set_lang(lang: str):
    I18N.set_lang(lang)
