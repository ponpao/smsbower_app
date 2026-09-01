// Wrapper around the official `scrcpy` binary. TMIRROR never reimplements
// video encode/decode — every mirror window is a real scrcpy process
// attached to an already-authorized adb device.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { app, screen } from 'electron'
import { detectTools } from './binaries'
import type { ArrangeMode } from '../shared/types'

class ScrcpyNotFoundError extends Error {
  constructor() {
    super('scrcpy was not found. Set its location in Settings.')
    this.name = 'ScrcpyNotFoundError'
  }
}

interface MirrorHandle {
  serial: string
  child: ChildProcess
  recording: boolean
}

const mirrors = new Map<string, MirrorHandle>()

function recordingsDir(): string {
  const dir = join(app.getPath('videos') || app.getPath('documents'), 'TMIRROR Recordings')
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  return dir
}

interface WindowRect {
  x: number
  y: number
  width: number
  height: number
}

async function scrcpyPathOrThrow(): Promise<string> {
  const tools = await detectTools()
  if (!tools.scrcpyPath) throw new ScrcpyNotFoundError()
  return tools.scrcpyPath
}

function buildArgs(serial: string, title: string, rect?: WindowRect, recordPath?: string): string[] {
  const args = ['-s', serial, '--window-title', title]
  if (rect) {
    args.push(
      '--window-x',
      String(Math.round(rect.x)),
      '--window-y',
      String(Math.round(rect.y)),
      '--window-width',
      String(Math.round(rect.width)),
      '--window-height',
      String(Math.round(rect.height))
    )
  }
  if (recordPath) {
    args.push('--record', recordPath)
  }
  return args
}

export function isMirroring(serial: string): boolean {
  return mirrors.has(serial)
}

export function activeSerials(): string[] {
  return Array.from(mirrors.keys())
}

export async function startMirror(serial: string, deviceLabel: string, rect?: WindowRect): Promise<void> {
  if (mirrors.has(serial)) return
  const bin = await scrcpyPathOrThrow()
  const title = `TMIRROR — ${deviceLabel}`
  const child = spawn(bin, buildArgs(serial, title, rect), { stdio: 'ignore' })
  mirrors.set(serial, { serial, child, recording: false })
  child.on('exit', () => {
    mirrors.delete(serial)
  })
}

export function stopMirror(serial: string): void {
  const handle = mirrors.get(serial)
  if (!handle) return
  handle.child.kill()
  mirrors.delete(serial)
}

export function stopAllMirrors(): void {
  for (const serial of Array.from(mirrors.keys())) stopMirror(serial)
}

function workArea(): WindowRect {
  const display = screen.getPrimaryDisplay()
  return {
    x: display.workArea.x,
    y: display.workArea.y,
    width: display.workArea.width,
    height: display.workArea.height
  }
}

function computeLayout(mode: ArrangeMode, count: number): WindowRect[] {
  const area = workArea()
  if (count === 0) return []

  if (mode === 'side-by-side') {
    const width = area.width / count
    return Array.from({ length: count }, (_, i) => ({
      x: area.x + i * width,
      y: area.y,
      width,
      height: area.height
    }))
  }

  // grid
  const cols = Math.ceil(Math.sqrt(count))
  const rows = Math.ceil(count / cols)
  const cellWidth = area.width / cols
  const cellHeight = area.height / rows
  return Array.from({ length: count }, (_, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    return {
      x: area.x + col * cellWidth,
      y: area.y + row * cellHeight,
      width: cellWidth,
      height: cellHeight
    }
  })
}

// Relaunches every active mirror positioned into the requested layout.
// scrcpy has no CLI to reposition a running window, so arranging means a
// quick, deliberate restart of each mirror — the same authorized session,
// just repositioned.
export async function arrangeMirrors(
  mode: ArrangeMode,
  devices: { serial: string; label: string }[]
): Promise<void> {
  const activeDevices = devices.filter((d) => mirrors.has(d.serial))
  const rects = computeLayout(mode, activeDevices.length)

  for (let i = 0; i < activeDevices.length; i++) {
    const { serial, label } = activeDevices[i]
    stopMirror(serial)
    await startMirror(serial, label, rects[i])
  }
}

export async function startRecording(serial: string, deviceLabel: string): Promise<string> {
  stopMirror(serial)
  const bin = await scrcpyPathOrThrow()
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  const outPath = join(recordingsDir(), `tmirror-${deviceLabel.replace(/\s+/g, '_')}-${timestamp}.mp4`)
  const title = `TMIRROR — Recording ${deviceLabel}`
  const child = spawn(bin, buildArgs(serial, title, undefined, outPath), { stdio: 'ignore' })
  mirrors.set(serial, { serial, child, recording: true })
  child.on('exit', () => {
    mirrors.delete(serial)
  })
  return outPath
}

export function stopRecording(serial: string): void {
  stopMirror(serial)
}

export function isRecording(serial: string): boolean {
  return mirrors.get(serial)?.recording ?? false
}

export { ScrcpyNotFoundError }
