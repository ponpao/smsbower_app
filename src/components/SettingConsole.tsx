import React, { useState } from 'react';
import { useStore } from '@/store/store';
import { VerticalSlider } from './VerticalSlider';
import { STRIP_CONTROLS, EQ_LABELS } from '@/lib/defaults';
import { EQ_BANDS } from '@shared/types';

const QUICK_EQ = [
  { name: 'Flat', eq: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
  { name: 'vocalBoost', eq: [0, 0, -1, 0, 1, 2, 2, 1, 1, 0] },
  { name: 'assBass', eq: [3, 3, 2, 1, 0, 0, 0, 0, 0, 0] },
  { name: 'Bright', eq: [0, 0, 0, 0, 0, 0, 1, 2, 3, 3] },
  { name: 'Warm', eq: [2, 2, 1, 0, 0, -1, -1, -2, -2, -1] },
  { name: 'AI Tw', eq: [0, 0, 0, 0, -1, -2, -2, -1, 0, 1] },
  { name: 'Hip-Hop', eq: [3, 2, 1, 0, -1, 0, 1, 1, 1, 1] },
  { name: 'Pop', eq: [1, 1, 0, 0, 0, 1, 1, 2, 2, 1] },
  { name: 'R&B', eq: [2, 2, 1, 0, 0, 0, 0, 1, 1, 0] },
  { name: 'Rock', eq: [1, 1, 1, 1, 1, 1, 1, 1, 0, 0] },
  { name: 'Lo-Fi', eq: [2, 1, 0, 0, -1, -2, -3, -4, -5, -6] },
];

export const SettingConsole: React.FC<{ onOpenExport: () => void; onAnalyzeAi: () => void }> = ({
  onOpenExport, onAnalyzeAi,
}) => {
  const {
    params, setStrip, setEq, templates, template, applyTemplate,
    humanizeOn, setHumanizeOn, autoIntensity, setAutoIntensity,
    presets, savePreset, applyPreset, deletePreset,
  } = useStore();
  const [showPresets, setShowPresets] = useState(false);
  const [showQuickEq, setShowQuickEq] = useState(false);
  const templateNames = ['Default', ...Object.keys(templates).filter((t) => t !== 'Default')];

  const savePresetPrompt = async () => {
    const name = window.prompt('Preset name');
    if (name) { await savePreset(name); setShowPresets(false); }
  };

  return (
    <div className="flex flex-col mx-3 mb-2 rounded-lg border border-slate-800 bg-slate-900/50">
      {/* Header row: template / presets / quick eq / humanize toggle / analyze */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800">
        <div className="flex items-center gap-2 no-drag">
          <span className="text-[11px] text-slate-400">Template</span>
          <select
            value={template === 'Custom' ? 'Custom' : template}
            onChange={(e) => applyTemplate(e.target.value)}
            className="bg-slate-800 text-slate-200 text-[11px] rounded px-2 py-1 outline-none border border-slate-700"
          >
            {template === 'Custom' && <option value="Custom">Custom</option>}
            {templateNames.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          <div className="relative">
            <button onClick={() => setShowPresets((v) => !v)} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300">Presets ▾</button>
            {showPresets && (
              <div className="absolute z-30 mt-1 min-w-[180px] py-1 rounded-md border border-slate-700 bg-slate-850 shadow-xl">
                <button onClick={savePresetPrompt} className="block w-full text-left px-3 py-1.5 text-[12px] text-accent-soft hover:bg-accent-dim/60">＋ Save current…</button>
                {presets.length === 0 && <div className="px-3 py-1.5 text-[11px] text-slate-500">No saved presets</div>}
                {presets.map((p) => (
                  <div key={p.name} className="flex items-center justify-between px-3 py-1.5 hover:bg-slate-800">
                    <button onClick={() => { applyPreset(p.name); setShowPresets(false); }} className="text-[12px] text-slate-300 flex-1 text-left">{p.name}</button>
                    <button onClick={() => deletePreset(p.name)} className="text-[11px] text-red-400/70 hover:text-red-400 ml-2">✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="relative">
            <button onClick={() => setShowQuickEq((v) => !v)} className="px-2 py-1 text-[11px] rounded bg-accent/80 hover:bg-accent text-white">Quick EQ ◂</button>
            {showQuickEq && (
              <div className="absolute z-30 mt-1 grid grid-cols-2 gap-1 p-2 rounded-md border border-slate-700 bg-slate-850 shadow-xl">
                {QUICK_EQ.map((q) => (
                  <button
                    key={q.name}
                    onClick={() => { q.eq.forEach((v, i) => setEq(i, v)); setShowQuickEq(false); }}
                    className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-accent-dim text-slate-300 whitespace-nowrap"
                  >{q.name}</button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 no-drag">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-850 border border-slate-700">
            <span className="text-[11px] text-slate-300">Humanize &amp; Master</span>
            <button
              onClick={() => setHumanizeOn(!humanizeOn)}
              className={`w-9 h-4 rounded-full transition-colors ${humanizeOn ? 'bg-accent' : 'bg-slate-600'}`}
            >
              <span className={`block w-3.5 h-3.5 bg-white rounded-full transition-transform ${humanizeOn ? 'translate-x-5' : 'translate-x-0.5'}`} />
            </button>
            <button
              onClick={() => setAutoIntensity(!autoIntensity)}
              className={`text-[10px] px-2 py-0.5 rounded ${autoIntensity ? 'bg-accent-dim text-accent-soft' : 'bg-slate-800 text-slate-400'}`}
            >{autoIntensity ? 'Auto' : 'Manual'}</button>
          </div>
          <button onClick={onAnalyzeAi} className="px-2.5 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">☆ Analyze AI</button>
          <button onClick={onOpenExport} className="px-2.5 py-1 text-[11px] rounded bg-accent hover:bg-accent-soft text-white">Export…</button>
        </div>
      </div>

      {/* Console body: mastering strip (left) + EQ (right) */}
      <div className="flex gap-3 p-3">
        {/* STEALTH / mastering strip */}
        <div className={`flex-1 rounded-lg bg-slate-950/40 border border-slate-800 p-3 ${humanizeOn ? '' : 'opacity-50'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-widest text-accent-soft">Mastering Strip</span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500">Humanize</span>
              <input
                type="range" min={0} max={100} step={1}
                value={params.humanize}
                onChange={(e) => useStore.getState().setHumanize(parseFloat(e.target.value))}
                className="w-28 accent-accent no-drag"
              />
              <span className="text-[10px] font-mono text-accent-soft w-8">{Math.round(params.humanize)}%</span>
            </div>
          </div>
          <div className="flex gap-1 justify-between overflow-x-auto pb-1">
            {STRIP_CONTROLS.map((c) => (
              <VerticalSlider
                key={String(c.key)}
                label={c.label}
                unit={c.unit}
                min={c.min}
                max={c.max}
                step={c.step}
                value={params.strip[c.key] as number}
                disabled={!humanizeOn}
                onChange={(v) => setStrip(c.key, v)}
              />
            ))}
          </div>
        </div>

        {/* 10-band EQ */}
        <div className="w-[380px] rounded-lg bg-slate-950/40 border border-slate-800 p-3">
          <span className="text-[10px] uppercase tracking-widest text-accent-soft">EQ · 10-band</span>
          <div className="flex gap-1 justify-between mt-2">
            {EQ_BANDS.map((_, i) => (
              <VerticalSlider
                key={i}
                label={EQ_LABELS[i]}
                unit="dB"
                min={-12}
                max={12}
                step={0.5}
                value={params.eq[i]}
                onChange={(v) => setEq(i, v)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
