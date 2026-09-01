import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ToastStack } from './components/Toast'
import { DevicesPage } from './pages/DevicesPage'
import { ConnectPage } from './pages/ConnectPage'
import { TransferPage } from './pages/TransferPage'
import { ClipboardPage } from './pages/ClipboardPage'
import { SettingsPage } from './pages/SettingsPage'

export type Page = 'devices' | 'connect' | 'transfer' | 'clipboard' | 'settings'

export default function App(): JSX.Element {
  const [page, setPage] = useState<Page>('devices')

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-ink-50">
      <Sidebar page={page} onNavigate={setPage} />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {page === 'devices' && <DevicesPage onNavigate={setPage} />}
        {page === 'connect' && <ConnectPage />}
        {page === 'transfer' && <TransferPage />}
        {page === 'clipboard' && <ClipboardPage />}
        {page === 'settings' && <SettingsPage />}
      </main>
      <ToastStack />
    </div>
  )
}
