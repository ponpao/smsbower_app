"""
tag_editor.py — Local metadata writing via mutagen.

Writes accurate, user-supplied tags (and an optional cover image) to audio
files the user owns. It intentionally does NOT strip provenance, forge a DAW
"software encoder" to disguise a track's origin, or "bypass" any AI-detection
system. It is an ordinary tag editor: whatever the user types is what gets
written.

Supported containers: MP3 (ID3), FLAC, MP4/M4A. WAV tagging support in mutagen
is limited, so WAV files get an INFO/ID3 best-effort and a clear note otherwise.
"""

from __future__ import annotations

import os

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import (
        ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, TCON, TENC,
        TCOP, COMM, APIC,
    )
    from mutagen.flac import FLAC, Picture
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.wave import WAVE
    _HAVE_MUTAGEN = True
except Exception:  # noqa: BLE001
    _HAVE_MUTAGEN = False


def _require():
    if not _HAVE_MUTAGEN:
        raise RuntimeError(
            "Metadata writing needs mutagen. Install with: pip install mutagen"
        )


def _clean_title(title, options):
    if not title:
        return title
    if options.get("remove_track_numbers"):
        # Strip a leading "01 - ", "1. ", "12) " style prefix.
        import re
        title = re.sub(r"^\s*\d+\s*[-.)]\s*", "", title)
    if options.get("force_uppercase"):
        title = title.upper()
    return title


def _load_cover(cover_path):
    with open(cover_path, "rb") as fh:
        data = fh.read()
    ext = os.path.splitext(cover_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    return data, mime


def write_tags(path, tags, cover_path=None, options=None):
    """Write tags to a single file. Returns a short status detail string."""
    _require()
    options = options or {}
    ext = os.path.splitext(path)[1].lower()

    # Title cleanup applies to whatever title we end up writing. If no explicit
    # title tag was provided, derive a display title from the filename.
    title = tags.get("title")
    if title is None:
        title = os.path.splitext(os.path.basename(path))[0]
    title = _clean_title(title, options)

    if ext in (".mp3", ".wav"):
        return _write_id3(path, tags, title, cover_path, ext)
    if ext == ".flac":
        return _write_flac(path, tags, title, cover_path)
    if ext in (".m4a", ".mp4", ".aac"):
        return _write_mp4(path, tags, title, cover_path)

    # Fallback: let mutagen sniff it; write common keys if it supports mapping.
    audio = MutagenFile(path, easy=True)
    if audio is None:
        raise RuntimeError(f"Unsupported file type: {ext or 'unknown'}")
    _easy_set(audio, tags, title)
    audio.save()
    return "tags written (generic)"


def _easy_set(audio, tags, title):
    mapping = {
        "artist": "artist", "album": "album", "genre": "genre",
        "date": "date", "title": "title",
    }
    if title:
        audio["title"] = title
    for key, easykey in mapping.items():
        if key == "title":
            continue
        val = tags.get(key)
        if val:
            audio[easykey] = str(val)


def _write_id3(path, tags, title, cover_path, ext):
    """ID3-based tagging. MP3 uses a raw ID3 tag; WAV embeds ID3 via WAVE."""
    if ext == ".wav":
        audio = WAVE(path)
        if audio.tags is None:
            audio.add_tags()
        id3 = audio.tags
    else:
        try:
            id3 = ID3(path)
        except ID3NoHeaderError:
            id3 = ID3()
        audio = None

    if title:
        id3.setall("TIT2", [TIT2(encoding=3, text=title)])
    _set_frame(id3, "TPE1", TPE1, tags.get("artist"))
    _set_frame(id3, "TALB", TALB, tags.get("album"))
    _set_frame(id3, "TDRC", TDRC, tags.get("date"))
    _set_frame(id3, "TCON", TCON, tags.get("genre"))
    _set_frame(id3, "TENC", TENC, tags.get("encoder"))
    _set_frame(id3, "TCOP", TCOP, tags.get("copyright"))
    if tags.get("comment"):
        id3.setall("COMM", [COMM(encoding=3, lang="eng", desc="",
                                 text=tags["comment"])])
    if cover_path and os.path.exists(cover_path):
        data, mime = _load_cover(cover_path)
        id3.delall("APIC")
        id3.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data))

    if audio is not None:
        audio.save()
    else:
        id3.save(path)
    return "ID3 tags written" + (" + cover" if cover_path else "")


def _set_frame(id3, key, frame_cls, value):
    if value:
        id3.setall(key, [frame_cls(encoding=3, text=str(value))])


def _write_flac(path, tags, title, cover_path):
    audio = FLAC(path)
    if title:
        audio["title"] = title
    for key, tagkey in (("artist", "artist"), ("album", "album"),
                        ("genre", "genre"), ("date", "date"),
                        ("copyright", "copyright"), ("comment", "comment"),
                        ("encoder", "encodedby")):
        val = tags.get(key)
        if val:
            audio[tagkey] = str(val)
    if cover_path and os.path.exists(cover_path):
        data, mime = _load_cover(cover_path)
        pic = Picture()
        pic.type = 3
        pic.mime = mime
        pic.data = data
        audio.clear_pictures()
        audio.add_picture(pic)
    audio.save()
    return "FLAC tags written" + (" + cover" if cover_path else "")


def _write_mp4(path, tags, title, cover_path):
    audio = MP4(path)
    if title:
        audio["\xa9nam"] = [title]
    for key, atom in (("artist", "\xa9ART"), ("album", "\xa9alb"),
                      ("genre", "\xa9gen"), ("date", "\xa9day"),
                      ("comment", "\xa9cmt"), ("encoder", "\xa9too"),
                      ("copyright", "cprt")):
        val = tags.get(key)
        if val:
            audio[atom] = [str(val)]
    if cover_path and os.path.exists(cover_path):
        data, mime = _load_cover(cover_path)
        fmt = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(data, imageformat=fmt)]
    audio.save()
    return "MP4 tags written" + (" + cover" if cover_path else "")
