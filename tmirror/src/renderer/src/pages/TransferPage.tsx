import { useEffect, useState } from 'react'
import { TopBar } from '../components/TopBar'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { useDevices } from '../state/useDevices'
import { useI18n } from '../i18n/I18nContext'
import { useToast } from '../state/ToastContext'
import type { FileEntry } from '@shared/types'

const REMOTE_FOLDERS = [
  { key: 'download', path: '/sdcard/Download' },
  { key: 'pictures', path: '/sdcard/Pictures' }
] as const

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function TransferPage(): JSX.Element {
  const { devices } = useDevices()
  const { t } = useI18n()
  const { push } = useToast()
  const readyDevices = devices.filter((d) => d.status === 'ready')
  const [serial, setSerial] = useState<string>('')
  const [folderKey, setFolderKey] = useState<(typeof REMOTE_FOLDERS)[number]['key']>('download')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (readyDevices.length > 0 && !readyDevices.some((d) => d.serial === serial)) {
      setSerial(readyDevices[0].serial)
    }
    if (readyDevices.length === 0) setSerial('')
  }, [readyDevices, serial])

  const folderPath = REMOTE_FOLDERS.find((f) => f.key === folderKey)?.path ?? '/sdcard/Download'

  async function refreshEntries(): Promise<void> {
    if (!serial) return
    const list = await window.tmirror.transfer.listRemote(serial, folderPath)
    setEntries(list)
  }

  useEffect(() => {
    refreshEntries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serial, folderPath])

  async function handlePull(entry: FileEntry): Promise<void> {
    const dir = await window.tmirror.dialog.pickDirectory()
    if (!dir) return
    const result = await window.tmirror.transfer.pull(serial, entry.path, dir)
    push(result.ok ? t.toast.pullSuccess : result.message ?? t.toast.pullFail, result.ok ? 'success' : 'error')
  }

  async function pushLocalPaths(paths: string[]): Promise<void> {
    if (!serial || paths.length === 0) return
    setBusy(true)
    for (const path of paths) {
      const isApk = path.toLowerCase().endsWith('.apk')
      const result = isApk
        ? await window.tmirror.transfer.installApk(serial, path)
        : await window.tmirror.transfer.push(serial, path, folderPath)
      push(
        result.ok ? (isApk ? t.toast.installSuccess : t.toast.pushSuccess) : result.message ?? t.toast.pushFail,
        result.ok ? 'success' : 'error'
      )
    }
    setBusy(false)
    refreshEntries()
  }

  async function handleBrowse(): Promise<void> {
    const paths = await window.tmirror.dialog.pickFiles()
    await pushLocalPaths(paths)
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>): Promise<void> {
    e.preventDefault()
    setIsDragOver(false)
    const paths = Array.from(e.dataTransfer.files).map((f) => window.tmirror.getPathForFile(f))
    await pushLocalPaths(paths)
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <TopBar title={t.transfer.title} subtitle={t.transfer.subtitle} />
      <div className="flex flex-1 flex-col gap-4 overflow-hidden px-8 py-6">
        <select
          value={serial}
          onChange={(e) => setSerial(e.target.value)}
          className="w-fit rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm"
        >
          {readyDevices.length === 0 && <option value="">{t.transfer.noDevice}</option>}
          {readyDevices.map((d) => (
            <option key={d.serial} value={d.serial}>
              {d.model ?? d.serial}
            </option>
          ))}
        </select>

        {!serial ? (
          <EmptyState icon="📁" title={t.transfer.selectDevice} />
        ) : (
          <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden md:grid-cols-2">
            <Card
              className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed text-center transition ${
                isDragOver ? 'border-teal-400 bg-teal-50' : 'border-ink-200'
              }`}
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragOver(true)
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
            >
              <p className="text-sm font-semibold text-ink-800">{t.transfer.thisPc}</p>
              <p className="text-xs text-ink-500">{t.transfer.dropHint}</p>
              <button
                type="button"
                disabled={busy}
                onClick={handleBrowse}
                className="rounded-lg bg-coral-500 px-4 py-2 text-sm font-semibold text-white hover:bg-coral-600 disabled:opacity-50"
              >
                {t.common.browse}
              </button>
            </Card>

            <Card className="flex flex-col overflow-hidden">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex gap-1 rounded-lg bg-ink-100 p-1 text-xs font-medium">
                  {REMOTE_FOLDERS.map((f) => (
                    <button
                      key={f.key}
                      type="button"
                      onClick={() => setFolderKey(f.key)}
                      className={`rounded-md px-2.5 py-1 ${
                        folderKey === f.key ? 'bg-white shadow-sm text-ink-900' : 'text-ink-500'
                      }`}
                    >
                      {f.key === 'download' ? t.transfer.phoneDownloads : t.transfer.phonePictures}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={refreshEntries}
                  className="rounded-lg bg-ink-100 px-2.5 py-1 text-xs font-medium text-ink-700 hover:bg-ink-200"
                >
                  {t.common.refresh}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {entries.length === 0 ? (
                  <p className="py-8 text-center text-xs text-ink-400">{t.transfer.empty}</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {entries.map((entry) => (
                      <li
                        key={entry.path}
                        className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-ink-50"
                      >
                        <span className="truncate text-sm text-ink-700">{entry.name}</span>
                        <div className="flex shrink-0 items-center gap-2">
                          {!entry.isDirectory && <span className="text-xs text-ink-400">{formatSize(entry.size)}</span>}
                          {!entry.isDirectory && (
                            <button
                              type="button"
                              onClick={() => handlePull(entry)}
                              className="rounded-md bg-teal-500 px-2 py-1 text-xs font-semibold text-white hover:bg-teal-600"
                            >
                              {t.transfer.pull}
                            </button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
