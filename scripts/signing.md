# Code signing

Signed installers require your own certificates; they are not committed here.
TRAVKOD is built with PyInstaller (see `build_pyinstaller.md`), so signing is
applied to the produced app/installer after the build.

## Windows
Build `dist/TRAVKOD` with PyInstaller, then sign the executable (and your
installer) with `signtool`:

```powershell
signtool sign /fd SHA256 /a /f mycert.pfx /p <password> ^
  /tr http://timestamp.digicert.com /td SHA256 dist\TRAVKOD\TRAVKOD.exe
```

Wrap `dist/TRAVKOD` with Inno Setup or NSIS for an installer, then sign the
installer the same way.

## macOS
Build a `.app` (add a `BUNDLE(...)` step to `travkod.spec`), then sign and
notarize with your Developer ID:

```bash
codesign --deep --force --options runtime \
  --sign "Developer ID Application: <you> (<TEAMID>)" dist/TRAVKOD.app
xcrun notarytool submit dist/TRAVKOD.dmg \
  --apple-id "<APPLE_ID>" --team-id "<TEAMID>" --password "<APP_SPECIFIC_PW>" --wait
xcrun stapler staple dist/TRAVKOD.dmg
```

Never commit certificates or passwords.
