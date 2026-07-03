import React, { useState, useCallback } from 'react';
import { useStore } from '@/store/store';
import { api } from '@/lib/api';
import type { QueueItem } from '@shared/types';

const COLUMNS = [
  '#', 'Filename', 'Duration', 'Type', 'Key/Major', 'Sample Rate / Bits',
  'Loudness', 'True Peak', 'Channels', 'Status',
];

interface MenuState { x: number; y: number; item?: QueueItem }

const StatusPill: React.FC<{ item: QueueItem }> = ({ item }) => {
  const color: Record<string, string> = {
    Idle: 'text-slate-500', Queued: 'text-amber-400', Processing: 'text-accent-soft',
    Done: 'text-green-400', Error: 'text-red-400', Paused: 'text-slate-400',
  };
  if (item.status === 'Processing') {
    return (
      <div className="flex items-center gap-2">
        <div className="w-16 h-1 bg-slate-700 rounded overflow-hidden">
          <div className="h-full bg-accent" style={{ width: `${Math.round(item.progress * 100)}%` }} />
        </div>
        <span className="text-[10px] text-accent-soft">{item.stage}</span>
      </div>
    );
  }
  return <span className={`text-[11px] ${color[item.status] || 'text-slate-500'}`}>{item.status}</span>;
};

export const BatchQueue: React.FC = () => {
  const {
    queue, selected, toggleSelect, selectAll, removeSelected, clearAll,
    addPaths, exporting, startExport, stopExport, lastOutDir,
  } = useStore();
  const [menu, setMenu] = useState<MenuState | null>(null);

  const onContext = useCallback((e: React.MouseEvent, item?: QueueItem) => {
    e.preventDefault();
    if (item) toggleSelect(item.id, false);
    setMenu({ x: e.clientX, y: e.clientY, item });
  }, [toggleSelect]);

  const closeMenu = () => setMenu(null);

  const doAddFiles = async () => { const p = await api.addFiles(); if (p.length) addPaths(p); };
  const doAddFolder = async () => { const p = await api.addFolder(); if (p.length) addPaths(p); };
  const analyzeOne = async (item?: QueueItem) => {
    if (!item) return;
    const meta = await api.analyze(item.path);
    useStore.setState((s) => ({ queue: s.queue.map((q) => (q.id === item.id ? { ...q, meta } : q)) }));
  };

  const menuItems = [
    { label: 'Select all', fn: selectAll },
    { label: 'Add files…', fn: doAddFiles },
    { label: 'Add folder…', fn: doAddFolder },
    { label: 'Remove selected', fn: removeSelected, disabled: selected.size === 0 },
    { label: 'Clear all', fn: clearAll, disabled: queue.length === 0 },
    { sep: true },
    { label: 'Analyze file', fn: () => analyzeOne(menu?.item), disabled: !menu?.item },
    { label: exporting ? 'Stop export' : 'Start export', fn: exporting ? stopExport : startExport, disabled: queue.length === 0 },
    { label: 'Open output folder', fn: () => lastOutDir && api.openOutput(lastOutDir), disabled: !lastOutDir },
  ];

  return (
    <div className="flex flex-col h-full" onClick={closeMenu}>
      <div className="flex items-center justify-between px-3 py-1.5">
        <span className="text-[11px] uppercase tracking-widest text-slate-400">Batch Queue</span>
        <div className="flex items-center gap-2 no-drag">
          <button onClick={doAddFiles} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300">+ Files</button>
          <button onClick={doAddFolder} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300">+ Folder</button>
          <button
            onClick={exporting ? stopExport : startExport}
            disabled={queue.length === 0}
            className={`px-3 py-1 text-[11px] rounded font-medium disabled:opacity-40 ${exporting ? 'bg-red-600/80 hover:bg-red-500' : 'bg-accent hover:bg-accent-soft'} text-white`}
          >
            {exporting ? 'Stop' : 'Start Export'}
          </button>
        </div>
      </div>

      <div
        className="flex-1 mx-3 mb-2 rounded-lg border border-slate-800 bg-slate-900/50 overflow-auto"
        onContextMenu={(e) => onContext(e)}
      >
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-slate-850 text-slate-400">
            <tr>
              {COLUMNS.map((c) => (
                <th key={c} className="text-left font-medium px-3 py-2 whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {queue.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="px-3 py-10 text-center text-slate-600">
                  Drop audio here, or use “+ Files” / “+ Folder”. Right-click for the menu.
                </td>
              </tr>
            )}
            {queue.map((it, i) => {
              const m = it.meta;
              const isSel = selected.has(it.id);
              return (
                <tr
                  key={it.id}
                  onClick={(e) => toggleSelect(it.id, e.metaKey || e.ctrlKey)}
                  onContextMenu={(e) => onContext(e, it)}
                  className={`border-t border-slate-800/60 cursor-pointer ${isSel ? 'bg-accent-dim/40' : 'hover:bg-slate-800/40'}`}
                >
                  <td className="px-3 py-1.5 text-slate-500">{i + 1}</td>
                  <td className="px-3 py-1.5 text-slate-200 max-w-[220px] truncate" title={it.filename}>{it.filename}</td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.duration_str ?? '—'}</td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.type ?? '—'}</td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.key ?? '—'}</td>
                  <td className="px-3 py-1.5 text-slate-400">
                    {m ? `${(m.sample_rate / 1000).toFixed(1)}k / ${m.bit_depth ?? '—'}bit` : '—'}
                  </td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.loudness_lufs != null ? `${m.loudness_lufs} LUFS` : '—'}</td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.true_peak_dbtp != null ? `${m.true_peak_dbtp} dB` : '—'}</td>
                  <td className="px-3 py-1.5 text-slate-400">{m?.channel_label ?? '—'}</td>
                  <td className="px-3 py-1.5"><StatusPill item={it} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {menu && (
        <div
          className="fixed z-50 min-w-[180px] py-1 rounded-md border border-slate-700 bg-slate-850 shadow-xl text-[12px]"
          style={{ left: menu.x, top: menu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          {menuItems.map((mi, idx) =>
            'sep' in mi ? (
              <div key={idx} className="my-1 border-t border-slate-700" />
            ) : (
              <button
                key={idx}
                disabled={(mi as any).disabled}
                onClick={() => { (mi as any).fn(); closeMenu(); }}
                className="block w-full text-left px-3 py-1.5 text-slate-300 hover:bg-accent-dim/60 disabled:opacity-40 disabled:hover:bg-transparent"
              >
                {(mi as any).label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
};
