import React from 'react';

export const Modal: React.FC<{
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  width?: number;
}> = ({ title, onClose, children, width = 480 }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
    <div
      className="rounded-xl border border-slate-700 bg-slate-900 shadow-2xl no-drag"
      style={{ width }}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-[13px] font-semibold text-slate-200">{title}</h2>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-sm">✕</button>
      </div>
      <div className="p-4">{children}</div>
    </div>
  </div>
);
