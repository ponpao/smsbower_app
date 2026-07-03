# Code signing

Signed installers require your own certificates; they are not committed here.

## Windows (NSIS)
Set before `npm run dist:win`:
- `CSC_LINK` — path/base64 of your `.pfx`
- `CSC_KEY_PASSWORD` — its password
electron-builder signs the installer and app automatically.

## macOS (dmg)
- `CSC_LINK` / `CSC_KEY_PASSWORD` — Developer ID Application cert
- Notarize with `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`
  (electron-builder runs notarization when these are present).

Never commit certificates or passwords.
