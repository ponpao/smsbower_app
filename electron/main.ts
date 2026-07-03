// Electron main process: window, menus, IPC, preset storage, system stats, and
// the bridge to the Job Orchestrator / Python DSP worker pool.

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from 'electron';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Orchestrator, QueueJob } from './orchestrator.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = process.env.NODE_ENV === 'development';

let win: BrowserWindow | null = null;
const orch = new Orchestrator();

const AUDIO_EXTS = ['.wav', '.flac', '.mp3', '.aif', '.aiff', '.ogg', '.m4a'];
const PRESET_FILE = () => path.join(app.getPath('userData'), 'presets.json');

function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 760,
    minWidth: 980,
    minHeight: 620,
    backgroundColor: '#0d1420',
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  // Wire orchestrator events to the renderer.
  orch.onStatus = (jobId, status, extra) =>
    win?.webContents.send('tk:onJobStatus', { jobId, status, extra });
  orch.onProgress = (jobId, stage, frac) =>
    win?.webContents.send('tk:onProgress', { jobId, stage, frac });
  orch.onResult = (jobId, result) =>
    win?.webContents.send('tk:onJobResult', { jobId, ...result });
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// --------------------------------------------------------------------------
// IPC: file import
// --------------------------------------------------------------------------
ipcMain.handle('tk:addFiles', async () => {
  const res = await dialog.showOpenDialog(win!, {
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'Audio', extensions: AUDIO_EXTS.map((e) => e.slice(1)) }],
  });
  return res.canceled ? [] : res.filePaths;
});

ipcMain.handle('tk:addFolder', async () => {
  const res = await dialog.showOpenDialog(win!, { properties: ['openDirectory'] });
  if (res.canceled) return [];
  const dir = res.filePaths[0];
  const out: string[] = [];
  const walk = (d: string) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (AUDIO_EXTS.includes(path.extname(entry.name).toLowerCase())) out.push(p);
    }
  };
  walk(dir);
  return out;
});

ipcMain.handle('tk:chooseOutput', async () => {
  const res = await dialog.showOpenDialog(win!, { properties: ['openDirectory', 'createDirectory'] });
  return res.canceled ? null : res.filePaths[0];
});

ipcMain.handle('tk:openOutput', async (_e, folder: string) => {
  if (folder) await shell.openPath(folder);
});

// --------------------------------------------------------------------------
// IPC: analysis / authenticity / release / templates (one-shot workers)
// --------------------------------------------------------------------------
ipcMain.handle('tk:analyze', async (_e, filePath: string) =>
  orch.oneShot('analyze', { path: filePath }),
);

ipcMain.handle('tk:authenticity', async (_e, filePath: string) =>
  orch.oneShot('authenticity', { path: filePath }),
);

ipcMain.handle('tk:releaseCheck', async (_e, payload) =>
  orch.oneShot('release_check', payload),
);

ipcMain.handle('tk:templates', async () => orch.oneShot('templates', {}));

// --------------------------------------------------------------------------
// IPC: batch export
// --------------------------------------------------------------------------
ipcMain.handle('tk:startExport', async (_e, payload) => {
  const { items, params, exportSettings } = payload as {
    items: { id: string; path: string; filename: string; isAi?: boolean }[];
    params: any;
    exportSettings: any;
  };
  orch.setThreads(exportSettings.threads ?? 4);

  const outDir = exportSettings.output_folder || path.join(os.homedir(), 'TRAVKOD Exports');
  fs.mkdirSync(outDir, { recursive: true });

  const jobs: QueueJob[] = [];
  if (exportSettings.merge && items.length > 1) {
    const outBase = path.join(outDir, 'TRAVKOD_merged');
    jobs.push({
      id: 'merged',
      method: 'merge_process',
      params: {
        inputs: items.map((i) => i.path),
        output: outBase,
        params,
        export: exportSettings,
      },
    });
  } else {
    for (const it of items) {
      const stem = path.parse(it.filename).name;
      const outBase = path.join(outDir, `${stem}_travkod`);
      jobs.push({
        id: it.id,
        method: 'process',
        params: { input: it.path, output: outBase, params, export: exportSettings },
      });
    }
  }

  orch.enqueue(jobs);
  orch.start().catch((err) =>
    win?.webContents.send('tk:onJobStatus', {
      jobId: '*', status: 'Error', extra: { error: String(err?.message || err) },
    }),
  );
  return { outDir, count: jobs.length };
});

ipcMain.handle('tk:stopExport', async () => {
  orch.stop();
  return true;
});

// --------------------------------------------------------------------------
// IPC: presets (persisted in userData)
// --------------------------------------------------------------------------
ipcMain.handle('tk:loadPresets', async () => {
  try {
    return JSON.parse(fs.readFileSync(PRESET_FILE(), 'utf-8'));
  } catch {
    return [];
  }
});

ipcMain.handle('tk:savePreset', async (_e, preset) => {
  let list: any[] = [];
  try { list = JSON.parse(fs.readFileSync(PRESET_FILE(), 'utf-8')); } catch { /* new */ }
  const idx = list.findIndex((p) => p.name === preset.name);
  if (idx >= 0) list[idx] = preset; else list.push(preset);
  fs.writeFileSync(PRESET_FILE(), JSON.stringify(list, null, 2));
  return list;
});

ipcMain.handle('tk:deletePreset', async (_e, name: string) => {
  let list: any[] = [];
  try { list = JSON.parse(fs.readFileSync(PRESET_FILE(), 'utf-8')); } catch { /* none */ }
  list = list.filter((p) => p.name !== name);
  fs.writeFileSync(PRESET_FILE(), JSON.stringify(list, null, 2));
  return list;
});

// --------------------------------------------------------------------------
// IPC: system stats + window controls
// --------------------------------------------------------------------------
let lastCpu = os.cpus();
ipcMain.handle('tk:sysStats', async () => {
  const cpus = os.cpus();
  let idle = 0, total = 0;
  for (let i = 0; i < cpus.length; i++) {
    const a = lastCpu[i]?.times, b = cpus[i].times;
    if (!a) continue;
    const t = (b.user - a.user) + (b.nice - a.nice) + (b.sys - a.sys) + (b.idle - a.idle) + (b.irq - a.irq);
    idle += b.idle - a.idle;
    total += t;
  }
  lastCpu = cpus;
  const cpu = total > 0 ? Math.round((1 - idle / total) * 100) : 0;
  const ram = Math.round((1 - os.freemem() / os.totalmem()) * 100);
  return { cpu, ram };
});

ipcMain.handle('tk:windowControl', async (_e, action: string) => {
  if (!win) return;
  if (action === 'minimize') win.minimize();
  else if (action === 'maximize') win.isMaximized() ? win.unmaximize() : win.maximize();
  else if (action === 'close') win.close();
});
