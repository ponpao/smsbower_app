// Locates the official `adb` (Android platform-tools) and `scrcpy` binaries.
// TMIRROR never bundles or downloads these — the user installs the official
// projects and either has them on PATH or points Settings at their folder.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { delimiter, join } from 'node:path'
import { loadSettings } from './store'
import type { ToolStatus } from '../shared/types'

const isWindows = process.platform === 'win32'
const ADB_NAME = isWindows ? 'adb.exe' : 'adb'
const SCRCPY_NAME = isWindows ? 'scrcpy.exe' : 'scrcpy'

function findOnPath(binaryName: string): string | null {
  const pathVar = process.env.PATH || ''
  for (const dir of pathVar.split(delimiter)) {
    if (!dir) continue
    const candidate = join(dir, binaryName)
    if (existsSync(candidate)) return candidate
  }
  return null
}

function resolveBinary(binaryName: string, configuredPath: string | null): string | null {
  if (configuredPath) {
    if (existsSync(configuredPath)) return configuredPath
    const joined = join(configuredPath, binaryName)
    if (existsSync(joined)) return joined
  }
  return findOnPath(binaryName)
}

function runVersion(binPath: string): Promise<string | undefined> {
  return new Promise((resolvePromise) => {
    try {
      const child = spawn(binPath, ['--version'])
      let out = ''
      child.stdout?.on('data', (d) => (out += d.toString()))
      child.stderr?.on('data', (d) => (out += d.toString()))
      child.on('error', () => resolvePromise(undefined))
      child.on('close', () => {
        const firstLine = out.split(/\r?\n/).find((l) => l.trim().length > 0)
        resolvePromise(firstLine?.trim())
      })
    } catch {
      resolvePromise(undefined)
    }
  })
}

export async function detectTools(): Promise<ToolStatus> {
  const settings = loadSettings()
  const adbPath = resolveBinary(ADB_NAME, settings.adbPath)
  const scrcpyPath = resolveBinary(SCRCPY_NAME, settings.scrcpyPath)

  const [adbVersion, scrcpyVersion] = await Promise.all([
    adbPath ? runVersion(adbPath) : Promise.resolve(undefined),
    scrcpyPath ? runVersion(scrcpyPath) : Promise.resolve(undefined)
  ])

  return {
    adbPath,
    scrcpyPath,
    adbFound: !!adbPath,
    scrcpyFound: !!scrcpyPath,
    adbVersion,
    scrcpyVersion
  }
}

export function binaryNames(): { adb: string; scrcpy: string } {
  return { adb: ADB_NAME, scrcpy: SCRCPY_NAME }
}
