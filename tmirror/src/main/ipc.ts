import { type BrowserWindow, dialog, ipcMain, clipboard } from 'electron'
import { randomUUID } from 'node:crypto'
import { basename } from 'node:path'
import * as adb from './adb'
import * as scrcpy from './scrcpy'
import { detectTools } from './binaries'
import { loadSettings, saveSettings } from './store'
import { cancelPairSession, createPairSession, setPairStatusListener } from './pairServer'
import { IPC } from '../shared/ipc'
import type { ArrangeMode, Settings } from '../shared/types'

function requireWindow(getMainWindow: () => BrowserWindow | null): BrowserWindow {
  const win = getMainWindow()
  if (!win) throw new Error('No window available')
  return win
}

export function registerIpcHandlers(getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle(IPC.devicesList, async () => {
    return adb.listDevices()
  })

  ipcMain.handle(IPC.devicesStartMirror, async (_e, serial: string, label: string) => {
    await scrcpy.startMirror(serial, label)
    return { ok: true }
  })

  ipcMain.handle(IPC.devicesStopMirror, async (_e, serial: string) => {
    scrcpy.stopMirror(serial)
    return { ok: true }
  })

  ipcMain.handle(IPC.devicesArrange, async (_e, mode: ArrangeMode, devices: { serial: string; label: string }[]) => {
    await scrcpy.arrangeMirrors(mode, devices)
    return { ok: true }
  })

  ipcMain.handle(IPC.devicesCloseAllMirrors, async () => {
    scrcpy.stopAllMirrors()
    return { ok: true }
  })

  ipcMain.handle(IPC.devicesScreenshot, async (_e, serial: string) => {
    const win = requireWindow(getMainWindow)
    const target = await dialog.showSaveDialog(win, {
      title: 'Save screenshot',
      defaultPath: `tmirror-screenshot-${Date.now()}.png`,
      filters: [{ name: 'PNG image', extensions: ['png'] }]
    })
    if (target.canceled || !target.filePath) return { ok: false, message: 'Cancelled' }
    return adb.screenshot(serial, target.filePath)
  })

  ipcMain.handle(IPC.devicesStartRecording, async (_e, serial: string, label: string) => {
    const path = await scrcpy.startRecording(serial, label)
    return { ok: true, message: path }
  })

  ipcMain.handle(IPC.devicesStopRecording, async (_e, serial: string) => {
    scrcpy.stopRecording(serial)
    return { ok: true }
  })

  ipcMain.handle(IPC.devicesUninstall, async (_e, serial: string, packageName: string) => {
    return adb.uninstallPackage(serial, packageName)
  })

  ipcMain.handle(IPC.devicesEnableWifi, async (_e, serial: string) => {
    const result = await adb.enableTcpIp(serial)
    if (!result.ok) return result
    const ip = await adb.getWifiIpAddress(serial)
    return { ok: true, message: ip ?? 'Enabled. Find the IP in phone Wi-Fi settings.' }
  })

  ipcMain.handle(IPC.devicesConnectTcp, async (_e, host: string, port: number) => {
    return adb.connectOverTcp(host, port)
  })

  ipcMain.handle(IPC.transferInstallApk, async (event, serial: string, apkPath: string) => {
    const id = randomUUID()
    event.sender.send(IPC.transferProgress, { id, serial, fileName: basename(apkPath), kind: 'install', status: 'starting' })
    const result = await adb.installApk(serial, apkPath)
    event.sender.send(IPC.transferProgress, {
      id,
      serial,
      fileName: basename(apkPath),
      kind: 'install',
      status: result.ok ? 'success' : 'error',
      message: result.message
    })
    return result
  })

  ipcMain.handle(IPC.transferPush, async (event, serial: string, localPath: string, remoteDir: string) => {
    const id = randomUUID()
    event.sender.send(IPC.transferProgress, { id, serial, fileName: basename(localPath), kind: 'push', status: 'starting' })
    const result = await adb.pushFile(serial, localPath, remoteDir)
    event.sender.send(IPC.transferProgress, {
      id,
      serial,
      fileName: basename(localPath),
      kind: 'push',
      status: result.ok ? 'success' : 'error',
      message: result.message
    })
    return result
  })

  ipcMain.handle(IPC.transferPull, async (event, serial: string, remotePath: string, localDir: string) => {
    const id = randomUUID()
    event.sender.send(IPC.transferProgress, { id, serial, fileName: basename(remotePath), kind: 'pull', status: 'starting' })
    const result = await adb.pullFile(serial, remotePath, localDir)
    event.sender.send(IPC.transferProgress, {
      id,
      serial,
      fileName: basename(remotePath),
      kind: 'pull',
      status: result.ok ? 'success' : 'error',
      message: result.message
    })
    return result
  })

  ipcMain.handle(IPC.transferListRemote, async (_e, serial: string, remoteDir: string) => {
    return adb.listRemoteDir(serial, remoteDir)
  })

  ipcMain.handle(IPC.clipboardReadPc, async () => {
    return { ok: true, text: clipboard.readText() }
  })

  ipcMain.handle(IPC.clipboardWritePc, async (_e, text: string) => {
    clipboard.writeText(text)
    return { ok: true }
  })

  ipcMain.handle(IPC.clipboardSendToDevice, async (_e, serial: string, text: string) => {
    return adb.sendTextToDevice(serial, text)
  })

  ipcMain.handle(IPC.pairCreateSession, async () => {
    return createPairSession()
  })

  ipcMain.handle(IPC.pairCancelSession, async () => {
    cancelPairSession()
    return { ok: true }
  })

  setPairStatusListener((evt) => {
    getMainWindow()?.webContents.send(IPC.pairStatus, evt)
  })

  ipcMain.handle(IPC.toolsDetect, async () => {
    return detectTools()
  })

  ipcMain.handle(IPC.toolsPickFolder, async () => {
    const win = requireWindow(getMainWindow)
    const result = await dialog.showOpenDialog(win, { properties: ['openDirectory'] })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  ipcMain.handle(IPC.settingsGet, async () => {
    return loadSettings()
  })

  ipcMain.handle(IPC.settingsSet, async (_e, settings: Settings) => {
    saveSettings(settings)
    return { ok: true }
  })

  ipcMain.handle(IPC.dialogPickFiles, async (_e, filters?: { name: string; extensions: string[] }[]) => {
    const win = requireWindow(getMainWindow)
    const result = await dialog.showOpenDialog(win, {
      properties: ['openFile', 'multiSelections'],
      filters
    })
    if (result.canceled) return []
    return result.filePaths
  })

  ipcMain.handle(IPC.dialogPickDirectory, async () => {
    const win = requireWindow(getMainWindow)
    const result = await dialog.showOpenDialog(win, { properties: ['openDirectory'] })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })
}
