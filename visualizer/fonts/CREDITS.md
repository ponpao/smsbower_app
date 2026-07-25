# Bundled fonts

All fonts here ship with the app so that export never depends on a network
connection or on a font being installed on the user's machine. Every file is
licensed under the SIL Open Font License 1.1 — see `OFL.txt`.

Real weight files are bundled per script (Regular + Bold). Synthetic/faux bold
is never used: smearing a glyph to fake weight closes the counters on Khmer
subscripts (ជើង) and Thai mark stacks.

| Script | Files | Source | Copyright |
|---|---|---|---|
| Khmer (km) | `NotoSansKhmer-VF.ttf`, `Battambang-*`, `Bokor`, `Dangrek`, `Fasthand`, `Koulen`, `Moul`, `Preahvihear`, `Suwannaphum-*` | Google Fonts | The Noto Project Authors / respective authors |
| Thai (th) | `NotoSansThai-Regular.ttf`, `NotoSansThai-Bold.ttf` | Noto | The Noto Project Authors |
| Devanagari (hi) | `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Noto | The Noto Project Authors |
| Tamil (ta) | `NotoSansTamil-Regular.ttf`, `NotoSansTamil-Bold.ttf` | Noto | The Noto Project Authors |
| Korean (ko) | `NanumSquare-Regular.ttf`, `NanumSquare-Bold.ttf` | Naver / Sandoll | Copyright (c) 2010, NAVER Corporation |

Latin falls through to the system UI font (Arial / DejaVu), which every target
platform has.

## Not yet bundled

- **Lao (lo)** and **Myanmar (my)** are wired up in `SCRIPT_FONTS` but have no
  bundled face. They resolve to a system font if one exists, otherwise the
  coverage check will flag them. Drop `NotoSansLao-*.ttf` /
  `NotoSansMyanmar-*.ttf` in this folder to enable them.
