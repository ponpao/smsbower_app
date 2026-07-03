import React from 'react';

interface Props {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: 'dB' | '%' | 'Hz';
  disabled?: boolean;
  onChange: (v: number) => void;
}

function fmt(value: number, unit: 'dB' | '%' | 'Hz'): string {
  if (unit === 'Hz') return `${Math.round(value)} Hz`;
  if (unit === '%') return `${Math.round(value)} %`;
  const s = value > 0 ? '+' : '';
  return `${s}${value.toFixed(value % 1 === 0 ? 0 : 1)} dB`;
}

export const VerticalSlider: React.FC<Props> = ({
  label, value, min, max, step, unit, disabled, onChange,
}) => {
  const active = Math.abs(value) > (unit === 'Hz' ? min + 0.5 : 0.01);
  return (
    <div className="flex flex-col items-center gap-1.5 select-none no-drag">
      <span className={`text-[10px] uppercase tracking-wide ${active ? 'text-slate-300' : 'text-slate-500'}`}>
        {label}
      </span>
      <input
        type="range"
        className="v-slider"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        onDoubleClick={() => onChange(unit === 'Hz' ? min : 0)}
        title={`${label}: ${fmt(value, unit)} (double-click to reset)`}
      />
      <span className={`text-[10px] font-mono ${active ? 'text-accent-soft' : 'text-slate-500'}`}>
        {fmt(value, unit)}
      </span>
    </div>
  );
};
