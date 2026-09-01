// Shared types between the Electron main process and the renderer.
// TMIRROR only ever talks to devices the user has explicitly authorized
// over USB debugging (or a locally-confirmed LAN pairing after that).

export type ConnectionKind = 'usb' | 'tcp'

export type DeviceStatus = 'ready' | 'unauthorized' | 'offline'

export interface Device {
  serial: string
  status: DeviceStatus
  connection: ConnectionKind
  model?: string
  androidVersion?: string
  sdkInt?: number
  batteryPercent?: number
  isMirroring: boolean
}

export interface DevicesSnapshot {
  devices: Device[]
  fetchedAt: number
}

export interface ToolStatus {
  adbPath: string | null
  scrcpyPath: string | null
  adbFound: boolean
  scrcpyFound: boolean
  adbVersion?: string
  scrcpyVersion?: string
}

export interface Settings {
  language: 'km' | 'en'
  adbPath: string | null
  scrcpyPath: string | null
  accent: 'coral' | 'teal'
}

export type ArrangeMode = 'grid' | 'side-by-side'

export interface TransferProgressEvent {
  id: string
  serial: string
  fileName: string
  kind: 'install' | 'push' | 'pull'
  status: 'starting' | 'progress' | 'success' | 'error'
  message?: string
  percent?: number
}

export interface PairSession {
  token: string
  url: string
  qrDataUrl: string
  lanIp: string
  port: number
  expiresAt: number
}

export type PairSessionState = 'pending' | 'confirmed' | 'expired' | 'cancelled'

export interface PairStatusEvent {
  token: string
  state: PairSessionState
  serial?: string
}

export interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifiedAt?: number
}

export interface ClipboardResult {
  ok: boolean
  text?: string
  message?: string
}

export interface CommandResult {
  ok: boolean
  message?: string
}
