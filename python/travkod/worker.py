"""TRAVKOD Python DSP worker — newline-delimited JSON over stdio.

The Node orchestrator spawns a pool of these (one child process per "Thread").
Each process handles one request at a time and streams progress events for the
batch queue. All work is local; nothing leaves the machine.

Protocol (one JSON object per line):
  request  -> {"id": int, "method": str, "params": {...}}
  progress -> {"id": int, "event": "progress", "stage": str, "frac": float}
  response -> {"id": int, "result": {...}}
  error    -> {"id": int, "error": {"message": str}}

Methods: ping, analyze, authenticity, release_check, templates, process,
         merge_process.
"""
from __future__ import annotations

import json
import os
import sys
import traceback

import numpy as np

# Allow running both as a module (-m travkod.worker) and as a script.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from travkod import analyze as analyze_mod
    from travkod import authenticity as auth_mod
    from travkod import release as release_mod
    from travkod import io_export
    from travkod import humanize_master as engine
    from travkod.params import Params, FACTORY_TEMPLATES
else:
    from . import analyze as analyze_mod
    from . import authenticity as auth_mod
    from . import release as release_mod
    from . import io_export
    from . import humanize_master as engine
    from .params import Params, FACTORY_TEMPLATES

VERSION = "1.0.0"

_out = sys.stdout


def _send(obj) -> None:
    _out.write(json.dumps(obj) + "\n")
    _out.flush()


def _progress(req_id, stage, frac) -> None:
    _send({"id": req_id, "event": "progress", "stage": stage, "frac": round(frac, 4)})


def m_ping(_p, _id):
    return {"ok": True, "version": VERSION, "engine": "numpy/scipy",
            "pyloudnorm": engine._HAVE_PYLN}


def m_analyze(p, _id):
    return analyze_mod.analyze_file(p["path"])


def m_authenticity(p, _id):
    return auth_mod.analyze(p["path"])


def m_release_check(p, _id):
    return release_mod.check(
        p["meta"],
        lufs_target=p.get("lufs_target", -14.0),
        is_ai=p.get("is_ai", False),
        has_metadata=p.get("has_metadata", True),
    )


def m_templates(_p, _id):
    return {"templates": FACTORY_TEMPLATES}


def m_process(p, req_id):
    """Humanize + master a single file, then export."""
    audio, sr = io_export.read_audio(p["input"])
    params = Params.from_dict(p.get("params"))

    processed = engine.process(audio, sr, params,
                               progress=lambda s, f: _progress(req_id, s, f))

    exp = p.get("export", {})
    out_path = io_export.export(
        processed, sr, p["output"],
        fmt=exp.get("format", "wav"),
        bit_depth=int(exp.get("bit_depth", 24)),
        target_sr=exp.get("sample_rate"),
        mp3_bitrate=int(exp.get("mp3_bitrate", 320)),
    )

    lufs = engine.measure_lufs(processed, sr)
    tp = analyze_mod.true_peak_dbtp(processed, sr)
    _progress(req_id, "done", 1.0)
    return {
        "output_path": out_path,
        "metrics": {
            "loudness_lufs": None if lufs is None else round(lufs, 1),
            "true_peak_dbtp": tp,
            "sample_rate": exp.get("sample_rate") or sr,
        },
    }


def m_merge_process(p, req_id):
    """Merge > One File: concatenate inputs, process the whole, export once."""
    inputs = p["inputs"]
    clips = [io_export.read_audio(ip) for ip in inputs]
    base_sr = clips[0][1]
    merged = io_export.concat(clips, base_sr, gap_s=p.get("gap_s", 0.0))
    params = Params.from_dict(p.get("params"))
    processed = engine.process(merged, base_sr, params,
                               progress=lambda s, f: _progress(req_id, s, f))
    exp = p.get("export", {})
    out_path = io_export.export(
        processed, base_sr, p["output"],
        fmt=exp.get("format", "wav"),
        bit_depth=int(exp.get("bit_depth", 24)),
        target_sr=exp.get("sample_rate"),
        mp3_bitrate=int(exp.get("mp3_bitrate", 320)),
    )
    _progress(req_id, "done", 1.0)
    return {"output_path": out_path, "merged_count": len(inputs)}


METHODS = {
    "ping": m_ping,
    "analyze": m_analyze,
    "authenticity": m_authenticity,
    "release_check": m_release_check,
    "templates": m_templates,
    "process": m_process,
    "merge_process": m_merge_process,
}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {}) or {}
        fn = METHODS.get(method)
        if fn is None:
            _send({"id": req_id, "error": {"message": f"unknown method: {method}"}})
            continue
        try:
            result = fn(params, req_id)
            _send({"id": req_id, "result": result})
        except Exception as e:  # pragma: no cover - report to orchestrator
            _send({"id": req_id, "error": {
                "message": str(e), "trace": traceback.format_exc()}})


if __name__ == "__main__":
    main()
