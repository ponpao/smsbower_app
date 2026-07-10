# -*- coding: utf-8 -*-
"""
License gate UI (CustomTkinter) for the Video Visualizer.

Usage in the app entry point (before building the main window):

    from license.license_gate import require_license
    if not require_license():
        sys.exit(0)          # no valid license -> app must not run
    # ... build and run the visualizer ...

Shows the PC's Machine ID (to send to the admin), a code box, live status,
and the days remaining. If the license is missing/expired/revoked the app
cannot proceed.
"""

import sys
import threading

import customtkinter as ctk

try:
    from . import license_client as lic
except ImportError:
    import license_client as lic

ACCENT = "#d64336"
ACCENT_HOVER = "#b8352b"
MUTED = ("#6b7280", "#8b8b9e")


class LicenseDialog(ctk.CTkToplevel):
    def __init__(self, master, state):
        super().__init__(master)
        self.title("TRAVKOD CODEs — License / ឡាយសិន")
        self.geometry("440x430")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = False
        self._machine = lic.machine_id()

        ctk.CTkLabel(self, text="🔑 License Activation",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(18, 2))
        ctk.CTkLabel(self, text="សូមបញ្ចូលកូដ ដើម្បីប្រើប្រាស់កម្មវិធី "
                                "(Enter your code to unlock).",
                     font=ctk.CTkFont(size=12), text_color=MUTED).pack()

        # Machine ID row (read-only, copyable)
        ctk.CTkLabel(self, text="Your PC ID (ផ្ញើ ID នេះទៅ Admin):",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=24, pady=(16, 2))
        idrow = ctk.CTkFrame(self, fg_color="transparent")
        idrow.pack(fill="x", padx=24)
        self.id_entry = ctk.CTkEntry(idrow, font=ctk.CTkFont(size=13))
        self.id_entry.insert(0, self._machine)
        self.id_entry.configure(state="readonly")
        self.id_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(idrow, text="📋 Copy", width=70, fg_color=("#d1d5db", "#2b2b3a"),
                      hover_color=("#b8bcc4", "#3a3a4d"),
                      text_color=("#111827", "#e5e7eb"),
                      command=self._copy_id).pack(side="left", padx=(6, 0))

        # Code entry
        ctk.CTkLabel(self, text="License Code (កូដ):",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=24, pady=(14, 2))
        self.code_entry = ctk.CTkEntry(
            self, placeholder_text="TRAV-XXXX-XXXX-XXXX",
            font=ctk.CTkFont(size=15), justify="center", height=40)
        self.code_entry.pack(fill="x", padx=24)
        self.code_entry.bind("<Return>", lambda e: self._activate())

        self.activate_btn = ctk.CTkButton(
            self, text="⚡ Activate / ដំណើរការ", height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._activate)
        self.activate_btn.pack(fill="x", padx=24, pady=(14, 6))

        self.status_lbl = ctk.CTkLabel(
            self, text=state.message or lic._msg(state.reason or "no_license"),
            font=ctk.CTkFont(size=12), text_color=("#b91c1c", "#f87171"),
            wraplength=390, justify="center")
        self.status_lbl.pack(padx=24, pady=(2, 4))

        ctk.CTkLabel(self, text="បើមិនទាន់មានកូដ សូមទាក់ទង Admin។",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self.code_entry.focus_set)

    def _copy_id(self):
        self.clipboard_clear()
        self.clipboard_append(self._machine)
        self.status_lbl.configure(text="Copied PC ID ✓", text_color=MUTED)

    def _activate(self):
        code = self.code_entry.get().strip()
        if not code:
            return
        self.activate_btn.configure(state="disabled", text="Checking…")
        self.status_lbl.configure(text="កំពុងពិនិត្យ… (Checking online…)",
                                  text_color=MUTED)

        def worker():
            st = lic.activate(code)
            self.after(0, self._done, st)

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, st):
        self.activate_btn.configure(state="normal", text="⚡ Activate / ដំណើរការ")
        if st.ok:
            self.result = True
            self.status_lbl.configure(
                text=f"✅ Activated! សល់ {st.days_left} ថ្ងៃ (expires {st.expiry})",
                text_color=("#047857", "#34d399"))
            self.after(900, self.destroy)
        else:
            self.status_lbl.configure(text=st.message or st.reason,
                                      text_color=("#b91c1c", "#f87171"))

    def _on_close(self):
        self.result = False
        self.destroy()


def require_license(parent=None):
    """Return True if the app may run. Shows the activation dialog otherwise.

    Can be called before or after a root window exists; creates a temporary
    hidden root if needed.
    """
    state = lic.check_license()
    if state.ok:
        return True

    owns_root = parent is None
    if owns_root:
        parent = ctk.CTk()
        parent.withdraw()

    dialog = LicenseDialog(parent, state)
    dialog.grab_set()
    parent.wait_window(dialog)
    allowed = dialog.result

    if owns_root:
        parent.destroy()
    return allowed


def license_banner():
    """Short status string for showing remaining days in the app, or ''. """
    st = lic.check_license()
    if st.ok and st.days_left is not None:
        return f"License OK · សល់ {st.days_left} ថ្ងៃ (exp {st.expiry})"
    return ""


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    print("require_license ->", require_license())
    sys.exit(0)
