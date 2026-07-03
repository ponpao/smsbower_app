// Shared contract types used by both the Electron main process and the renderer.

export const EQ_BANDS = [30, 80, 150, 250, 500, 1000, 2000, 4000, 8000, 12000] as const;

export type JobStatus =
  | 'Idle'
  | 'Queued'
  | 'Processing'
  | 'Done'
  | 'Error'
  | 'Paused';

export interface FileMeta {
  path: string;
  filename: string;
  duration: number;
  duration_str: string;
  type: string;
  codec: string;
  key: string;
  sample_rate: number;
  bit_depth: number | null;
  loudness_lufs: number | null;
  true_peak_dbtp: number | null;
  channels: number;
  channel_label: string;
}

export interface QueueItem {
  id: string;
  path: string;
  filename: string;
  status: JobStatus;
  progress: number; // 0..1
  stage?: string;
  meta?: FileMeta;
  error?: string;
  outputPath?: string;
  isAi?: boolean; // user-declared "AI-generated source"
}

export interface MasterStrip {
  bass: number; deep: number; mid: number; clear: number; treble: number;
  presence: number; low_cut: number; gate: number; de_ess: number; air: number;
  comp: number; limit: number; saturation: number; reverb: number; echo: number;
  width: number; gain: number;
}

export interface Params {
  strip: MasterStrip;
  eq: number[]; // len 10
  humanize: number;
  autotune_enabled: boolean;
  autotune_strength: number;
  autotune_key: string;
  autotune_scale: string;
  lufs_target: number | null;
  true_peak_ceiling: number;
}

export type ExportFormat = 'wav' | 'flac' | 'mp3';

export interface ExportSettings {
  format: ExportFormat;
  sample_rate: number | null; // null = keep source
  bit_depth: number;
  mp3_bitrate: number;
  threads: number; // 1..8
  autotune: boolean;
  merge: boolean;
  lufs_target: number | null;
  output_folder: string | null;
}

export interface ProgressEvent {
  jobId: string;
  stage: string;
  frac: number;
}

export interface JobResult {
  jobId: string;
  outputPath?: string;
  metrics?: {
    loudness_lufs: number | null;
    true_peak_dbtp: number | null;
    sample_rate: number;
  };
  error?: string;
}

export interface AuthenticityReport {
  p_ai: number;
  ci_low: number;
  ci_high: number;
  confidence_label: string;
  features: Record<string, number>;
  beta: boolean;
  disclaimer: string;
  note: string;
}

export interface ReleaseCheckItem {
  name: string;
  status: 'pass' | 'warn';
  detail: string;
}

export interface ReleaseCheck {
  items: ReleaseCheckItem[];
  passed: boolean;
  warn_count: number;
  summary: string;
}

export interface Preset {
  name: string;
  params: Params;
  builtin?: boolean;
}

// IPC channel names (renderer <-> main).
export const IPC = {
  addFiles: 'tk:addFiles',
  addFolder: 'tk:addFolder',
  analyze: 'tk:analyze',
  startExport: 'tk:startExport',
  stopExport: 'tk:stopExport',
  authenticity: 'tk:authenticity',
  releaseCheck: 'tk:releaseCheck',
  templates: 'tk:templates',
  chooseOutput: 'tk:chooseOutput',
  openOutput: 'tk:openOutput',
  savePreset: 'tk:savePreset',
  loadPresets: 'tk:loadPresets',
  deletePreset: 'tk:deletePreset',
  sysStats: 'tk:sysStats',
  windowControl: 'tk:windowControl',
  onProgress: 'tk:onProgress',
  onJobStatus: 'tk:onJobStatus',
  onJobResult: 'tk:onJobResult',
} as const;
