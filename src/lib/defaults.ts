import type { Params, ExportSettings, MasterStrip } from '@shared/types';

export const defaultStrip = (): MasterStrip => ({
  bass: 0, deep: 0, mid: 0, clear: 0, treble: 0, presence: 0,
  low_cut: 25, gate: 0, de_ess: 0, air: 0, comp: 0, limit: 85,
  saturation: 0, reverb: 0, echo: 0, width: 0, gain: 0,
});

export const defaultParams = (): Params => ({
  strip: defaultStrip(),
  eq: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  humanize: 35,
  autotune_enabled: false,
  autotune_strength: 30,
  autotune_key: 'C',
  autotune_scale: 'major',
  lufs_target: -14,
  true_peak_ceiling: -1,
});

export const defaultExport = (): ExportSettings => ({
  format: 'wav',
  sample_rate: null,
  bit_depth: 24,
  mp3_bitrate: 320,
  threads: 4,
  autotune: false,
  merge: false,
  lufs_target: -14,
  output_folder: null,
});

// Mastering-strip slider definitions: label, key, unit, range, step.
export interface StripControl {
  key: keyof MasterStrip;
  label: string;
  unit: 'dB' | '%' | 'Hz';
  min: number;
  max: number;
  step: number;
}

export const STRIP_CONTROLS: StripControl[] = [
  { key: 'bass', label: 'Bass', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'deep', label: 'Deep', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'mid', label: 'Mid', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'clear', label: 'Clear', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'treble', label: 'Treble', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'presence', label: 'Pres', unit: 'dB', min: -12, max: 12, step: 0.5 },
  { key: 'low_cut', label: 'LCut', unit: 'Hz', min: 20, max: 120, step: 1 },
  { key: 'gate', label: 'Gate', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'de_ess', label: 'DeEss', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'air', label: 'Air', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'comp', label: 'Comp', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'limit', label: 'Limit', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'saturation', label: 'Sat', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'reverb', label: 'Verb', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'echo', label: 'Echo', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'width', label: 'Width', unit: '%', min: -100, max: 100, step: 1 },
  { key: 'gain', label: 'Gain', unit: 'dB', min: -12, max: 12, step: 0.5 },
];

export const EQ_LABELS = ['30', '80', '150', '250', '500', '1k', '2k', '4k', '8k', '12k'];
