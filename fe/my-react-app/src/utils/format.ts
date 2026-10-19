import type { EvidenceValue } from '../types/dashboard';

export const formatSavedDate = (value?: string | null) => {
  if (!value) return 'Vừa lưu';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Vừa lưu';
  return date.toLocaleDateString('vi-VN');
};

export const formatScorePercent = (value: number) => `${Math.round(value * 1000) / 10}%`;

export const stringifyEvidence = (value: EvidenceValue) => {
  if (!value) return 'missing_section';
  return Array.isArray(value) ? value.join('. ') : value;
};
