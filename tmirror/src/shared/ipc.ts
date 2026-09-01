// Canonical IPC channel names shared between main, preload and renderer.
export const IPC = {
  devicesList: 'devices:list',
  devicesStartMirror: 'devices:startMirror',
  devicesStopMirror: 'devices:stopMirror',
  devicesArrange: 'devices:arrange',
  devicesCloseAllMirrors: 'devices:closeAllMirrors',
  devicesScreenshot: 'devices:screenshot',
  devicesStartRecording: 'devices:startRecording',
  devicesStopRecording: 'devices:stopRecording',
  devicesUninstall: 'devices:uninstall',
  devicesEnableWifi: 'devices:enableWifi',
  devicesConnectTcp: 'devices:connectTcp',

  transferInstallApk: 'transfer:installApk',
  transferPush: 'transfer:push',
  transferPull: 'transfer:pull',
  transferListRemote: 'transfer:listRemote',
  transferProgress: 'transfer:progress',

  clipboardReadPc: 'clipboard:readPc',
  clipboardWritePc: 'clipboard:writePc',
  clipboardSendToDevice: 'clipboard:sendToDevice',

  pairCreateSession: 'pair:createSession',
  pairCancelSession: 'pair:cancelSession',
  pairStatus: 'pair:status',

  toolsDetect: 'tools:detect',
  toolsPickFolder: 'tools:pickFolder',

  settingsGet: 'settings:get',
  settingsSet: 'settings:set',

  dialogPickFiles: 'dialog:pickFiles',
  dialogPickDirectory: 'dialog:pickDirectory'
} as const
