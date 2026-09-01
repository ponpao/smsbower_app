import { app } from 'electron'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Settings } from '../shared/types'

const DEFAULTS: Settings = {
  language: 'en',
  adbPath: null,
  scrcpyPath: null,
  accent: 'coral'
}

function settingsFile(): string {
  const dir = app.getPath('userData')
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
  return join(dir, 'tmirror-settings.json')
}

export function loadSettings(): Settings {
  try {
    const raw = readFileSync(settingsFile(), 'utf-8')
    const parsed = JSON.parse(raw)
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

export function saveSettings(settings: Settings): void {
  writeFileSync(settingsFile(), JSON.stringify(settings, null, 2), 'utf-8')
}
