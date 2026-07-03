import React, { useEffect, useState } from 'react';
import { Modal } from './Modal';
import { useStore } from '@/store/store';
import { api } from '@/lib/api';
import type { ReleaseCheck } from '@shared/types';

export const ReleaseCheckModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { queue, currentId, exportSettings } = useStore();
  const item = queue.find((q) => q.id === currentId) || queue[0];
  const [check, setCheck] = useState<ReleaseCheck | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (!item?.meta) { setLoading(false); return; }
      const res = await api.releaseCheck({
        meta: item.meta,
        lufs_target: exportSettings.lufs_target,
        is_ai: !!item.isAi,
        has_metadata: true,
      });
      setCheck(res);
      setLoading(false);
    })();
  }, [item, exportSettings.lufs_target]);

  return (
    <Modal title="Release Readiness Check" onClose={onClose} width={520}>
      {!item?.meta && <p className="text-[12px] text-slate-400">Select and analyze a track first.</p>}
      {loading && item?.meta && <p className="text-[12px] text-slate-400">Checking…</p>}
      {check && (
        <div>
          <div className={`text-[13px] mb-3 ${check.passed ? 'text-green-400' : 'text-amber-400'}`}>
            {check.passed ? '✓ ' : '⚠ '}{check.summary}
          </div>
          <ul className="space-y-1.5">
            {check.items.map((it, i) => (
              <li key={i} className="flex items-start gap-2 text-[12px]">
                <span className={it.status === 'pass' ? 'text-green-400' : 'text-amber-400'}>
                  {it.status === 'pass' ? '✓' : '⚠'}
                </span>
                <div>
                  <span className="text-slate-200">{it.name}</span>
                  <span className="text-slate-500"> — {it.detail}</span>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[10px] text-slate-500 leading-relaxed border-t border-slate-800 pt-3">
            This checklist reports objective facts about your master. It never tells you how to
            “pass” a distributor check. Where a release requires AI disclosure, disclose it.
          </p>
        </div>
      )}
    </Modal>
  );
};
