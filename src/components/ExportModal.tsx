import React from 'react';
import { Modal } from './Modal';
import { useStore } from '@/store/store';
import { api } from '@/lib/api';
import type { ExportFormat } from '@shared/types';

const Row: React.FC<{ label: string; children: React.ReactNode; hint?: string }> = ({ label, children, hint }) => (
  <div className="flex items-center justify-between py-2">
    <div>
      <div className="text-[12px] text-slate-300">{label}</div>
      {hint && <div className="text-[10px] text-slate-500">{hint}</div>}
    </div>
    <div className="no-drag">{children}</div>
  </div>
);

const sel = 'bg-slate-800 text-slate-200 text-[12px] rounded px-2 py-1 border border-slate-700 outline-none';

export const ExportModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { exportSettings: ex, setExport, startExport } = useStore();

  const chooseFolder = async () => {
    const f = await api.chooseOutput();
    if (f) setExport({ output_folder: f });
  };

  const lufsValue = ex.lufs_target === null ? 'off' : String(ex.lufs_target);
  const setLufs = (v: string) => {
    if (v === 'off') setExport({ lufs_target: null });
    else if (v === 'custom') setExport({ lufs_target: -12 });
    else setExport({ lufs_target: parseFloat(v) });
  };

  return (
    <Modal title="Export Settings" onClose={onClose} width={460}>
      <Row label="Format">
        <select value={ex.format} onChange={(e) => setExport({ format: e.target.value as ExportFormat })} className={sel}>
          <option value="wav">WAV</option>
          <option value="flac">FLAC</option>
          <option value="mp3">MP3</option>
        </select>
      </Row>

      <Row label="Sample rate">
        <select
          value={ex.sample_rate ?? 'source'}
          onChange={(e) => setExport({ sample_rate: e.target.value === 'source' ? null : parseInt(e.target.value) })}
          className={sel}
        >
          <option value="source">Keep source</option>
          <option value="44100">44.1 kHz</option>
          <option value="48000">48 kHz</option>
          <option value="96000">96 kHz</option>
        </select>
      </Row>

      {ex.format !== 'mp3' && (
        <Row label="Bit depth">
          <select value={ex.bit_depth} onChange={(e) => setExport({ bit_depth: parseInt(e.target.value) })} className={sel}>
            <option value={16}>16-bit</option>
            <option value={24}>24-bit</option>
            <option value={32}>32-bit float</option>
          </select>
        </Row>
      )}
      {ex.format === 'mp3' && (
        <Row label="MP3 bitrate">
          <select value={ex.mp3_bitrate} onChange={(e) => setExport({ mp3_bitrate: parseInt(e.target.value) })} className={sel}>
            <option value={192}>192 kbps</option>
            <option value={256}>256 kbps</option>
            <option value={320}>320 kbps</option>
          </select>
        </Row>
      )}

      <Row label="Threads" hint="Parallel worker processes (1–8)">
        <input
          type="number" min={1} max={8} value={ex.threads}
          onChange={(e) => setExport({ threads: Math.max(1, Math.min(8, parseInt(e.target.value) || 1)) })}
          className={`${sel} w-16`}
        />
      </Row>

      <Row label="Mastering target (LUFS)">
        <select value={lufsValue} onChange={(e) => setLufs(e.target.value)} className={sel}>
          <option value="off">Off</option>
          <option value="-14">-14 (streaming)</option>
          <option value="-9">-9 (loud)</option>
          <option value="custom">Custom…</option>
        </select>
      </Row>
      {ex.lufs_target !== null && ![-14, -9].includes(ex.lufs_target) && (
        <Row label="Custom LUFS">
          <input type="number" step={0.5} value={ex.lufs_target}
            onChange={(e) => setExport({ lufs_target: parseFloat(e.target.value) })}
            className={`${sel} w-20`} />
        </Row>
      )}

      <Row label="Autotune (vocal)" hint="Gentle correction, off by default">
        <button
          onClick={() => setExport({ autotune: !ex.autotune })}
          className={`w-9 h-4 rounded-full ${ex.autotune ? 'bg-accent' : 'bg-slate-600'}`}
        >
          <span className={`block w-3.5 h-3.5 bg-white rounded-full transition-transform ${ex.autotune ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </button>
      </Row>

      <Row label="Merge → one file" hint="Concatenate the batch into a single export">
        <button
          onClick={() => setExport({ merge: !ex.merge })}
          className={`w-9 h-4 rounded-full ${ex.merge ? 'bg-accent' : 'bg-slate-600'}`}
        >
          <span className={`block w-3.5 h-3.5 bg-white rounded-full transition-transform ${ex.merge ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </button>
      </Row>

      <Row label="Output folder" hint={ex.output_folder || 'Defaults to ~/TRAVKOD Exports'}>
        <button onClick={chooseFolder} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300">Choose…</button>
      </Row>

      <div className="flex justify-end gap-2 mt-3 pt-3 border-t border-slate-800">
        <button onClick={onClose} className="px-3 py-1.5 text-[12px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300">Close</button>
        <button
          onClick={() => { startExport(); onClose(); }}
          className="px-4 py-1.5 text-[12px] rounded bg-accent hover:bg-accent-soft text-white font-medium"
        >Start Export</button>
      </div>
    </Modal>
  );
};
