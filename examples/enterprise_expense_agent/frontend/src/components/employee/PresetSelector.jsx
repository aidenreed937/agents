import React from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

export function PresetSelector() {
  const presets = useExpenseStore((state) => state.presets);
  const applyPreset = useExpenseStore((state) => state.applyPreset);

  if (!presets || presets.length === 0) return null;

  return (
    <div className="presets-wrap">
      <span className="presets-label">快速体验业务场景（点击一键填入）：</span>
      <div className="presets-grid" id="presetsContainer">
        {presets.map((p) => (
          <button
            key={p.id}
            type="button"
            className="preset-chip"
            title={p.description}
            onClick={() => applyPreset(p)}
          >
            <span>{p.title}</span>
            <span className="chip-tag">{p.badge}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
