import React, { useEffect, useState } from 'react';
import { Modal } from './Modal';
import { useStore } from '@/store/store';
import { api } from '@/lib/api';
import type { AuthenticityReport } from '@shared/types';

export const AuthenticityModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { queue, currentId, markAi } = useStore();
  const item = queue.find((q) => q.id === currentId) || queue[0];
  const [rep, setRep] = useState<AuthenticityReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (!item) { setLoading(false); return; }
      try { setRep(await api.authenticity(item.path)); } finally { setLoading(false); }
    })();
  }, [item?.path]);

  const pct = rep ? Math.round(rep.p_ai * 100) : 0;
  const lo = rep ? Math.round(rep.ci_low * 100) : 0;
  const hi = rep ? Math.round(rep.ci_high * 100) : 0;

  return (
    <Modal title="Authenticity Report" onClose={onClose} width={520}>
      <div className="flex items-center gap-2 mb-3">
        <span className="px-2 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
          BETA — experimental, may be wrong
        </span>
      </div>

      {loading && <p className="text-[12px] text-slate-400">Analyzing…</p>}
      {!item && <p className="text-[12px] text-slate-400">Select a track first.</p>}

      {rep && (
        <div>
          <div className="text-[12px] text-slate-400 mb-1">Estimated probability this track is AI-generated</div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-semibold text-slate-100">~{pct}%</span>
            <span className="text-[12px] text-slate-500">range {lo}–{hi}% · {rep.confidence_label}</span>
          </div>

          {/* Confidence interval bar (never a single certain number). */}
          <div className="relative h-3 mt-3 rounded bg-slate-800 overflow-hidden">
            <div className="absolute h-full bg-accent/30" style={{ left: `${lo}%`, width: `${Math.max(2, hi - lo)}%` }} />
            <div className="absolute h-full w-[2px] bg-accent-soft" style={{ left: `${pct}%` }} />
          </div>
          <div className="flex justify-between text-[9px] text-slate-600 mt-1"><span>0% (human)</span><span>100% (AI)</span></div>

          <p className="mt-4 text-[12px] text-slate-300">{rep.note}</p>
          <p className="mt-2 text-[10px] text-slate-500 leading-relaxed">{rep.disclaimer}</p>

          <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
            <span className="text-[11px] text-slate-400">Mark this source as AI-generated?</span>
            <button
              onClick={() => item && markAi(item.id, !item.isAi)}
              className={`px-3 py-1 text-[11px] rounded ${item?.isAi ? 'bg-accent text-white' : 'bg-slate-800 text-slate-300'}`}
            >{item?.isAi ? 'Marked AI ✓' : 'Mark as AI'}</button>
          </div>
          <p className="mt-2 text-[10px] text-slate-500">
            Marking a source AI-generated turns on the disclosure reminder in the Release Check —
            so you disclose where your distributor requires it.
          </p>
        </div>
      )}
    </Modal>
  );
};
