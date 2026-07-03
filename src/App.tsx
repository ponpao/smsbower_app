import { useEffect, useState } from 'react';
import { TitleBar } from './components/TitleBar';
import { BatchQueue } from './components/BatchQueue';
import { SettingConsole } from './components/SettingConsole';
import { TransportBar } from './components/TransportBar';
import { StatusBar } from './components/StatusBar';
import { ExportModal } from './components/ExportModal';
import { ReleaseCheckModal } from './components/ReleaseCheckModal';
import { AuthenticityModal } from './components/AuthenticityModal';
import { FirstRunNotice } from './components/FirstRunNotice';
import { useStore, bindIpc } from './store/store';

export default function App() {
  const { loadInitial, firstRunAck, addPaths, startExport, setPlaying, playing } = useStore();
  const [modal, setModal] = useState<null | 'export' | 'release' | 'ai'>(null);

  useEffect(() => {
    bindIpc();
    loadInitial();
  }, []);

  // Keyboard shortcuts: Space = play/pause, Cmd/Ctrl+E = export.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.code === 'Space') { e.preventDefault(); setPlaying(!playing); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'e') { e.preventDefault(); startExport(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [playing, startExport, setPlaying]);

  // Drag & drop audio files anywhere onto the window.
  useEffect(() => {
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      const paths: string[] = [];
      for (const f of Array.from(e.dataTransfer?.files || [])) {
        const p = (f as any).path as string | undefined;
        if (p) paths.push(p);
      }
      if (paths.length) addPaths(paths);
    };
    const prevent = (e: DragEvent) => e.preventDefault();
    window.addEventListener('dragover', prevent);
    window.addEventListener('drop', onDrop);
    return () => {
      window.removeEventListener('dragover', prevent);
      window.removeEventListener('drop', onDrop);
    };
  }, [addPaths]);

  return (
    <div className="flex flex-col h-full">
      <TitleBar />
      <div className="flex flex-col flex-1 min-h-0">
        <div className="h-[38%] min-h-[180px] flex flex-col">
          <BatchQueue />
        </div>
        <div className="flex-1 min-h-0 overflow-auto">
          <SettingConsole
            onOpenExport={() => setModal('export')}
            onAnalyzeAi={() => setModal('ai')}
          />
        </div>
      </div>
      <TransportBar onOpenRelease={() => setModal('release')} />
      <StatusBar />

      {modal === 'export' && <ExportModal onClose={() => setModal(null)} />}
      {modal === 'release' && <ReleaseCheckModal onClose={() => setModal(null)} />}
      {modal === 'ai' && <AuthenticityModal onClose={() => setModal(null)} />}
      {!firstRunAck && <FirstRunNotice />}
    </div>
  );
}
