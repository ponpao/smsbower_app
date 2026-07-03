import React from 'react';
import { useStore } from '@/store/store';

// Transport: play/next, Effect (A/B: processed vs original preview), waveform
// scrubber, volume. Audio preview is wired through the store; the waveform is a
// lightweight placeholder rendering that scrubs position.
export const TransportBar: React.FC<{ onOpenRelease: () => void }> = ({ onOpenRelease }) => {
  const { playing, setPlaying, effectOn, setEffectOn, queue, currentId } = useStore();
  const current = queue.find((q) => q.id === currentId) || queue[0];
  const [pos, setPos] = React.useState(0);
  const [vol, setVol] = React.useState(0.8);

  const dur = current?.meta?.duration ?? 0;
  const fmt = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex items-center gap-4 h-14 px-4 bg-slate-950 border-t border-slate-800 no-drag">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setPlaying(!playing)}
          className="w-9 h-9 rounded-full bg-accent hover:bg-accent-soft text-white flex items-center justify-center text-sm"
          title="Play / Pause (Space)"
        >{playing ? '❚❚' : '▶'}</button>
        <button className="w-7 h-7 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center text-xs" title="Next">⏭</button>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-[11px] text-slate-400">Effect</span>
        <button
          onClick={() => setEffectOn(!effectOn)}
          className={`w-9 h-4 rounded-full transition-colors ${effectOn ? 'bg-accent' : 'bg-slate-600'}`}
          title="A/B: processed vs original"
        >
          <span className={`block w-3.5 h-3.5 bg-white rounded-full transition-transform ${effectOn ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </button>
        <span className="text-[10px] text-slate-500 w-14">{effectOn ? 'Processed' : 'Original'}</span>
      </div>

      <span className="text-[10px] font-mono text-slate-500 w-9 text-right">{fmt(pos * dur)}</span>
      <div className="flex-1 relative h-8 flex items-center">
        {/* Placeholder waveform bars behind the scrubber. */}
        <div className="absolute inset-0 flex items-center gap-[2px] px-0.5 pointer-events-none">
          {Array.from({ length: 90 }).map((_, i) => {
            const h = 6 + Math.abs(Math.sin(i * 0.7) * Math.cos(i * 0.29)) * 22;
            const active = i / 90 < pos;
            return <div key={i} className={`w-full rounded-sm ${active ? 'bg-accent/70' : 'bg-slate-700'}`} style={{ height: h }} />;
          })}
        </div>
        <input
          type="range" min={0} max={1} step={0.001} value={pos}
          onChange={(e) => setPos(parseFloat(e.target.value))}
          className="w-full accent-accent relative z-10 opacity-0 cursor-pointer h-8"
          title="Scrub"
        />
      </div>
      <span className="text-[10px] font-mono text-slate-500 w-9">{fmt(dur)}</span>

      <div className="flex items-center gap-2">
        <span className="text-slate-500 text-xs">🔊</span>
        <input type="range" min={0} max={1} step={0.01} value={vol} onChange={(e) => setVol(parseFloat(e.target.value))} className="w-20 accent-accent" title="Volume" />
      </div>

      <button onClick={onOpenRelease} className="px-3 py-1.5 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700">
        Release Check
      </button>
    </div>
  );
};
