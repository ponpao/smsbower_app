# Optional UI font

TK Downloader uses the system UI font by default. Windows and macOS ship a Khmer
font (Khmer UI / Khmer Sangam MN), so ខ្មែរ renders correctly out of the box.

If Khmer text shows as empty boxes (□□□) — which can happen on a minimal Linux
install — drop **one** Khmer-capable font file here:

```
tk_downloader/assets/fonts/NotoSansKhmer-Regular.ttf
```

The first `.ttf` / `.otf` found in this folder is registered as the app-wide UI
font automatically on the next launch. Nothing else to configure.

Noto Sans Khmer is a good choice (SIL Open Font License):
<https://fonts.google.com/noto/specimen/Noto+Sans+Khmer>

On Debian/Ubuntu you can also just install a system font instead:
`sudo apt install fonts-noto-core`
