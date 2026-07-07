# Bundled fonts

Place `KantumruyPro*.ttf` here before building. The easiest way:

```
python scripts/fetch_font.py
```

(downloads the official Kantumruy Pro variable font from the
[google/fonts](https://github.com/google/fonts/tree/main/ofl/kantumruypro)
repository, OFL-licensed).

If no .ttf is present, Grok Studio automatically falls back to **Segoe UI**
at runtime — the app still works, Khmer text just renders with the system
font instead.
