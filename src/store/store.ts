import { create } from 'zustand';
import type {
  QueueItem, Params, ExportSettings, MasterStrip, Preset, FileMeta,
} from '@shared/types';
import { api } from '@/lib/api';
import { defaultParams, defaultExport, defaultStrip } from '@/lib/defaults';

let idCounter = 0;
const nextId = () => `job_${Date.now()}_${idCounter++}`;

interface State {
  queue: QueueItem[];
  selected: Set<string>;
  params: Params;
  exportSettings: ExportSettings;
  presets: Preset[];
  templates: Record<string, any>;
  humanizeOn: boolean; // "Humanize & Master" main toggle
  autoIntensity: boolean;
  template: string;
  firstRunAck: boolean;
  exporting: boolean;
  lastOutDir: string | null;

  // playback (A/B preview)
  playing: boolean;
  effectOn: boolean; // processed vs original preview
  currentId: string | null;

  // actions
  addPaths: (paths: string[]) => Promise<void>;
  removeSelected: () => void;
  clearAll: () => void;
  selectAll: () => void;
  toggleSelect: (id: string, multi: boolean) => void;
  setStrip: (k: keyof MasterStrip, v: number) => void;
  setEq: (i: number, v: number) => void;
  setHumanize: (v: number) => void;
  setParams: (p: Partial<Params>) => void;
  applyTemplate: (name: string) => void;
  setExport: (p: Partial<ExportSettings>) => void;
  setHumanizeOn: (v: boolean) => void;
  setAutoIntensity: (v: boolean) => void;
  ackFirstRun: () => void;
  markAi: (id: string, isAi: boolean) => void;

  startExport: () => Promise<void>;
  stopExport: () => Promise<void>;

  loadInitial: () => Promise<void>;
  savePreset: (name: string) => Promise<void>;
  deletePreset: (name: string) => Promise<void>;
  applyPreset: (name: string) => void;

  setPlaying: (v: boolean) => void;
  setEffectOn: (v: boolean) => void;
  setCurrent: (id: string | null) => void;

  _onStatus: (jobId: string, status: string, extra?: any) => void;
  _onProgress: (jobId: string, stage: string, frac: number) => void;
  _onResult: (jobId: string, result: any) => void;
}

export const useStore = create<State>((set, get) => ({
  queue: [],
  selected: new Set(),
  params: defaultParams(),
  exportSettings: defaultExport(),
  presets: [],
  templates: {},
  humanizeOn: true,
  autoIntensity: true,
  template: 'Default',
  firstRunAck: localStorage.getItem('tk_firstRunAck') === '1',
  exporting: false,
  lastOutDir: null,
  playing: false,
  effectOn: true,
  currentId: null,

  addPaths: async (paths) => {
    const existing = new Set(get().queue.map((q) => q.path));
    const fresh = paths.filter((p) => !existing.has(p));
    const items: QueueItem[] = fresh.map((p) => ({
      id: nextId(),
      path: p,
      filename: p.split(/[\\/]/).pop() || p,
      status: 'Idle',
      progress: 0,
    }));
    set((s) => ({ queue: [...s.queue, ...items] }));

    // Analyze each newly added file (metadata columns).
    for (const it of items) {
      try {
        const meta: FileMeta = await api.analyze(it.path);
        set((s) => ({
          queue: s.queue.map((q) => (q.id === it.id ? { ...q, meta } : q)),
        }));
      } catch (e: any) {
        set((s) => ({
          queue: s.queue.map((q) =>
            q.id === it.id ? { ...q, status: 'Error', error: String(e?.message || e) } : q,
          ),
        }));
      }
    }
  },

  removeSelected: () =>
    set((s) => ({
      queue: s.queue.filter((q) => !s.selected.has(q.id)),
      selected: new Set(),
    })),

  clearAll: () => set({ queue: [], selected: new Set(), currentId: null }),

  selectAll: () => set((s) => ({ selected: new Set(s.queue.map((q) => q.id)) })),

  toggleSelect: (id, multi) =>
    set((s) => {
      const sel = new Set(multi ? s.selected : []);
      if (sel.has(id) && multi) sel.delete(id);
      else sel.add(id);
      return { selected: sel, currentId: id };
    }),

  setStrip: (k, v) =>
    set((s) => ({ params: { ...s.params, strip: { ...s.params.strip, [k]: v } }, template: 'Custom' })),

  setEq: (i, v) =>
    set((s) => {
      const eq = s.params.eq.slice();
      eq[i] = v;
      return { params: { ...s.params, eq }, template: 'Custom' };
    }),

  setHumanize: (v) => set((s) => ({ params: { ...s.params, humanize: v } })),

  setParams: (p) => set((s) => ({ params: { ...s.params, ...p } })),

  applyTemplate: (name) => {
    const tpl = get().templates[name];
    if (!tpl) {
      set({ template: name });
      return;
    }
    const base = defaultParams();
    if (tpl.strip) base.strip = { ...base.strip, ...tpl.strip };
    if (tpl.eq) base.eq = tpl.eq;
    if (typeof tpl.humanize === 'number') base.humanize = tpl.humanize;
    if ('lufs_target' in tpl) base.lufs_target = tpl.lufs_target;
    set({ params: base, template: name });
  },

  setExport: (p) =>
    set((s) => ({ exportSettings: { ...s.exportSettings, ...p } })),

  setHumanizeOn: (v) => set({ humanizeOn: v }),
  setAutoIntensity: (v) => set({ autoIntensity: v }),
  ackFirstRun: () => {
    localStorage.setItem('tk_firstRunAck', '1');
    set({ firstRunAck: true });
  },
  markAi: (id, isAi) =>
    set((s) => ({ queue: s.queue.map((q) => (q.id === id ? { ...q, isAi } : q)) })),

  startExport: async () => {
    const s = get();
    const items = s.queue;
    if (items.length === 0) return;
    // When "Humanize & Master" is on, use the console params. When off, pass
    // neutral params: no tonal/humanize processing, just optional LUFS
    // normalize + the safety limiter + format conversion.
    const params = s.humanizeOn
      ? { ...s.params, lufs_target: s.exportSettings.lufs_target,
          autotune_enabled: s.exportSettings.autotune }
      : { ...defaultParams(), strip: { ...defaultStrip() },
          humanize: 0, lufs_target: s.exportSettings.lufs_target };

    set((st) => ({
      exporting: true,
      queue: st.queue.map((q) => ({ ...q, status: 'Queued', progress: 0 })),
    }));

    const res = await api.startExport({
      items: items.map((i) => ({ id: i.id, path: i.path, filename: i.filename, isAi: i.isAi })),
      params,
      exportSettings: s.exportSettings,
    });
    set({ lastOutDir: res.outDir });
  },

  stopExport: async () => {
    await api.stopExport();
    set((s) => ({
      exporting: false,
      queue: s.queue.map((q) => (q.status === 'Processing' || q.status === 'Queued'
        ? { ...q, status: 'Paused' } : q)),
    }));
  },

  loadInitial: async () => {
    try {
      const [{ templates }, presets] = await Promise.all([
        api.templates(), api.loadPresets(),
      ]);
      set({ templates, presets });
    } catch { /* stub */ }
  },

  savePreset: async (name) => {
    const preset: Preset = { name, params: get().params };
    const list = await api.savePreset(preset);
    set({ presets: list });
  },

  deletePreset: async (name) => {
    const list = await api.deletePreset(name);
    set({ presets: list });
  },

  applyPreset: (name) => {
    const p = get().presets.find((x) => x.name === name);
    if (p) set({ params: JSON.parse(JSON.stringify(p.params)), template: 'Custom' });
  },

  setPlaying: (v) => set({ playing: v }),
  setEffectOn: (v) => set({ effectOn: v }),
  setCurrent: (id) => set({ currentId: id }),

  _onStatus: (jobId, status, extra) =>
    set((s) => {
      const done = status === 'Done' || status === 'Error';
      const stillGoing = s.queue.some(
        (q) => q.id !== jobId && (q.status === 'Processing' || q.status === 'Queued'),
      );
      return {
        exporting: done && !stillGoing ? false : s.exporting,
        queue: s.queue.map((q) =>
          q.id === jobId || jobId === '*'
            ? { ...q, status: status as any, error: extra?.error, outputPath: extra?.output_path }
            : q,
        ),
      };
    }),

  _onProgress: (jobId, stage, frac) =>
    set((s) => ({
      queue: s.queue.map((q) => (q.id === jobId ? { ...q, progress: frac, stage } : q)),
    })),

  _onResult: (jobId, result) =>
    set((s) => ({
      queue: s.queue.map((q) =>
        q.id === jobId
          ? { ...q, outputPath: result.output_path, error: result.error,
              status: result.error ? 'Error' : 'Done', progress: 1 }
          : q,
      ),
    })),
}));

// Wire main-process events into the store once.
export function bindIpc() {
  const s = useStore.getState();
  api.onJobStatus(({ jobId, status, extra }) => s._onStatus(jobId, status, extra));
  api.onProgress(({ jobId, stage, frac }) => s._onProgress(jobId, stage, frac));
  api.onJobResult((r) => s._onResult(r.jobId, r));
}
