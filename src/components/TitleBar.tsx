import React from 'react';
import { api } from '@/lib/api';

export const TitleBar: React.FC = () => {
  return (
    <div className="titlebar-drag flex items-center justify-between h-9 px-3 bg-slate-950 border-b border-slate-800">
      <div className="flex items-center gap-2">
        <span className="text-accent text-sm">▚</span>
        <span className="text-slate-200 text-sm font-semibold tracking-[0.3em]">TRAVKOD</span>
        <span className="text-slate-600 text-[10px] ml-2">honest master &amp; humanize</span>
      </div>
      <div className="no-drag flex items-center gap-2">
        <button
          onClick={() => api.windowControl('minimize')}
          className="w-3 h-3 rounded-full bg-yellow-500/80 hover:bg-yellow-400"
          title="Minimize"
        />
        <button
          onClick={() => api.windowControl('maximize')}
          className="w-3 h-3 rounded-full bg-green-500/80 hover:bg-green-400"
          title="Maximize"
        />
        <button
          onClick={() => api.windowControl('close')}
          className="w-3 h-3 rounded-full bg-red-500/80 hover:bg-red-400"
          title="Close"
        />
      </div>
    </div>
  );
};
