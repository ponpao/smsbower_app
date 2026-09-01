// Thin wrapper around the official `adb` binary (Android platform-tools).
// Every call here targets a specific, already-visible device serial that
// the OS-level USB debugging prompt (or a prior authorized USB pairing)
// has already put in front of the user. TMIRROR never talks to a device
// that adb itself doesn't already list.
import { spawn } from 'node:child_process'
import { basename } from 'node:path'
import { detectTools } from './binaries'
import type { ClipboardResult, CommandResult, Device, DeviceStatus, FileEntry } from '../shared/types'

class AdbNotFoundError extends Error {
  constructor() {
    super('adb was not found. Set its location in Settings.')
    this.name = 'AdbNotFoundError'
  }
}

async function adbPathOrThrow(): Promise<string> {
  const tools = await detectTools()
  if (!tools.adbPath) throw new AdbNotFoundError()
  return tools.adbPath
}

function run(bin: string, args: string[], opts: { timeoutMs?: number } = {}): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolvePromise, reject) => {
    const child = spawn(bin, args)
    let stdout = ''
    let stderr = ''
    const timeout = opts.timeoutMs
      ? setTimeout(() => {
          child.kill()
          reject(new Error(`Timed out running ${bin} ${args.join(' ')}`))
        }, opts.timeoutMs)
      : null

    child.stdout?.on('data', (d) => (stdout += d.toString()))
    child.stderr?.on('data', (d) => (stderr += d.toString()))
    child.on('error', (err) => {
      if (timeout) clearTimeout(timeout)
      reject(err)
    })
    child.on('close', (code) => {
      if (timeout) clearTimeout(timeout)
      resolvePromise({ code: code ?? -1, stdout, stderr })
    })
  })
}

async function adb(args: string[], opts: { timeoutMs?: number } = {}): Promise<{ code: number; stdout: string; stderr: string }> {
  const bin = await adbPathOrThrow()
  return run(bin, args, opts)
}

function parseDeviceLine(line: string): { serial: string; status: DeviceStatus; connection: 'usb' | 'tcp' } | null {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('List of devices')) return null
  const parts = trimmed.split(/\s+/)
  if (parts.length < 2) return null
  const [serial, rawStatus] = parts
  let status: DeviceStatus
  if (rawStatus === 'device') status = 'ready'
  else if (rawStatus === 'unauthorized') status = 'unauthorized'
  else status = 'offline'
  const connection = /:\d+$/.test(serial) ? 'tcp' : 'usb'
  return { serial, status, connection }
}

async function getProp(serial: string, prop: string): Promise<string | undefined> {
  const res = await adb(['-s', serial, 'shell', 'getprop', prop], { timeoutMs: 5000 })
  const value = res.stdout.trim()
  return value.length > 0 ? value : undefined
}

async function getBattery(serial: string): Promise<number | undefined> {
  const res = await adb(['-s', serial, 'shell', 'dumpsys', 'battery'], { timeoutMs: 5000 })
  const match = res.stdout.match(/level:\s*(\d+)/)
  return match ? Number(match[1]) : undefined
}

export async function listDevices(): Promise<Device[]> {
  const res = await adb(['devices'], { timeoutMs: 8000 })
  const lines = res.stdout.split(/\r?\n/)
  const basics = lines.map(parseDeviceLine).filter((d): d is NonNullable<typeof d> => d !== null)

  const devices = await Promise.all(
    basics.map(async (b): Promise<Device> => {
      if (b.status !== 'ready') {
        return { ...b, isMirroring: false }
      }
      const [model, androidVersion, sdkRaw, battery] = await Promise.all([
        getProp(b.serial, 'ro.product.model'),
        getProp(b.serial, 'ro.build.version.release'),
        getProp(b.serial, 'ro.build.version.sdk'),
        getBattery(b.serial)
      ])
      return {
        ...b,
        model,
        androidVersion,
        sdkInt: sdkRaw ? Number(sdkRaw) : undefined,
        batteryPercent: battery,
        isMirroring: false
      }
    })
  )

  return devices
}

export async function installApk(serial: string, apkPath: string): Promise<CommandResult> {
  const res = await adb(['-s', serial, 'install', '-r', apkPath], { timeoutMs: 120000 })
  if (res.code === 0 && /Success/i.test(res.stdout)) {
    return { ok: true, message: `Installed ${basename(apkPath)}` }
  }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb install failed' }
}

export async function pushFile(serial: string, localPath: string, remoteDir = '/sdcard/Download'): Promise<CommandResult> {
  const remotePath = `${remoteDir.replace(/\/$/, '')}/${basename(localPath)}`
  const res = await adb(['-s', serial, 'push', localPath, remotePath], { timeoutMs: 300000 })
  if (res.code === 0) return { ok: true, message: `Sent ${basename(localPath)}` }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb push failed' }
}

export async function pullFile(serial: string, remotePath: string, localDir: string): Promise<CommandResult> {
  const res = await adb(['-s', serial, 'pull', remotePath, localDir], { timeoutMs: 300000 })
  if (res.code === 0) return { ok: true, message: `Pulled ${basename(remotePath)}` }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb pull failed' }
}

export async function listRemoteDir(serial: string, remoteDir: string): Promise<FileEntry[]> {
  const res = await adb(['-s', serial, 'shell', 'ls', '-la', remoteDir], { timeoutMs: 8000 })
  if (res.code !== 0) return []
  const lines = res.stdout.split(/\r?\n/).filter((l) => l.trim().length > 0 && !l.startsWith('total'))
  const entries: FileEntry[] = []
  for (const line of lines) {
    const parts = line.trim().split(/\s+/)
    if (parts.length < 8) continue
    const perms = parts[0]
    const size = Number(parts[4]) || 0
    const name = parts.slice(7).join(' ')
    if (name === '.' || name === '..') continue
    entries.push({
      name,
      path: `${remoteDir.replace(/\/$/, '')}/${name}`,
      isDirectory: perms.startsWith('d'),
      size
    })
  }
  return entries
}

export async function uninstallPackage(serial: string, packageName: string): Promise<CommandResult> {
  const res = await adb(['-s', serial, 'uninstall', packageName], { timeoutMs: 30000 })
  if (res.code === 0 && /Success/i.test(res.stdout)) {
    return { ok: true, message: `Uninstalled ${packageName}` }
  }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb uninstall failed' }
}

// Types text into the currently focused field on the device. This simulates
// keystrokes via the official `adb shell input` command — it is not a
// system-clipboard write (Android exposes no such adb command), so the UI
// labels it accurately as "send text" rather than "set clipboard".
export async function sendTextToDevice(serial: string, text: string): Promise<ClipboardResult> {
  const escaped = text.replace(/([\\ ()<>|;&*~"'`!$#])/g, '\\$1')
  const res = await adb(['-s', serial, 'shell', 'input', 'text', escaped], { timeoutMs: 8000 })
  if (res.code === 0) return { ok: true, message: 'Sent to device' }
  return { ok: false, message: res.stderr.trim() || 'Failed to send text' }
}

export async function screenshot(serial: string, localPath: string): Promise<CommandResult> {
  const remoteTmp = '/sdcard/tmirror_screenshot.png'
  const cap = await adb(['-s', serial, 'shell', 'screencap', '-p', remoteTmp], { timeoutMs: 15000 })
  if (cap.code !== 0) return { ok: false, message: cap.stderr.trim() || 'screencap failed' }
  const pull = await adb(['-s', serial, 'pull', remoteTmp, localPath], { timeoutMs: 15000 })
  await adb(['-s', serial, 'shell', 'rm', remoteTmp], { timeoutMs: 5000 })
  if (pull.code !== 0) return { ok: false, message: pull.stderr.trim() || 'pull failed' }
  return { ok: true, message: localPath }
}

// Switches an already-authorized USB device into ADB-over-Wi-Fi mode.
// Must be run while the device is still attached and authorized on USB —
// this is the standard `adb tcpip` flow, not a hidden or persistent backdoor:
// it only takes effect until the device reboots or Wi-Fi debugging is
// turned off again on the device.
export async function enableTcpIp(serial: string, port = 5555): Promise<CommandResult> {
  const res = await adb(['-s', serial, 'tcpip', String(port)], { timeoutMs: 10000 })
  if (res.code === 0) return { ok: true, message: res.stdout.trim() || `Listening on port ${port}` }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb tcpip failed' }
}

export async function getWifiIpAddress(serial: string): Promise<string | undefined> {
  const res = await adb(['-s', serial, 'shell', 'ip', 'route'], { timeoutMs: 5000 })
  const match = res.stdout.match(/src\s+(\d+\.\d+\.\d+\.\d+)/)
  return match ? match[1] : undefined
}

export async function connectOverTcp(host: string, port: number): Promise<CommandResult> {
  const res = await adb(['connect', `${host}:${port}`], { timeoutMs: 15000 })
  if (res.code === 0 && /connected/i.test(res.stdout)) {
    return { ok: true, message: res.stdout.trim() }
  }
  return { ok: false, message: res.stderr.trim() || res.stdout.trim() || 'adb connect failed' }
}

export { AdbNotFoundError }
