// Locates the Python interpreter and the DSP worker for both dev and packaged
// runs. In a packaged app we prefer an embedded runtime under
// resources/python-embed; in dev we fall back to the project's .venv or system
// python. All processing stays local — this only resolves paths.

import { app } from 'electron';
import fs from 'node:fs';
import path from 'node:path';

export interface PythonEnv {
  python: string;
  cwd: string; // dir to run `-m travkod.worker` from
  args: string[];
}

function firstExisting(candidates: string[]): string | null {
  for (const c of candidates) {
    try {
      if (c && fs.existsSync(c)) return c;
    } catch {
      /* ignore */
    }
  }
  return null;
}

export function resolvePythonEnv(): PythonEnv {
  const isPackaged = app.isPackaged;
  const resourcesRoot = isPackaged
    ? process.resourcesPath
    : path.resolve(app.getAppPath());

  const pythonDir = isPackaged
    ? path.join(resourcesRoot, 'python')
    : path.join(resourcesRoot, 'python');

  // Preferred: an embedded interpreter shipped with the app.
  const embedded = firstExisting([
    path.join(resourcesRoot, 'python-embed', process.platform === 'win32' ? 'python.exe' : 'bin/python3'),
  ]);

  // Dev fallbacks: project venv, then system python.
  const venv = firstExisting([
    path.join(resourcesRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
    path.join(process.cwd(), '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'),
  ]);

  const python =
    embedded || venv || (process.platform === 'win32' ? 'python' : 'python3');

  return {
    python,
    cwd: pythonDir,
    args: ['-m', 'travkod.worker'],
  };
}
