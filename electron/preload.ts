// Secure bridge: exposes a typed, minimal `window.travkod` API to the renderer.
// No Node globals leak into the page (contextIsolation + no nodeIntegration).

import { contextBridge, ipcRenderer } from 'electron';

const api = {
  addFiles: () => ipcRenderer.invoke('tk:addFiles') as Promise<string[]>,
  addFolder: () => ipcRenderer.invoke('tk:addFolder') as Promise<string[]>,
  analyze: (p: string) => ipcRenderer.invoke('tk:analyze', p),
  authenticity: (p: string) => ipcRenderer.invoke('tk:authenticity', p),
  releaseCheck: (payload: any) => ipcRenderer.invoke('tk:releaseCheck', payload),
  templates: () => ipcRenderer.invoke('tk:templates'),
  startExport: (payload: any) => ipcRenderer.invoke('tk:startExport', payload),
  stopExport: () => ipcRenderer.invoke('tk:stopExport'),
  chooseOutput: () => ipcRenderer.invoke('tk:chooseOutput') as Promise<string | null>,
  openOutput: (folder: string) => ipcRenderer.invoke('tk:openOutput', folder),
  loadPresets: () => ipcRenderer.invoke('tk:loadPresets'),
  savePreset: (preset: any) => ipcRenderer.invoke('tk:savePreset', preset),
  deletePreset: (name: string) => ipcRenderer.invoke('tk:deletePreset', name),
  sysStats: () => ipcRenderer.invoke('tk:sysStats') as Promise<{ cpu: number; ram: number }>,
  windowControl: (action: 'minimize' | 'maximize' | 'close') =>
    ipcRenderer.invoke('tk:windowControl', action),

  onProgress: (cb: (e: any) => void) => {
    const h = (_: unknown, data: any) => cb(data);
    ipcRenderer.on('tk:onProgress', h);
    return () => ipcRenderer.removeListener('tk:onProgress', h);
  },
  onJobStatus: (cb: (e: any) => void) => {
    const h = (_: unknown, data: any) => cb(data);
    ipcRenderer.on('tk:onJobStatus', h);
    return () => ipcRenderer.removeListener('tk:onJobStatus', h);
  },
  onJobResult: (cb: (e: any) => void) => {
    const h = (_: unknown, data: any) => cb(data);
    ipcRenderer.on('tk:onJobResult', h);
    return () => ipcRenderer.removeListener('tk:onJobResult', h);
  },
};

contextBridge.exposeInMainWorld('travkod', api);

export type TravkodApi = typeof api;
