import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/store/store';

export const StatusBar: React.FC = () => {
  const [stats, setStats] = useState({ cpu: 0, ram: 0 });
  const exporting = useStore((s) => s.exporting);
  const queue = useStore((s) => s.queue);

  useEffect(() => {
    const t = setInterval(async () => {
      try { setStats(await api.sysStats()); } catch { /* ignore */ }
    }, 1500);
    return () => clearInterval(t);
  }, []);

  const done = queue.filter((q) => q.status === 'Done').length;
  const status = exporting ? 'Processing' : queue.length ? 'Ready' : 'Idle';

  return (
    <div className="flex items-center justify-between h-6 px-3 bg-slate-950 border-t border-slate-800 text-[10px] text-slate-500">
      <div className="flex items-center gap-3">
        <span>
          Status: <span className={exporting ? 'text-accent-soft processing-pulse' : 'text-slate-300'}>{status}</span>
        </span>
        {queue.length > 0 && (
          <span>Queue: <span className="text-slate-300">{done}/{queue.length}</span></span>
        )}
        <span className="text-slate-600">All processing runs locally</span>
      </div>
      <div className="flex items-center gap-4 font-mono">
        <span>CPU: <span className="text-slate-300">{stats.cpu}%</span></span>
        <span>RAM: <span className="text-slate-300">{stats.ram}%</span></span>
      </div>
    </div>
  );
};
