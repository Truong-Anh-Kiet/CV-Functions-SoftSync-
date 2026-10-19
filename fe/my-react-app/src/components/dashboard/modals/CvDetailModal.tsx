import { useEffect, useState } from 'react';
import type { SearchCvResult, SearchApiResponse } from '../../../types/search';
import type { MatchingResult, ViewMatch } from '../../../types/matching';
import { fetchCvStructured } from '../../../services/api/client';
import { stringifyEvidence } from '../../../utils/format';

interface CvDetailModalProps {
  result: SearchCvResult | null;
  profile?: WebProfile | null;
  searchMeta?: SearchApiResponse['data'] | null;
  onClose: () => void;
}

interface WebProfile {
  id?: string | number;
  source?: string;
  candidate_name?: string;
  title?: string;
  location?: string;
  experience?: string;
  salary?: string;
  summary?: string;
  skills?: string;
  raw_text?: string;
  attachment_url?: string;
  cv_url?: string;
  apply_url?: string;
  profile_url?: string;
  affiliation?: string;
  citations?: string;
  h_index?: number;
  i10_index?: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const color = score >= 70 ? '#16a34a' : score >= 40 ? '#d97706' : '#dc2626';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ flex: 1, height: 8, background: '#e2e8f0', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: 999 }} />
      </div>
      <span style={{ fontSize: 14, fontWeight: 800, color, minWidth: 44 }}>{score}%</span>
    </div>
  );
}

function InfoChip({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '5px 12px', background: '#f8fafc',
      border: '1px solid #e2e8f0', borderRadius: 999,
      fontSize: 12, fontWeight: 600, color: '#475569',
    }}>
      {icon}
      {label}
    </div>
  );
}

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

// ─── Heatmap ─────────────────────────────────────────────────────────────────

const HEATMAP_SIZE = 28;

function getHeatmapColor(val: number): string {
  if (val === 0) return '#f8fafc';
  const intensity = Math.min(1, Math.abs(val));
  const r = Math.round(6 + (226 - 6) * (1 - intensity));
  const g = Math.round(182 + (233 - 182) * (1 - intensity));
  const b = Math.round(212 + (253 - 212) * (1 - intensity));
  return `rgb(${r},${g},${b})`;
}

function HeatmapMatrix({ matrix, rowLabels, colLabels }: {
  matrix: number[][];
  rowLabels: string[];
  colLabels: string[];
}) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
  return (
    <div style={{ position: 'relative', overflow: 'auto', maxHeight: 280 }}>
      <table style={{ borderCollapse: 'collapse', fontSize: 10 }}>
        <thead>
          <tr>
            <th style={{ width: 80, minWidth: 80 }} />
            {colLabels.map((l, j) => (
              <th key={j} style={{
                padding: '2px 4px', fontSize: 9, fontWeight: 600, color: '#94a3b8',
                textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden',
                textOverflow: 'ellipsis', maxWidth: HEATMAP_SIZE * 2,
              }} title={l}>
                {l.length > 10 ? l.slice(0, 9) + '…' : l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td style={{
                padding: '2px 4px', fontSize: 9, fontWeight: 600, color: '#94a3b8',
                textAlign: 'right', whiteSpace: 'nowrap', overflow: 'hidden',
                textOverflow: 'ellipsis', maxWidth: 80,
              }} title={rowLabels[i]}>
                {rowLabels[i]?.length > 12 ? rowLabels[i].slice(0, 11) + '…' : rowLabels[i]}
              </td>
              {row.map((val, j) => (
                <td key={j} style={{ padding: 1 }}>
                  <div
                    style={{
                      width: HEATMAP_SIZE, height: HEATMAP_SIZE,
                      background: getHeatmapColor(val), borderRadius: 3, cursor: 'pointer',
                    }}
                    onMouseEnter={e => {
                      const rect = (e.target as HTMLElement).getBoundingClientRect();
                      setTooltip({ x: rect.left, y: rect.top, text: `${rowLabels[i]} ↔ ${colLabels[j]}: ${val.toFixed(3)}` });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {tooltip && (
        <div style={{
          position: 'fixed', left: tooltip.x, top: tooltip.y - 36,
          background: '#0f172a', color: 'white', padding: '4px 8px',
          borderRadius: 6, fontSize: 10, fontWeight: 600, zIndex: 99999,
          whiteSpace: 'nowrap', pointerEvents: 'none',
        }}>
          {tooltip.text}
        </div>
      )}
    </div>
  );
}

// ─── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'xai' | 'heatmap' | 'data';

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Tổng quan' },
  { id: 'xai', label: 'Giải thích AI' },
  { id: 'heatmap', label: 'Heatmap' },
  { id: 'data', label: 'Dữ liệu' },
];

// ─── Main ──────────────────────────────────────────────────────────────────────

export default function CvDetailModal({ result, profile, searchMeta, onClose }: CvDetailModalProps) {
  if (!result) return null;

  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [cvText, setCvText] = useState('');
  const [cvTextLoading, setCvTextLoading] = useState(false);
  const [cvStructured, setCvStructured] = useState<Record<string, unknown> | null>(null);

  const score = Math.round(result.search_score * 100);
  const isAcademic = profile && (profile.source === 'Google Scholar' || String(profile?.id)?.startsWith('scholar-'));
  const isVW = profile && (profile.source === 'VietnamWorks' || String(profile?.id)?.startsWith('vietnamworks-'));
  const isDb = !profile;

  const normalizeCvName = (v: string) => v.replace(/\.pdf$/i, '').trim().toLowerCase();
  const rerankItem: MatchingResult | undefined = searchMeta?.rerank?.results?.find(
    r => normalizeCvName(r.cv_file) === normalizeCvName(result.filename),
  );

  const hasHeatmap = !!(rerankItem?.alignment_matrix_masked && rerankItem?.heatmap_labels);
  const hasStructured = !!(rerankItem?.cv_structured || rerankItem?.jd_structured);
  const hasViewMatches = !!(rerankItem?.view_matches && rerankItem.view_matches.length > 0);

  useEffect(() => {
    if (!isDb || !result.id) return;
    setCvTextLoading(true);
    setCvText('');
    const docId = typeof result.id === 'number' ? result.id : parseInt(String(result.id), 10);
    if (isNaN(docId)) { setCvTextLoading(false); return; }
    void (async () => {
      const { ok, text, structured } = await fetchCvStructured(docId);
      setCvText(ok ? text : '');
      setCvStructured(ok && Object.keys(structured).length > 0 ? structured : null);
      setCvTextLoading(false);
    })();
  }, [isDb, result.id]);

  // Auto-switch to heatmap or xai tab if rerank data available
  useEffect(() => {
    if (activeTab !== 'overview') return;
    if (hasHeatmap) {
      setActiveTab('heatmap');
    } else if (hasViewMatches) {
      setActiveTab('xai');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasHeatmap, hasViewMatches]);

  // Profile fields
  const name = profile?.candidate_name || '';
  const jobTitle = profile?.title || '';
  const location = profile?.location || '';
  const experience = profile?.experience || '';
  const salary = profile?.salary || '';
  const skills = profile?.skills || '';
  const rawText = profile?.raw_text || '';
  const pdfUrl = profile
    ? (profile.attachment_url || profile.cv_url || '')
    : (result.preview_url || result.cloudinary_url || '');
  const applyUrl = profile
    ? (profile.apply_url || profile.profile_url || '')
    : '';

  const sourceName = isAcademic ? 'Google Scholar' : isVW ? 'VietnamWorks' : profile ? 'CareerViet' : 'CV Database';
  const sourceColor = isAcademic ? '#15803d' : isVW ? '#6d28d9' : '#1d4ed8';
  const displayName = name || result.filename.replace(/\.pdf$/i, '');
  const initials = displayName.split(' ').slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)',
        backdropFilter: 'blur(4px)', zIndex: 9999,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'white', borderRadius: 20,
          boxShadow: '0 25px 60px rgba(15,23,42,0.2)',
          width: '100%', maxWidth: 960, maxHeight: '92vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          animation: 'fadeUp 0.2s ease',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div style={{ padding: '24px 28px 20px', borderBottom: '1px solid #f1f5f9', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: `linear-gradient(135deg, ${sourceColor}22, ${sourceColor}44)`,
              border: `2px solid ${sourceColor}44`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, fontWeight: 900, color: sourceColor, flexShrink: 0,
            }}>
              {initials}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#94a3b8', marginBottom: 4 }}>
                {sourceName}
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 800, color: '#0f172a', margin: 0, lineHeight: 1.2 }}>
                {displayName}
              </h2>
              {jobTitle && (
                <div style={{ fontSize: 13, color: '#64748b', fontWeight: 500, marginTop: 4 }}>
                  {jobTitle}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              style={{
                width: 34, height: 34, borderRadius: 10,
                border: '1px solid #e2e8f0', background: 'white',
                color: '#94a3b8', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, fontSize: 18, lineHeight: 1,
              }}
              aria-label="Đóng"
            >
              &times;
            </button>
          </div>

          {/* Info chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
            {isDb ? (
              <>
                {result.text_length ? (
                  <InfoChip label={`${result.text_length.toLocaleString('vi-VN')} ký tự`}
                    icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>} />
                ) : (
                  <InfoChip label="PDF"
                    icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>} />
                )}
                {result.created_at && (
                  <InfoChip label={`Upload: ${formatDate(result.created_at)}`}
                    icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>} />
                )}
              </>
            ) : (
              <>
                {location && <InfoChip label={location}
                  icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>} />}
                {experience && <InfoChip label={experience}
                  icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>} />}
                {salary && <InfoChip label={salary}
                  icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>} />}
              </>
            )}
          </div>

          {/* Scores row */}
          <div style={{ display: 'flex', gap: 24, marginTop: 16, alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b' }}>Vector Match</span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8' }}>{score}%</span>
              </div>
              <ScoreBar score={score} />
            </div>
            {rerankItem && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: rerankItem.match ? '#16a34a' : '#dc2626' }} />
                <span style={{ fontSize: 14, fontWeight: 800, color: '#0f172a', fontFamily: 'ui-monospace, monospace' }}>
                  {rerankItem.score.toFixed(1)}<small style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>/10</small>
                </span>
                <span style={{
                  padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 800,
                  background: rerankItem.match ? '#f0fdf4' : '#fef2f2',
                  color: rerankItem.match ? '#15803d' : '#b91c1c',
                  border: `1px solid ${rerankItem.match ? '#bbf7d0' : '#fecaca'}`,
                }}>
                  {rerankItem.label}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ── Tab bar ── */}
        <div style={{
          display: 'flex', borderBottom: '2px solid #f1f5f9',
          gap: 0, padding: '0 28px', background: '#fafafa', flexShrink: 0,
        }}>
          {TABS.map(tab => {
            const disabled = (tab.id === 'xai' || tab.id === 'heatmap' || tab.id === 'data') && !rerankItem;
            return (
              <button
                key={tab.id}
                onClick={() => !disabled && setActiveTab(tab.id)}
                style={{
                  padding: '10px 16px', background: 'none', border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #06b6d4' : '2px solid transparent',
                  color: activeTab === tab.id ? '#0891b2' : disabled ? '#cbd5e1' : '#64748b',
                  fontSize: 13, fontWeight: activeTab === tab.id ? 700 : 500,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s ease', marginBottom: -2,
                }}
              >
                {tab.label}
                {tab.id === 'xai' && rerankItem?.view_matches && (
                  <span style={{
                    marginLeft: 6, padding: '1px 6px', borderRadius: 999,
                    background: '#ecfeff', color: '#0891b2',
                    fontSize: 10, fontWeight: 700,
                  }}>
                    {rerankItem.view_matches.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* ── Body ── */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>

          {/* ── TAB: Overview ── */}
          {activeTab === 'overview' && (
            <>
              {/* Extracted fields for DB CV */}
              {isDb && cvStructured && Object.keys(cvStructured).length > 0 && (
                (() => {
                  const main = extractDbFields(cvStructured);
                  if (main.length === 0) {
                    // Fallback: show all top-level key-value pairs
                    const fallback = extractDbFieldsGeneric(cvStructured);
                    if (fallback.length > 0) return <ExtractedFieldsCard fields={fallback} />;
                  }
                  return main.length > 0 ? <ExtractedFieldsCard fields={main} /> : null;
                })()
              )}

              {/* Extracted fields for Web CV */}
              {!isDb && profile && (
                <ExtractedFieldsCard fields={extractWebFields(profile as unknown as Record<string, unknown>)} />
              )}

              {/* DB CV full structured sections */}
              {isDb && cvStructured && Object.keys(cvStructured).length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <CvStructuredSections structured={cvStructured} />
                </div>
              )}

              {/* DB CV raw text fallback (no structured) */}
              {isDb && (!cvStructured || Object.keys(cvStructured).length === 0) && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#94a3b8', marginBottom: 8 }}>Nội dung CV</div>
                  {cvTextLoading ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10, color: '#94a3b8', fontSize: 13 }}>
                      <div style={{ width: 16, height: 16, border: '2px solid #e2e8f0', borderTopColor: '#0891b2', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                      Đang tải nội dung CV...
                    </div>
                  ) : cvText ? (
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, maxHeight: 420, overflowY: 'auto' }}>
                      <pre style={{ fontSize: 13, color: '#334155', lineHeight: 1.8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit', margin: 0 }}>
                        {cvText.slice(0, 4000)}{cvText.length > 4000 ? '\n\n... (nội dung đã bị cắt ngắn)' : ''}
                      </pre>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: '32px 24px', color: '#cbd5e1' }}>
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                      </svg>
                      <span style={{ fontSize: 13, fontWeight: 500, color: '#94a3b8' }}>Không có nội dung để hiển thị</span>
                    </div>
                  )}
                </div>
              )}

              {/* Web CV raw text */}
              {!isDb && rawText && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#94a3b8', marginBottom: 8 }}>Nội dung CV</div>
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 16, maxHeight: 320, overflowY: 'auto' }}>
                    <pre style={{ fontSize: 13, color: '#334155', lineHeight: 1.8, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit', margin: 0 }}>
                      {rawText.slice(0, 2000)}{rawText.length > 2000 ? '\n\n... (nội dung đã bị cắt ngắn)' : ''}
                    </pre>
                  </div>
                </div>
              )}

              {/* Web profile skills */}
              {!isDb && skills && (
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#94a3b8', marginBottom: 8 }}>Kỹ năng</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {skills.split(',').map((s: string, i: number) => s.trim() && (
                      <span key={i} style={{ padding: '4px 12px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, fontSize: 12, fontWeight: 600, color: '#15803d' }}>
                        {s.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Academic stats */}
              {isAcademic && profile ? (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#94a3b8', marginBottom: 8 }}>Thông tin học thuật</div>
                  {profile.affiliation && (
                    <p style={{ fontSize: 14, color: '#334155', margin: '0 0 12px' }}>{profile.affiliation}</p>
                  )}
                  <div style={{ display: 'flex', gap: 24 }}>
                    {profile.citations && (
                      <div>
                        <div style={{ fontSize: 28, fontWeight: 900, color: '#0f172a' }}>{profile.citations}</div>
                        <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Trích dẫn</div>
                      </div>
                    )}
                    {profile.h_index !== undefined && (
                      <div>
                        <div style={{ fontSize: 28, fontWeight: 900, color: '#0f172a' }}>{profile.h_index}</div>
                        <div style={{ fontSize: 11, color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>H-index</div>
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              {/* DB info grid */}
              {isDb && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
                  {result.embedding_dimension && (
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 14px' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 4 }}>Embedding</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>{result.embedding_dimension}D</div>
                    </div>
                  )}
                  {result.indexed_at && (
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 14px' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 4 }}>Indexed</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>{formatDate(result.indexed_at)}</div>
                    </div>
                  )}
                  {result.sbert_id && (
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 14px' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 4 }}>SBERT</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{result.sbert_id}</div>
                    </div>
                  )}
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 14px' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 4 }}>File</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{result.filename}</div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── TAB: XAI ── */}
          {activeTab === 'xai' && (
            !rerankItem?.view_matches || rerankItem.view_matches.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: '#94a3b8', fontSize: 14 }}>
                Không có dữ liệu giải thích AI. Bật AI Rerank khi tìm kiếm để xem.
              </div>
            ) : (
              <XaiTab
                matches={rerankItem.view_matches!}
                reason={(rerankItem as any).reason}
                cvCoverage={rerankItem.cv_view_coverage}
                jdCoverage={rerankItem.jd_view_coverage}
              />
            )
          )}

          {/* ── TAB: Heatmap ── */}
          {activeTab === 'heatmap' && (
            !hasHeatmap ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: '#94a3b8', fontSize: 14 }}>
                Không có ma trận heatmap. Bật AI Rerank để xem.
              </div>
            ) : (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                  {([
                    { title: 'Ma trận gốc (trước mask)', matrix: rerankItem!.alignment_matrix_raw!, labels: rerankItem!.heatmap_labels! },
                    { title: 'Ma trận đã mask (sau lọc)', matrix: rerankItem!.alignment_matrix_masked!, labels: rerankItem!.heatmap_labels! },
                  ] as const).map(({ title, matrix, labels }) => (
                    <div key={title}>
                      <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#94a3b8', marginBottom: 10 }}>
                        {title}
                      </div>
                      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 12, overflow: 'auto' }}>
                        <HeatmapMatrix matrix={matrix} rowLabels={labels.cv || []} colLabels={labels.jd || []} />
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>Thấp</span>
                  <div style={{ display: 'flex', gap: 2 }}>
                    {[0, 0.2, 0.4, 0.6, 0.8, 1].map(v => (
                      <div key={v} style={{ width: 20, height: 12, borderRadius: 2, background: getHeatmapColor(v) }} />
                    ))}
                  </div>
                  <span style={{ fontSize: 11, color: '#94a3b8' }}>Cao</span>
                </div>
              </div>
            )
          )}

          {/* ── TAB: Data ── */}
          {activeTab === 'data' && (
            !hasStructured ? (
              <div style={{ textAlign: 'center', padding: '48px 0', color: '#94a3b8', fontSize: 14 }}>
                Không có dữ liệu structured. Bật AI Rerank để xem.
              </div>
            ) : (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                  {rerankItem?.cv_structured ? (
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#0891b2', marginBottom: 10 }}>
                        CV Structured
                      </div>
                      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 14, overflow: 'auto', maxHeight: 400 }}>
                        <pre style={{ fontSize: 12, color: '#334155', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'ui-monospace, monospace', margin: 0 }}>
                          {JSON.stringify(rerankItem.cv_structured, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ) : null}
                  {rerankItem?.jd_structured ? (
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#7c3aed', marginBottom: 10 }}>
                        JD Structured
                      </div>
                      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 14, overflow: 'auto', maxHeight: 400 }}>
                        <pre style={{ fontSize: 12, color: '#334155', lineHeight: 1.7, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'ui-monospace, monospace', margin: 0 }}>
                          {JSON.stringify(rerankItem.jd_structured, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ) : null}
                </div>
                {rerankItem?.cv_view_coverage && (
                  <div style={{ marginTop: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#94a3b8', marginBottom: 10 }}>
                      CV View Coverage
                    </div>
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', fontSize: 13, color: '#475569', lineHeight: 1.6 }}>
                      {rerankItem.cv_view_coverage}
                    </div>
                  </div>
                )}
                {rerankItem?.jd_view_coverage && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#94a3b8', marginBottom: 10 }}>
                      JD View Coverage
                    </div>
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', fontSize: 13, color: '#475569', lineHeight: 1.6 }}>
                      {rerankItem.jd_view_coverage}
                    </div>
                  </div>
                )}
              </div>
            )
          )}
        </div>

        {/* ── Footer ── */}
        <div style={{
          padding: '16px 28px', borderTop: '1px solid #f1f5f9',
          display: 'flex', gap: 10, justifyContent: 'flex-end', flexShrink: 0,
        }}>
          {pdfUrl && !isDb && (
            <a href={pdfUrl} target="_blank" rel="noopener noreferrer"
              style={{
                padding: '9px 18px', background: '#f8fafc', border: '1px solid #e2e8f0',
                borderRadius: 10, fontSize: 13, fontWeight: 700, color: '#334155',
                textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
              </svg>
              Xem PDF
            </a>
          )}
          {applyUrl && (
            <a href={applyUrl} target="_blank" rel="noopener noreferrer"
              style={{
                padding: '9px 20px', background: 'linear-gradient(135deg, #0891b2, #06b6d4)',
                border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 700, color: 'white',
                textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6,
                boxShadow: '0 2px 8px rgba(6,182,212,0.3)',
              }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
              Ứng tuyển
            </a>
          )}
        </div>

        <style>{`
          @keyframes fadeUp {
            from { opacity: 0; transform: translateY(12px) scale(0.98); }
            to { opacity: 1; transform: translateY(0) scale(1); }
          }
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );
}

// ─── XAI Tab Component ────────────────────────────────────────────────────────

interface XaiTabProps {
  matches: ViewMatch[];
  reason?: string;
  cvCoverage?: string;
  jdCoverage?: string;
}

function XaiTab({ matches, reason, cvCoverage, jdCoverage }: XaiTabProps) {
  const matchesArr = matches || [];
  // Build unique label lists in order of first appearance
  const seenCv = new Set<string>();
  const seenJd = new Set<string>();
  const cvLabels: string[] = [];
  const jdLabels: string[] = [];
  matchesArr.forEach(m => {
    if (!seenCv.has(m.cv_label)) { seenCv.add(m.cv_label); cvLabels.push(m.cv_label); }
    if (!seenJd.has(m.jd_label)) { seenJd.add(m.jd_label); jdLabels.push(m.jd_label); }
  });

  // Map: "cvLabel||jdLabel" -> match
  const cellMap = new Map<string, ViewMatch>();
  matchesArr.forEach(m => cellMap.set(`${m.cv_label}||${m.jd_label}`, m));

  const statusStyle = (status: string) => {
    if (status === 'strong_match') return { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Khớp mạnh' };
    if (status === 'partial_match') return { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Khớp một phần' };
    if (status === 'missing') return { color: '#94a3b8', bg: '#f8fafc', border: '#e2e8f0', label: 'Thiếu' };
    return { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Không khớp' };
  };

  const cvEvidenceStr = (ev: ReturnType<typeof stringifyEvidence>) =>
    typeof ev === 'string' && ev !== 'missing_section' ? ev : '';

  return (
    <div>
      {/* Summary */}
      {(reason || cvCoverage || jdCoverage) && (
        <div style={{ padding: '12px 16px', background: '#f0fdfa', border: '1px solid #ccfbf1', borderRadius: 10, marginBottom: 20 }}>
          {reason && (
            <>
              <div style={{ fontSize: 11, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.4px', color: '#0891b2', marginBottom: 6 }}>
                Tổng kết AI
              </div>
              <p style={{ fontSize: 13, color: '#134e4a', lineHeight: 1.6, margin: '0 0 8px' }}>{reason}</p>
            </>
          )}
          {cvCoverage && (
            <p style={{ fontSize: 12, color: '#0e7490', lineHeight: 1.6, margin: 0 }}>{cvCoverage}</p>
          )}
          {jdCoverage && !cvCoverage && (
            <p style={{ fontSize: 12, color: '#0e7490', lineHeight: 1.6, margin: 0 }}>{jdCoverage}</p>
          )}
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Chú thích:</span>
        {[
          { color: '#16a34a', label: 'Khớp mạnh' },
          { color: '#d97706', label: 'Khớp một phần' },
          { color: '#dc2626', label: 'Không khớp' },
          { color: '#94a3b8', label: 'Thiếu' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: l.color }} />
            <span style={{ fontSize: 12, color: '#64748b', fontWeight: 500 }}>{l.label}</span>
          </div>
        ))}
        <span style={{ color: '#e2e8f0' }}>|</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 14, height: 14, borderRadius: 3, background: '#f8fafc', border: '1px solid #e2e8f0' }} />
          <span style={{ fontSize: 12, color: '#64748b', fontWeight: 500 }}>Không có dữ liệu</span>
        </div>
      </div>

      {/* Grid table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'separate', borderSpacing: 4, minWidth: '100%' }}>
          <thead>
            <tr>
              {/* Corner cell */}
              <th style={{
                minWidth: 120, width: 120, padding: '6px 12px',
                background: '#f1f5f9', borderRadius: '8px 0 0 0',
                border: '1px solid #e2e8f0', borderRight: 'none', borderBottom: 'none',
              }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.3px' }}>
                  CV \ JD
                </span>
              </th>
              {/* JD column headers */}
              {jdLabels.map(jdl => (
                <th key={jdl} style={{
                  padding: '6px 10px', background: '#f1f5f9',
                  border: '1px solid #e2e8f0', borderBottom: 'none',
                  textAlign: 'center', minWidth: 160, maxWidth: 220,
                }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, color: '#7c3aed',
                    lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={jdl}>
                    {jdl}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cvLabels.map(cvl => (
              <tr key={cvl}>
                {/* CV row header */}
                <td style={{
                  padding: '6px 12px', background: '#f1f5f9',
                  border: '1px solid #e2e8f0', borderTop: 'none', borderRight: 'none',
                  verticalAlign: 'middle',
                }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, color: '#0891b2',
                    lineHeight: 1.3, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={cvl}>
                    {cvl}
                  </div>
                </td>
                {/* Data cells */}
                {jdLabels.map(jdl => {
                  const match = cellMap.get(`${cvl}||${jdl}`);
                  if (!match) {
                    return (
                      <td key={jdl} style={{
                        padding: 10, background: '#f8fafc',
                        border: '1px solid #e2e8f0', borderTop: 'none', borderLeft: 'none',
                        textAlign: 'center', verticalAlign: 'middle', minWidth: 160, maxWidth: 220,
                      }}>
                        <span style={{ fontSize: 18, color: '#e2e8f0' }}>—</span>
                      </td>
                    );
                  }
                  const st = statusStyle(match.status);
                  const evCv = cvEvidenceStr(stringifyEvidence(match.cv_evidence));
                  const evJd = cvEvidenceStr(stringifyEvidence(match.jd_evidence));
                  return (
                    <td key={jdl} style={{
                      padding: 10, background: st.bg,
                      border: `1px solid ${st.border}`, borderTop: 'none', borderLeft: 'none',
                      verticalAlign: 'top', minWidth: 160, maxWidth: 220,
                    }}>
                      {/* Score */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div style={{ width: 7, height: 7, borderRadius: '50%', background: st.color }} />
                        <span style={{ fontSize: 14, fontWeight: 900, color: st.color, fontFamily: 'ui-monospace, monospace' }}>
                          {match.similarity.toFixed(3)}
                        </span>
                      </div>

                      {/* CV content */}
                      <div style={{ marginBottom: 6 }}>
                        <div style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.3px', color: '#0891b2', marginBottom: 4 }}>CV</div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a', lineHeight: 1.4, wordBreak: 'break-word' }}>
                          {match.cv_view || '—'}
                        </div>
                        {evCv && (
                          <div style={{ fontSize: 10, color: '#64748b', marginTop: 3, lineHeight: 1.4 }}>{evCv}</div>
                        )}
                      </div>

                      {/* Divider */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0', color: '#cbd5e1' }}>
                        <div style={{ flex: 1, height: 1, background: '#e2e8f0' }} />
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M5 12h14M12 5l7 7-7 7"/>
                        </svg>
                        <div style={{ flex: 1, height: 1, background: '#e2e8f0' }} />
                      </div>

                      {/* JD content */}
                      <div style={{ marginTop: 6 }}>
                        <div style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.3px', color: '#7c3aed', marginBottom: 4 }}>JD</div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a', lineHeight: 1.4, wordBreak: 'break-word' }}>
                          {match.jd_view || '—'}
                        </div>
                        {evJd && (
                          <div style={{ fontSize: 10, color: '#64748b', marginTop: 3, lineHeight: 1.4 }}>{evJd}</div>
                        )}
                      </div>

                      {/* Reason */}
                      {match.reason && (
                        <div style={{
                          marginTop: 8, padding: '5px 8px', background: 'rgba(255,255,255,0.6)',
                          borderRadius: 6, fontSize: 11, color: '#475569', lineHeight: 1.5,
                        }}>
                          {match.reason}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── CV Structured Sections ────────────────────────────────────────────────────

const SECTION_ORDER = [
  'personal_info', 'summary', 'experience', 'work_experience', 'education',
  'skills', 'certifications', 'projects', 'languages', 'achievements', 'publications', 'objective', 'contact', 'raw_text',
];

const SECTION_COLORS: Record<string, string> = {
  personal_info: '#6366f1',
  experience: '#0891b2', work_experience: '#0891b2',
  education: '#7c3aed',
  skills: '#16a34a',
  certifications: '#d97706',
  projects: '#db2777',
  languages: '#0284c7',
  achievements: '#ea580c',
  publications: '#7c3aed',
  summary: '#475569', objective: '#475569',
  contact: '#64748b', raw_text: '#94a3b8',
};

const SECTION_ICONS: Record<string, React.ReactNode> = {
  personal_info: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  experience: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>,
  work_experience: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>,
  education: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>,
  skills: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>,
  certifications: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>,
  projects: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  languages: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>,
  summary: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>,
  achievements: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>,
  publications: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
  objective: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>,
  contact: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.37 2 2 0 0 1 3.58 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6.18 6.18l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>,
  raw_text: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>,
};

function formatFieldValue(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return (v as unknown[]).map((item, i) => (
    <div key={i}>{formatFieldValue(item)}</div>
  ));
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>).map(([k, val], i, arr) => {
      if (val === null || val === undefined || val === '') return null;
      const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const displayVal = Array.isArray(val) ? val.join(', ') : typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val);
      return (
        <div key={k} style={{ marginBottom: i < arr.length - 1 ? 6 : 0 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.3px' }}>
            {label}
          </span>
          <div style={{ fontSize: 13, color: '#334155', lineHeight: 1.5, marginTop: 2 }}>
            {displayVal}
          </div>
        </div>
      );
    });
  }
  return String(v);
}

function renderSectionContent(content: unknown, color: string): React.ReactNode {
  if (!content) return null;
  if (typeof content === 'string') {
    return (
      <div style={{ background: '#f8fafc', border: `1px solid ${color}22`, borderLeft: `3px solid ${color}`, borderRadius: 10, padding: '10px 14px' }}>
        <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.7, margin: 0 }}>{content}</p>
      </div>
    );
  }
  if (Array.isArray(content)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {(content as unknown[]).map((item, i) => {
          if (typeof item === 'string') {
            return (
              <div key={i} style={{ background: '#f8fafc', border: `1px solid ${color}22`, borderLeft: `3px solid ${color}`, borderRadius: 10, padding: '10px 14px' }}>
                <p style={{ fontSize: 13, color: '#334155', lineHeight: 1.7, margin: 0 }}>{item}</p>
              </div>
            );
          }
          if (typeof item === 'object' && item !== null) {
            const entries = Object.entries(item as Record<string, unknown>);
            return (
              <div key={i} style={{ background: '#f8fafc', border: `1px solid ${color}22`, borderLeft: `3px solid ${color}`, borderRadius: 10, padding: '12px 16px' }}>
                {entries.map(([k, v], j) => {
                  if (v === null || v === undefined || v === '') return null;
                  const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                  if (Array.isArray(v)) {
                    return (
                      <div key={k} style={{ marginBottom: j < entries.length - 1 ? 10 : 0 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: 4 }}>
                          {label}
                        </div>
                        <div style={{ fontSize: 12, color: '#334155', lineHeight: 1.5 }}>
                          {v.map((vv, ii) => (
                            <div key={ii} style={{ marginBottom: 2 }}>{typeof vv === 'object' ? formatFieldValue(vv) : String(vv)}</div>
                          ))}
                        </div>
                      </div>
                    );
                  }
                  return (
                    <div key={k} style={{ marginBottom: j < entries.length - 1 ? 10 : 0 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: 4 }}>
                        {label}
                      </div>
                      <div style={{ fontSize: 13, color: '#334155', lineHeight: 1.5 }}>
                        {typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v)}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          }
          return null;
        })}
      </div>
    );
  }
  if (typeof content === 'object') {
    return (
      <div style={{ background: '#f8fafc', border: `1px solid ${color}22`, borderLeft: `3px solid ${color}`, borderRadius: 10, padding: '12px 16px' }}>
        {formatFieldValue(content)}
      </div>
    );
  }
  return null;
}

function CvStructuredSection({ label, content }: { label: string; content: unknown }) {
  const key = SECTION_ORDER.find(o => label.toLowerCase().includes(o)) || '';
  const color = SECTION_COLORS[key] || '#0891b2';
  const icon = SECTION_ICONS[key];
  const displayLabel = label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  if (!content) return null;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        {icon && (
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: `${color}18`, border: `1px solid ${color}33`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color, flexShrink: 0,
          }}>
            {icon}
          </div>
        )}
        <span style={{ fontSize: 12, fontWeight: 800, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
          {displayLabel}
        </span>
      </div>
      {renderSectionContent(content, color)}
    </div>
  );
}

function CvStructuredSections({ structured }: { structured: unknown }) {
  if (!structured || typeof structured !== 'object') {
    return <div style={{ textAlign: 'center', padding: 24, color: '#94a3b8', fontSize: 13 }}>Dữ liệu không hợp lệ</div>;
  }

  const entries = Object.entries(structured as Record<string, unknown>);
  const sorted = [...entries].sort(([a], [b]) => {
    const ia = SECTION_ORDER.findIndex(o => a.toLowerCase().includes(o));
    const ib = SECTION_ORDER.findIndex(o => b.toLowerCase().includes(o));
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return 0;
  });

  return (
    <div>
      {sorted.map(([label, content]) => (
        <CvStructuredSection key={label} label={label} content={content} />
      ))}
    </div>
  );
}

// ─── Extracted Fields Display (key-value grid) ─────────────────────────────────

interface ExtractedField {
  label: string;
  value: string | null | undefined;
  color: string;
}

function ExtractedFieldsCard({ fields }: { fields: ExtractedField[] }) {
  const valid = fields.filter(f => f.value && String(f.value).trim());
  if (valid.length === 0) return null;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
      gap: 10,
      marginBottom: 20,
    }}>
      {valid.map(({ label, value, color }) => (
        <div key={label} style={{
          background: '#f8fafc',
          border: `1px solid ${color}33`,
          borderLeft: `3px solid ${color}`,
          borderRadius: 10,
          padding: '10px 14px',
        }}>
          <div style={{
            fontSize: 10,
            fontWeight: 800,
            color: color,
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
            marginBottom: 4,
          }}>
            {label}
          </div>
          <div style={{ fontSize: 13, color: '#1e293b', fontWeight: 600, lineHeight: 1.4 }}>
            {value}
          </div>
        </div>
      ))}
    </div>
  );
}

// Extract key fields from DB structured data (CVStructuredData schema)
function extractDbFields(structured: Record<string, unknown>): ExtractedField[] {
  const fields: ExtractedField[] = [];

  // 1) personal_info
  const personal = structured.personal_info as Record<string, unknown> | undefined;
  if (personal) {
    if (personal.name) fields.push({ label: 'Họ tên', value: String(personal.name), color: '#6366f1' });
    if (personal.full_name) fields.push({ label: 'Họ tên', value: String(personal.full_name), color: '#6366f1' });
    if (personal.email) fields.push({ label: 'Email', value: String(personal.email), color: '#475569' });
    if (personal.phone) fields.push({ label: 'Điện thoại', value: String(personal.phone), color: '#475569' });
    if (personal.location) fields.push({ label: 'Nơi ở', value: String(personal.location), color: '#0284c7' });
    if (personal.address) fields.push({ label: 'Địa chỉ', value: String(personal.address), color: '#0284c7' });
  }

  // 2) Top-level fields often returned by LLM structurers
  if (structured.name && !personal) fields.push({ label: 'Họ tên', value: String(structured.name), color: '#6366f1' });
  if (structured.full_name && !personal) fields.push({ label: 'Họ tên', value: String(structured.full_name), color: '#6366f1' });
  if (structured.position) fields.push({ label: 'Vị trí', value: String(structured.position), color: '#0891b2' });
  if (structured.job_title) fields.push({ label: 'Vị trí', value: String(structured.job_title), color: '#0891b2' });
  if (structured.title) fields.push({ label: 'Vị trí', value: String(structured.title), color: '#0891b2' });
  if (structured.education_level) fields.push({ label: 'Trình độ', value: String(structured.education_level), color: '#7c3aed' });
  if (structured.experience_years) fields.push({ label: 'Kinh nghiệm', value: String(structured.experience_years), color: '#d97706' });
  if (structured.salary_expectation) fields.push({ label: 'Lương mong muốn', value: String(structured.salary_expectation), color: '#16a34a' });
  if (structured.location) fields.push({ label: 'Nơi ở', value: String(structured.location), color: '#0284c7' });

  // 3) Summary
  if (structured.summary) {
    const s = String(structured.summary);
    fields.push({ label: 'Tóm tắt', value: s.length > 200 ? s.slice(0, 200) + '...' : s, color: '#475569' });
  }

  // 4) Experience: grab first entry
  const experience = structured.experience;
  if (Array.isArray(experience) && experience.length > 0) {
    const first = experience[0] as Record<string, unknown>;
    if (first.job_title) fields.push({ label: 'Vị trí', value: String(first.job_title), color: '#0891b2' });
    if (first.company) fields.push({ label: 'Công ty', value: String(first.company), color: '#db2777' });
    if (first.description) {
      const d = String(first.description);
      fields.push({ label: 'Mô tả kinh nghiệm', value: d.length > 200 ? d.slice(0, 200) + '...' : d, color: '#d97706' });
    }
  }

  // 5) Education: grab first entry
  const education = structured.education;
  if (Array.isArray(education) && education.length > 0) {
    const first = education[0] as Record<string, unknown>;
    if (first.degree || first.institution) {
      fields.push({
        label: 'Học vấn',
        value: [first.degree, first.institution].filter(Boolean).join(' - '),
        color: '#7c3aed',
      });
    }
  }

  // 6) Certifications
  if (Array.isArray(structured.certifications) && structured.certifications.length > 0) {
    const certs = structured.certifications as Record<string, unknown>[];
    fields.push({ label: 'Chứng chỉ', value: certs.map(c => c.name).filter(Boolean).join(', '), color: '#d97706' });
  }

  // 7) Languages
  if (Array.isArray(structured.languages) && structured.languages.length > 0) {
    const langs = structured.languages as Record<string, unknown>[];
    fields.push({ label: 'Ngôn ngữ', value: langs.map(l => l.language).filter(Boolean).join(', '), color: '#0284c7' });
  }

  // 8) Skills
  if (Array.isArray(structured.skills) && structured.skills.length > 0) {
    const skills = structured.skills as (string | Record<string, unknown>)[];
    const skillNames = skills.map(s => typeof s === 'string' ? s : String(s.name || s.skill || '')).filter(Boolean);
    fields.push({ label: 'Kỹ năng', value: skillNames.join(', '), color: '#16a34a' });
  }

  return fields;
}

// Show all top-level key-value pairs as fallback cards
function extractDbFieldsGeneric(structured: Record<string, unknown>): ExtractedField[] {
  const SKIP_KEYS = new Set(['experience', 'education', 'certifications', 'languages', 'skills', 'projects']);
  const COLORS = ['#0891b2', '#6366f1', '#7c3aed', '#d97706', '#16a34a', '#0284c7', '#db2777', '#475569'];
  const fields: ExtractedField[] = [];

  for (const [key, value] of Object.entries(structured)) {
    if (SKIP_KEYS.has(key)) continue;
    if (value === null || value === undefined) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    if (typeof value === 'object' && !Array.isArray(value)) continue;

    const displayValue = String(value);
    if (!displayValue.trim()) continue;

    const labelMap: Record<string, string> = {
      name: 'Họ tên', full_name: 'Họ tên', candidate_name: 'Họ tên',
      position: 'Vị trí', job_title: 'Vị trí', title: 'Vị trí',
      email: 'Email', phone: 'Điện thoại', mobile: 'Di động',
      location: 'Nơi ở', address: 'Địa chỉ', city: 'Thành phố',
      education: 'Trình độ', education_level: 'Trình độ', level: 'Cấp bậc',
      experience: 'Kinh nghiệm', experience_years: 'Năm kinh nghiệm',
      salary: 'Lương', salary_expectation: 'Lương mong muốn',
      summary: 'Tóm tắt', objective: 'Mục tiêu',
    };
    const label = labelMap[key.toLowerCase()] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const color = COLORS[fields.length % COLORS.length];
    fields.push({ label, value: displayValue.length > 150 ? displayValue.slice(0, 150) + '...' : displayValue, color });
  }

  return fields;
}

// Extract key fields from Web profile (CareerVietProfile)
function extractWebFields(profile: Record<string, unknown>): ExtractedField[] {
  const fields: ExtractedField[] = [];

  if (profile.title) fields.push({ label: 'Vị trí', value: String(profile.title), color: '#0891b2' });
  if (profile.candidate_name) fields.push({ label: 'Họ tên', value: String(profile.candidate_name), color: '#6366f1' });
  if (profile.education) fields.push({ label: 'Trình độ', value: String(profile.education), color: '#7c3aed' });
  if (profile.level) fields.push({ label: 'Cấp bậc', value: String(profile.level), color: '#7c3aed' });
  if (profile.experience) fields.push({ label: 'Kinh nghiệm', value: String(profile.experience), color: '#d97706' });
  if (profile.salary) fields.push({ label: 'Lương', value: String(profile.salary), color: '#16a34a' });
  if (profile.location) fields.push({ label: 'Nơi ở', value: String(profile.location), color: '#0284c7' });
  if (profile.last_access) fields.push({ label: 'Cập nhật', value: String(profile.last_access), color: '#475569' });

  return fields;
}
