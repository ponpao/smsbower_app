# -*- coding: utf-8 -*-
"""
TRAVKOD CODEs — License client (core logic, UI-free)
====================================================

Gates the Video Visualizer so it only runs with an active license.

Flow (mode: online + signed offline cache, code bound to first PC):
  1. Compute a stable machine_id for this PC.
  2. Activation: user pastes a code; we POST {code, machine_id} to the
     Google Apps Script Web App. The server binds the code to this PC on
     first use, computes an expiry date, and returns a signed payload.
  3. Every launch we re-validate online (so Revoke takes effect fast) and
     refresh the signed cache. If offline, we fall back to the cache but
     STILL enforce the exact expiry date — one day past expiry and it stops.

Security notes (read before shipping):
  * The response is signed with HMAC-SHA256 using LICENSE_SECRET, shared
    with the Apps Script. This stops a fake local server from spoofing a
    "valid" reply. Because the secret is symmetric it lives in the client,
    so ship a COMPILED build (PyInstaller) — do not distribute this .py.
  * Local clock-rollback is detected (last_seen date) so users can't turn
    the clock back to dodge expiry; the online path uses server date, which
    can't be spoofed locally.

Configure LICENSE_SECRET and WEB_APP_URL below (or via env vars) to match
your Apps Script deployment.
"""

import base64
import hashlib
import hmac
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# --------------------------------------------------------------------------
# Configuration — must match the Google Apps Script
# --------------------------------------------------------------------------

# Paste your deployed Apps Script Web App /exec URL here (or set env var).
WEB_APP_URL = os.environ.get(
    "TRAVKOD_LICENSE_URL",
    "https://script.google.com/macros/s/REPLACE_WITH_YOUR_DEPLOYMENT_ID/exec",
)

# Shared secret — MUST equal LICENSE_SECRET in the Apps Script. Change it to
# a long random string before shipping.
LICENSE_SECRET = os.environ.get(
    "TRAVKOD_LICENSE_SECRET",
    "CHANGE-ME-to-a-long-random-secret-2026",
).encode("utf-8")

APP_NAME = "TRAVKOD CODEs — Video Visualizer"
NETWORK_TIMEOUT = 12          # seconds for the online check
CLOCK_SKEW_DAYS = 1           # tolerance before flagging clock rollback


def _cache_path():
    base = (os.environ.get("APPDATA")
            or os.environ.get("XDG_CONFIG_HOME")
            or os.path.expanduser("~/.config"))
    d = os.path.join(base, "TRAVKOD_CODEs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "license.json")


# --------------------------------------------------------------------------
# Machine fingerprint
# --------------------------------------------------------------------------

def _raw_ids():
    ids = [platform.node() or ""]
    import uuid as _uuid
    mac = _uuid.getnode()
    if not (mac >> 40) & 0x1:      # skip random/locally-administered MACs
        ids.append(f"{mac:012x}")
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["reg", "query",
                 r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
                text=True, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            m = re.search(r"MachineGuid\s+REG_SZ\s+([\w-]+)", out)
            if m:
                ids.append(m.group(1))
        except Exception:
            pass
    else:
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(p) as fh:
                    ids.append(fh.read().strip())
                break
            except Exception:
                pass
    return [x for x in ids if x]


def machine_id():
    """Stable, non-reversible PC id like ABCDE-FGHIJ-KLMNO-PQRST."""
    raw = "|".join(_raw_ids()) or platform.platform()
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()
    return "-".join(h[i:i + 5] for i in range(0, 20, 5))


# --------------------------------------------------------------------------
# Signing
# --------------------------------------------------------------------------

def _sign(payload_str):
    # web-safe base64 WITHOUT padding, so it matches Apps Script's
    # Utilities.base64EncodeWebSafe(...).replace(/=+$/,'')
    raw = base64.urlsafe_b64encode(
        hmac.new(LICENSE_SECRET, payload_str.encode("utf-8"),
                 hashlib.sha256).digest()).decode("ascii")
    return raw.rstrip("=")


def _canonical(machine, expiry, status):
    return f"{machine}|{expiry}|{status}"


def verify_server_sig(machine, expiry, status, sig):
    expected = _sign(_canonical(machine, expiry, status))
    return hmac.compare_digest(expected, sig or "")


# --------------------------------------------------------------------------
# License state
# --------------------------------------------------------------------------

@dataclass
class LicenseState:
    ok: bool
    reason: str = ""            # machine-readable: "", revoked, expired, ...
    message: str = ""          # human message (Khmer/English)
    expiry: str = ""           # YYYY-MM-DD (last valid day, inclusive)
    status: str = ""
    online: bool = False
    days_left: int = 0


REASON_TEXT = {
    "invalid_code": "កូដមិនត្រឹមត្រូវ (Invalid code).",
    "revoked": "ឡាយសិននេះត្រូវបានលុបចោល (License revoked).",
    "expired": "ឡាយសិនផុតកំណត់ហើយ (License expired).",
    "code_used_on_another_pc": "កូដនេះបានប្រើនៅ PC ផ្សេងរួចហើយ.",
    "no_license": "មិនទាន់មានឡាយសិន — សូមបញ្ចូលកូដ (No license — enter a code).",
    "clock_tamper": "ម៉ោង/កាលបរិច្ឆេទកុំព្យូទ័រមិនត្រឹមត្រូវ (Clock changed) — ត្រូវ online ម្តង.",
    "tampered": "ឯកសារឡាយសិនខូច (License file tampered).",
    "server_error": "ម៉ាស៊ីនមេមានបញ្ហា (Server error).",
    "network": "គ្មានអ៊ីនធឺណិត និងគ្មាន cache (Offline, no cache).",
}


def _msg(reason, extra=""):
    return (REASON_TEXT.get(reason, reason) + (("  " + extra) if extra else "")).strip()


# --------------------------------------------------------------------------
# Cache (tamper-evident)
# --------------------------------------------------------------------------

def _write_cache(data):
    data = dict(data)
    data["_cache_sig"] = _sign(json.dumps(_cache_body(data), sort_keys=True))
    try:
        with open(_cache_path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception:
        pass


def _cache_body(data):
    return {k: data.get(k) for k in
            ("code", "machine", "expiry", "status", "last_seen")}


def _read_cache():
    try:
        with open(_cache_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if _sign(json.dumps(_cache_body(data), sort_keys=True)) != data.get("_cache_sig"):
        return "TAMPERED"
    return data


def clear_cache():
    try:
        os.remove(_cache_path())
    except OSError:
        pass


# --------------------------------------------------------------------------
# Networking
# --------------------------------------------------------------------------

def _post(action, code, machine):
    body = json.dumps({"action": action, "code": code,
                       "machine_id": machine,
                       "app": APP_NAME}).encode("utf-8")
    req = urllib.request.Request(
        WEB_APP_URL, data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _apply_server_reply(reply, code, machine):
    """Validate a server reply's signature and turn it into a LicenseState,
    updating the cache. Returns LicenseState or None if the reply is bogus."""
    if not isinstance(reply, dict):
        return None
    if not reply.get("ok"):
        reason = reply.get("reason", "server_error")
        # cache a revoked/expired verdict so offline can't re-enable it
        if reason in ("revoked", "expired", "invalid_code",
                      "code_used_on_another_pc"):
            _write_cache({"code": code, "machine": machine,
                          "expiry": reply.get("expiry", ""),
                          "status": reason.upper(),
                          "last_seen": date.today().isoformat()})
        return LicenseState(False, reason, _msg(reason), online=True,
                            expiry=reply.get("expiry", ""))
    exp, status = reply.get("expiry", ""), reply.get("status", "ACTIVE")
    if not verify_server_sig(machine, exp, status, reply.get("sig")):
        return LicenseState(False, "tampered",
                            "Signature mismatch — untrusted server reply.",
                            online=True)
    server_today = reply.get("server_date") or date.today().isoformat()
    _write_cache({"code": code, "machine": machine, "expiry": exp,
                  "status": status, "last_seen": server_today})
    return _decide(exp, status, server_today, online=True)


# --------------------------------------------------------------------------
# Core decision — STRICT day expiry
# --------------------------------------------------------------------------

def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _decide(expiry, status, today_iso, online):
    """Allow only while today <= expiry date. One day past expiry -> blocked.
    e.g. expiry 2026-07-10 works on the 10th, blocked on the 11th."""
    if status and status.upper() == "REVOKED":
        return LicenseState(False, "revoked", _msg("revoked"), expiry=expiry,
                            status=status, online=online)
    try:
        exp = _parse_date(expiry)
        today = _parse_date(today_iso)
    except Exception:
        return LicenseState(False, "tampered", _msg("tampered"), online=online)
    if today > exp:
        return LicenseState(False, "expired",
                            _msg("expired", f"(ផុត {expiry})"),
                            expiry=expiry, status=status, online=online)
    days_left = (exp - today).days
    return LicenseState(True, "", "", expiry=expiry, status=status or "ACTIVE",
                        online=online, days_left=days_left)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def activate(code):
    """User-entered code -> validate online and store. Returns LicenseState."""
    code = (code or "").strip().upper()
    machine = machine_id()
    if not code:
        return LicenseState(False, "invalid_code", _msg("invalid_code"))
    try:
        reply = _post("activate", code, machine)
    except Exception:
        return LicenseState(False, "network",
                            "សូមភ្ជាប់អ៊ីនធឺណិត ដើម្បី activate លើកដំបូង "
                            "(Internet required to activate).")
    st = _apply_server_reply(reply, code, machine)
    return st or LicenseState(False, "server_error", _msg("server_error"))


def check_license():
    """Called at startup. Returns LicenseState (ok True/False)."""
    machine = machine_id()
    cache = _read_cache()
    if cache == "TAMPERED":
        clear_cache()
        return LicenseState(False, "tampered", _msg("tampered"))
    if not cache:
        return LicenseState(False, "no_license", _msg("no_license"))
    if cache.get("machine") != machine:
        return LicenseState(False, "code_used_on_another_pc",
                            _msg("code_used_on_another_pc"))

    code = cache.get("code", "")
    # 1) try online (authoritative — catches Revoke and uses server date)
    try:
        reply = _post("validate", code, machine)
        st = _apply_server_reply(reply, code, machine)
        if st is not None:
            return st
    except Exception:
        pass   # offline -> fall through to cache

    # 2) offline: enforce cached verdict + strict expiry + rollback guard
    status = cache.get("status", "")
    if status in ("REVOKED", "EXPIRED", "INVALID_CODE",
                  "CODE_USED_ON_ANOTHER_PC"):
        r = status.lower()
        return LicenseState(False, r, _msg(r), expiry=cache.get("expiry", ""),
                            status=status)
    today = date.today()
    last_seen_iso = cache.get("last_seen", today.isoformat())
    try:
        last_seen = _parse_date(last_seen_iso)
    except Exception:
        last_seen = today
    if today < last_seen - timedelta(days=CLOCK_SKEW_DAYS):
        return LicenseState(False, "clock_tamper", _msg("clock_tamper"),
                            expiry=cache.get("expiry", ""))
    # advance last_seen so the clock can't be rolled back later
    effective = max(today, last_seen)
    st = _decide(cache.get("expiry", ""), status or "ACTIVE",
                 effective.isoformat(), online=False)
    if st.ok:
        c = dict(cache)
        c["last_seen"] = effective.isoformat()
        _write_cache(c)
    return st


if __name__ == "__main__":
    print("Machine ID:", machine_id())
    print("Cache path:", _cache_path())
    st = check_license()
    print("License:", st)
