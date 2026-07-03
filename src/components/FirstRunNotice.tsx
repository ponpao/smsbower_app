import React from 'react';
import { Modal } from './Modal';
import { useStore } from '@/store/store';

export const FirstRunNotice: React.FC = () => {
  const ackFirstRun = useStore((s) => s.ackFirstRun);
  return (
    <Modal title="Welcome to TRAVKOD" onClose={ackFirstRun} width={460}>
      <p className="text-[13px] text-slate-300 leading-relaxed">
        TRAVKOD improves audio quality — it makes finished tracks warmer, less brittle and
        release-ready, then batch-exports them.
      </p>
      <p className="text-[13px] text-slate-300 leading-relaxed mt-3">
        <span className="text-accent-soft font-medium">If your track uses AI, disclose it</span> where
        your distributor requires. TRAVKOD does not help you hide AI use or defeat any detection —
        the Authenticity Report is an experimental, informational estimate only.
      </p>
      <p className="text-[11px] text-slate-500 leading-relaxed mt-3">
        All processing runs locally on your machine by default. Nothing is uploaded.
      </p>
      <div className="flex justify-end mt-4">
        <button onClick={ackFirstRun} className="px-4 py-1.5 text-[12px] rounded bg-accent hover:bg-accent-soft text-white font-medium">
          Got it
        </button>
      </div>
    </Modal>
  );
};
