export const getHeatmapColor = (value: number): string => {
  const val = Math.max(0, Math.min(1, value));
  if (val === 0) return 'rgb(220, 38, 38)';
  if (val < 0.5) {
    const t = val / 0.5;
    const r = Math.round(220 + (253 - 220) * t);
    const g = Math.round(38 + (224 - 38) * t);
    const b = Math.round(38 + (71 - 38) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    const t = (val - 0.5) / 0.5;
    const r = Math.round(253 + (22 - 253) * t);
    const g = Math.round(224 + (163 - 224) * t);
    const b = Math.round(71 + (74 - 71) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
};

export const getHeatmapTextColor = (value: number): string => {
  if (value === 0) return '#fff';
  if (value < 0.3 || value > 0.75) return '#fff';
  return '#1e293b';
};

export const formatHeatmapLabel = (label: string) => {
  const match = label.match(/\[.*?\]/);
  return match ? match[0] : label;
};
