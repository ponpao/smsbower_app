# Bundling a portable Python runtime (`python-embed/`)

For a self-contained installer, ship a portable Python 3.11 with the DSP deps so
users don't need Python installed. `electron-builder` copies `python-embed/` into
the app's resources (see `package.json > build.extraResources`), and
`electron/pythonEnv.ts` prefers it at runtime.

## Windows
1. Download the "Windows embeddable package" for Python 3.11 from python.org.
2. Unzip into `python-embed/`.
3. Enable site-packages (uncomment `import site` in `python311._pth`).
4. `python-embed\python.exe -m pip install -r python\requirements.txt`

## macOS / Linux
Use `python-build-standalone` (indygreg) or a relocatable venv:
```bash
python3.11 -m venv python-embed
python-embed/bin/python -m pip install -r python/requirements.txt
```
The locator looks for `python-embed/bin/python3` (unix) or
`python-embed/python.exe` (windows). If absent, it falls back to `.venv` then the
system `python3`.
