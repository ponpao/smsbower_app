import { contextBridge, ipcRenderer, webUtils } from 'electron'
import { IPC } from '../shared/ipc'
import type {
  ArrangeMode,
  ClipboardResult,
  CommandResult,
  Device,
  FileEntry,
  PairSession,
  PairStatusEvent,
  Settings,
  ToolStatus,
  TransferProgressEvent
} from '../shared/types'

const api = {
  devices: {
    list: (): Promise<Device[]> => ipcRenderer.invoke(IPC.devicesList),
    startMirror: (serial: string, label: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.devicesStartMirror, serial, label),
    stopMirror: (serial: string): Promise<CommandResult> => ipcRenderer.invoke(IPC.devicesStopMirror, serial),
    arrange: (mode: ArrangeMode, devices: { serial: string; label: string }[]): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.devicesArrange, mode, devices),
    closeAllMirrors: (): Promise<CommandResult> => ipcRenderer.invoke(IPC.devicesCloseAllMirrors),
    screenshot: (serial: string): Promise<CommandResult> => ipcRenderer.invoke(IPC.devicesScreenshot, serial),
    startRecording: (serial: string, label: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.devicesStartRecording, serial, label),
    stopRecording: (serial: string): Promise<CommandResult> => ipcRenderer.invoke(IPC.devicesStopRecording, serial),
    uninstall: (serial: string, packageName: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.devicesUninstall, serial, packageName),
    enableWifi: (serial: string): Promise<CommandResult> => ipcRenderer.invoke(IPC.devicesEnableWifi, serial),
    connectTcp: (host: string, port: number): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.devicesConnectTcp, host, port)
  },
  transfer: {
    installApk: (serial: string, apkPath: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.transferInstallApk, serial, apkPath),
    push: (serial: string, localPath: string, remoteDir: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.transferPush, serial, localPath, remoteDir),
    pull: (serial: string, remotePath: string, localDir: string): Promise<CommandResult> =>
      ipcRenderer.invoke(IPC.transferPull, serial, remotePath, localDir),
    listRemote: (serial: string, remoteDir: string): Promise<FileEntry[]> =>
      ipcRenderer.invoke(IPC.transferListRemote, serial, remoteDir),
    onProgress: (cb: (event: TransferProgressEvent) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, payload: TransferProgressEvent): void => cb(payload)
      ipcRenderer.on(IPC.transferProgress, listener)
      return () => ipcRenderer.removeListener(IPC.transferProgress, listener)
    }
  },
  clipboard: {
    readPc: (): Promise<ClipboardResult> => ipcRenderer.invoke(IPC.clipboardReadPc),
    writePc: (text: string): Promise<CommandResult> => ipcRenderer.invoke(IPC.clipboardWritePc, text),
    sendToDevice: (serial: string, text: string): Promise<ClipboardResult> =>
      ipcRenderer.invoke(IPC.clipboardSendToDevice, serial, text)
  },
  pair: {
    createSession: (): Promise<PairSession> => ipcRenderer.invoke(IPC.pairCreateSession),
    cancelSession: (): Promise<CommandResult> => ipcRenderer.invoke(IPC.pairCancelSession),
    onStatus: (cb: (event: PairStatusEvent) => void): (() => void) => {
      const listener = (_e: Electron.IpcRendererEvent, payload: PairStatusEvent): void => cb(payload)
      ipcRenderer.on(IPC.pairStatus, listener)
      return () => ipcRenderer.removeListener(IPC.pairStatus, listener)
    }
  },
  tools: {
    detect: (): Promise<ToolStatus> => ipcRenderer.invoke(IPC.toolsDetect),
    pickFolder: (): Promise<string | null> => ipcRenderer.invoke(IPC.toolsPickFolder)
  },
  settings: {
    get: (): Promise<Settings> => ipcRenderer.invoke(IPC.settingsGet),
    set: (settings: Settings): Promise<CommandResult> => ipcRenderer.invoke(IPC.settingsSet, settings)
  },
  dialog: {
    pickFiles: (filters?: { name: string; extensions: string[] }[]): Promise<string[]> =>
      ipcRenderer.invoke(IPC.dialogPickFiles, filters),
    pickDirectory: (): Promise<string | null> => ipcRenderer.invoke(IPC.dialogPickDirectory)
  },
  getPathForFile: (file: File): string => webUtils.getPathForFile(file)
}

contextBridge.exposeInMainWorld('tmirror', api)

export type TmirrorApi = typeof api
