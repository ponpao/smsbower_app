// Thin typed accessor for the preload bridge. Falls back to a stub in a plain
// browser (e.g. Vite preview without Electron) so the UI still renders.

import type {
  FileMeta, AuthenticityReport, ReleaseCheck, Params, Preset,
} from '@shared/types';

interface TravkodApi {
  addFiles(): Promise<string[]>;
  addFolder(): Promise<string[]>;
  analyze(path: string): Promise<FileMeta>;
  authenticity(path: string): Promise<AuthenticityReport>;
  releaseCheck(payload: any): Promise<ReleaseCheck>;
  templates(): Promise<{ templates: Record<string, any> }>;
  startExport(payload: any): Promise<{ outDir: string; count: number }>;
  stopExport(): Promise<boolean>;
  chooseOutput(): Promise<string | null>;
  openOutput(folder: string): Promise<void>;
  loadPresets(): Promise<Preset[]>;
  savePreset(preset: Preset): Promise<Preset[]>;
  deletePreset(name: string): Promise<Preset[]>;
  sysStats(): Promise<{ cpu: number; ram: number }>;
  windowControl(a: 'minimize' | 'maximize' | 'close'): Promise<void>;
  onProgress(cb: (e: { jobId: string; stage: string; frac: number }) => void): () => void;
  onJobStatus(cb: (e: { jobId: string; status: string; extra?: any }) => void): () => void;
  onJobResult(cb: (e: any) => void): () => void;
}

const stub: TravkodApi = {
  addFiles: async () => [],
  addFolder: async () => [],
  analyze: async (p) => ({
    path: p, filename: p.split('/').pop() || p, duration: 0, duration_str: '0:00',
    type: 'WAV', codec: 'PCM_24', key: '—', sample_rate: 44100, bit_depth: 24,
    loudness_lufs: null, true_peak_dbtp: null, channels: 2, channel_label: 'Stereo',
  }),
  authenticity: async () => ({
    p_ai: 0.5, ci_low: 0.3, ci_high: 0.7, confidence_label: 'low confidence',
    features: {}, beta: true, disclaimer: 'Beta — experimental.', note: 'Stub.',
  }),
  releaseCheck: async () => ({ items: [], passed: true, warn_count: 0, summary: 'Stub.' }),
  templates: async () => ({ templates: {} }),
  startExport: async () => ({ outDir: '', count: 0 }),
  stopExport: async () => true,
  chooseOutput: async () => null,
  openOutput: async () => {},
  loadPresets: async () => [],
  savePreset: async () => [],
  deletePreset: async () => [],
  sysStats: async () => ({ cpu: 0, ram: 0 }),
  windowControl: async () => {},
  onProgress: () => () => {},
  onJobStatus: () => () => {},
  onJobResult: () => () => {},
};

export const api: TravkodApi =
  (typeof window !== 'undefined' && (window as any).travkod) || stub;

export type { Params };
