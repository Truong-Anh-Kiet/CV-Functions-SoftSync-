import { useEffect, useState } from 'react';
import type { SearchCvResult, SearchApiResponse } from '../../../types/search';
import type { MatchingResult } from '../../../types/matching';
import { getCvHeatmap } from '../../../services/api/matching';
import HeatmapSection from '../matching/HeatmapSection';
import XaiExplanation from '../matching/XaiExplanation';
import StructuredDataViewer from '../matching/StructuredDataViewer';
import CellDetailModal, { type CellDetailState } from './CellDetailModal';

interface SearchDetailModalProps {
  result: SearchCvResult | null;
  jdText?: string;
  jdFile?: File | null;
  cvText?: string;
  cvFilename?: string;
  modelId?: string;
  searchMeta?: SearchApiResponse['data'] | null;
  enableAiMatching?: boolean;
  onClose: () => void;
}

type Tab = 'heatmap' | 'xai' | 'pdf' | 'overview' | 'json';

const detailMatchingCache = new Map<string, MatchingResult>();

const normalizeCvName = (value: string | number | null | undefined) => String(value ?? '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/(\.(pdf|txt))+$/i, '')
  .replace(/[^a-z0-9]+/gi, ' ')
  .trim()
  .toLowerCase();

const hasFullAiDetail = (candidate?: MatchingResult | null) => Boolean(
  candidate?.alignment_matrix_raw
  && candidate?.alignment_matrix_masked
  && candidate?.heatmap_labels
  && Array.isArray(candidate?.view_matches)
  && candidate.view_matches.length > 0,
);

const jdCacheKey = (jdText?: string, jdFile?: File | null) => {
  if (jdFile) return `file:${jdFile.name}:${jdFile.size}:${jdFile.lastModified}`;
  return `text:${(jdText || '').trim()}`;
};

const CV_VIEW_KEYS = ['skills', 'education', 'year_experience', 'experience', 'responsibilities', 'projects', 'publications', 'achievement', 'certification', 'employment_history'];
const JD_VIEW_KEYS = ['skills', 'education', 'year_experience_requirement', 'experience_requirement', 'responsibilities'];
const VIEW_LABEL_MAP: Record<string, string> = {
  skills: 'Kỹ năng',
  education: 'Học vấn',
  year_experience: 'Số năm kinh nghiệm',
  experience: 'Kinh nghiệm làm việc',
  responsibilities: 'Trách nhiệm',
  projects: 'Dự án',
  publications: 'Công trình',
  achievement: 'Thành tích',
  certification: 'Chứng chỉ',
  employment_history: 'Lịch sử công việc',
  year_experience_requirement: 'Yêu cầu kinh nghiệm',
  experience_requirement: 'Yêu cầu kinh nghiệm (loại)',
};

const extractStructuredField = (structured: unknown, key: string): string => {
  if (!structured || typeof structured !== 'object') return '(Không có dữ liệu)';
  const val = (structured as Record<string, unknown>)[key];
  if (val === undefined || val === null) return '(Không có trường này)';
  if (typeof val === 'string') return val.trim() || '(Trống)';
  if (Array.isArray(val)) return val.join('\n') || '(Trống)';
  return String(val);
};

export default function SearchDetailModal({
  result,
  jdText,
  jdFile,
  cvText,
  cvFilename,
  modelId,
  searchMeta,
  enableAiMatching = false,
  onClose,
}: SearchDetailModalProps) {
  const [loading, setLoading] = useState(false);
  const [matchingResult, setMatchingResult] = useState<MatchingResult | null>(null);
  const [matchingResultKey, setMatchingResultKey] = useState<string | null>(null);
  const [error] = useState<string | null>(null);
  const [cellDetail, setCellDetail] = useState<CellDetailState | null>(null);

  const resultFilename = result?.filename || '';
  const resultKey = result ? `${result.id}:${result.filename}` : '';
  const matchingCacheKey = result
    ? `${result.id}:${normalizeCvName(result.filename)}:${jdCacheKey(jdText, jdFile)}:${modelId || 'default'}`
    : '';
  const normalizedResult = normalizeCvName(resultFilename);
  const rerankItem: MatchingResult | undefined = searchMeta?.rerank?.results?.find(
    r => {
      const resultId = result?.id !== undefined && result?.id !== null ? String(result.id) : '';
      const sameProfile = Boolean(
        resultId
        && (
          (r.profile_id !== undefined && r.profile_id !== null && String(r.profile_id) === resultId)
          || (r.document_id !== undefined && r.document_id !== null && String(r.document_id) === resultId)
        ),
      );
      const sameName = [r.cv_file, r.source_cv_file]
        .filter(Boolean)
        .some(value => normalizeCvName(value) === normalizedResult);
      return sameProfile || sameName;
    },
  );

  console.log('[SearchDetailModal] props:', {
    hasResult: Boolean(result),
    jdText: jdText?.slice(0, 50),
    hasJdFile: Boolean(jdFile),
    cvText: cvText?.slice(0, 50),
    cvFilename,
    enableAiMatching,
    hasMatchingResult: Boolean(matchingResult),
    hasRerank: Boolean(rerankItem),
  });

  // Update tab when data changes

  const cachedMatchingResult = matchingCacheKey ? detailMatchingCache.get(matchingCacheKey) : undefined;
  const scopedMatchingResult = matchingResultKey === matchingCacheKey ? matchingResult : cachedMatchingResult || null;
  const displayResult = enableAiMatching ? (scopedMatchingResult || rerankItem || undefined) : undefined;
  const pdfUrl = result?.preview_url || result?.cloudinary_url || '';

  const hasHeatmap = Boolean(
    displayResult?.alignment_matrix_raw && displayResult?.alignment_matrix_masked && displayResult?.heatmap_labels,
  );
  const hasXai = Array.isArray(displayResult?.view_matches) && displayResult.view_matches.length > 0;
  const hasStructured = Boolean(displayResult?.cv_structured || displayResult?.jd_structured);
  const hasCvText = Boolean(cvText?.trim());
  const aiOffMessage = 'AI rerank chua bat.';

  // Always show tabs, but disable if no data
  const isLoading = loading && !displayResult;

  // Auto-select best tab based on available data
  const getDefaultTabForResult = (candidate?: MatchingResult | null): Tab => {
    const candidateHasHeatmap = Boolean(
      candidate?.alignment_matrix_raw && candidate?.alignment_matrix_masked && candidate?.heatmap_labels,
    );
    const candidateHasXai = Array.isArray(candidate?.view_matches) && candidate.view_matches.length > 0;
    const candidateHasStructured = Boolean(candidate?.cv_structured || candidate?.jd_structured);

    if (candidateHasHeatmap) return 'heatmap';
    if (candidateHasXai) return 'xai';
    if (candidateHasStructured) return 'json';
    if (pdfUrl) return 'pdf';
    return 'overview';
  };

  const getDefaultTab = (): Tab => {
    return getDefaultTabForResult(displayResult);
  };

  const [tab, setTab] = useState<Tab>(getDefaultTab);

  // Update tab when data changes
  useEffect(() => {
    if (tab === 'heatmap' && !hasHeatmap) setTab(getDefaultTab());
  }, [hasHeatmap, hasXai, hasStructured]);

  useEffect(() => {
    if (!result) return;

    // Only call matching API when the user explicitly enabled AI rerank.
    if (!enableAiMatching || (!jdText?.trim() && !jdFile)) {
      setMatchingResult(null);
      setMatchingResultKey(null);
      setTab(pdfUrl ? 'pdf' : 'overview');
      return;
    }

    const cached = matchingCacheKey ? detailMatchingCache.get(matchingCacheKey) : undefined;
    if (cached) {
      setLoading(false);
      setMatchingResult(cached);
      setMatchingResultKey(matchingCacheKey);
      setTab(getDefaultTabForResult(cached));
      return;
    }

    if (rerankItem) {
      if (matchingCacheKey) detailMatchingCache.set(matchingCacheKey, rerankItem);
      setMatchingResult(rerankItem);
      setMatchingResultKey(matchingCacheKey);
      setTab(getDefaultTabForResult(rerankItem));
      if (hasFullAiDetail(rerankItem)) {
        setLoading(false);
        return;
      }
    } else {
      setMatchingResult(null);
      setMatchingResultKey(null);
    }

    setLoading(true);

    void (async () => {
      try {
        const parsedDocumentId = typeof result.id === 'number' ? result.id : Number.parseInt(String(result.id), 10);
        const apiResult = await getCvHeatmap({
          jdText,
          jdFile: jdFile || undefined,
          cvDocumentId: cvText ? undefined : (Number.isFinite(parsedDocumentId) ? parsedDocumentId : undefined),
          cvText,
          cvFilename,
          modelId,
        });
        console.log('Matching API result:', apiResult);
        if (apiResult.ok && apiResult.result.data) {
          const data = apiResult.result.data as MatchingResult;
          console.log('Matching data:', data);
          if (matchingCacheKey) detailMatchingCache.set(matchingCacheKey, data);
          setMatchingResult(data);
          setMatchingResultKey(matchingCacheKey);
          setTab(getDefaultTabForResult(data));
        } else {
          console.log('Matching API failed:', apiResult.result);
        }
      } catch (e) {
        console.error('Matching error:', e);
        // Silently fail - just show overview
        setMatchingResult(null);
        setMatchingResultKey(null);
        setTab('overview');
      } finally {
        setLoading(false);
      }
    })();
  }, [resultKey, matchingCacheKey, jdText, jdFile, enableAiMatching, pdfUrl, rerankItem]);

  const handleCellClick = (rowIndex: number, colIndex: number, score: number, _result?: MatchingResult, cvKey?: string, jdKey?: string) => {
    if (!displayResult) return;
    // Prefer key extracted from BE label; fall back to hardcoded array index lookup
    const cv = cvKey || CV_VIEW_KEYS[rowIndex];
    const jd = jdKey || JD_VIEW_KEYS[colIndex];
    if (!cv || !jd) return;
    setCellDetail({
      cvKey: cv,
      jdKey: jd,
      cvLabel: VIEW_LABEL_MAP[cv] ?? cv,
      jdLabel: VIEW_LABEL_MAP[jd] ?? jd,
      score,
      cvEvidence: extractStructuredField(displayResult.cv_structured, cv),
      jdEvidence: extractStructuredField(displayResult.jd_structured, jd),
      rowIndex,
      colIndex,
    });
  };

  if (!result) return null;

  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div
        className="file-modal-content search-detail-modal"
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header ranking-detail-header">
          <div className="ranking-detail-title">
            <div>
              <h3 title={result.filename}>{result.filename}</h3>
              <div className="ranking-detail-meta">
                <span>ID #{result.id}</span>
                {result.text_length ? (
                  <span>{result.text_length.toLocaleString('vi-VN')} ký tự</span>
                ) : (
                  <span>PDF</span>
                )}
                {result.indexed_at && <span>Indexed {result.indexed_at}</span>}
                <div className="ranking-detail-meter">
                  <div style={{ width: `${Math.round(result.search_score * 100)}%` }} />
                </div>
                {displayResult && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: displayResult.match ? '#16a34a' : '#dc2626' }} />
                    <span style={{ fontSize: 14, fontWeight: 800, color: '#0f172a', fontFamily: 'ui-monospace, monospace' }}>
                      {displayResult.score.toFixed(1)}<small style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>/10</small>
                    </span>
                    <span style={{
                      padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 800,
                      background: displayResult.match ? '#f0fdf4' : '#fef2f2',
                      color: displayResult.match ? '#15803d' : '#b91c1c',
                      border: `1px solid ${displayResult.match ? '#bbf7d0' : '#fecaca'}`,
                    }}>
                      {displayResult.label}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
          <button className="close-modal" onClick={onClose} aria-label="Đóng">&times;</button>
        </div>

        <div className="ranking-detail-tabs" role="tablist">
          <button
            type="button"
            className={tab === 'heatmap' ? 'active' : ''}
            onClick={() => setTab('heatmap')}
          >
            Heatmap
            {!hasHeatmap && !isLoading && <span className="tab-badge">off</span>}
            {isLoading && <span className="tab-badge loading">...</span>}
          </button>
          <button
            type="button"
            className={tab === 'xai' ? 'active' : ''}
            onClick={() => setTab('xai')}
          >
            XAI giải thích
            {!hasXai && !isLoading && <span className="tab-badge">off</span>}
          </button>
          <button
            type="button"
            className={tab === 'pdf' ? 'active' : ''}
            onClick={() => setTab('pdf')}
          >
            CV PDF
            {!pdfUrl && <span className="tab-badge">off</span>}
          </button>
          <button
            type="button"
            className={tab === 'overview' ? 'active' : ''}
            onClick={() => setTab('overview')}
          >
            Tổng quan
          </button>
          <button
            type="button"
            className={tab === 'json' ? 'active' : ''}
            onClick={() => setTab('json')}
          >
            Structured JSON
            {!hasStructured && !isLoading && <span className="tab-badge">off</span>}
          </button>
        </div>

        <div className="modal-body ranking-detail-body" style={{ position: 'relative' }}>
          {isLoading && (
            <div className="detail-loading">
              <div className="detail-spinner" />
              <span>Đang phân tích CV vs JD bằng AI...</span>
            </div>
          )}

          {error && !isLoading && (
            <div className="detail-error">{error}</div>
          )}

          {!isLoading && !error && tab === 'heatmap' && hasHeatmap && displayResult && (
            <div className="ranking-detail-section">
              <HeatmapSection
                result={displayResult}
                onCellClick={(i, j, score) => handleCellClick(i, j, score)}
              />
            </div>
          )}

          {!isLoading && !error && tab === 'heatmap' && !hasHeatmap && !enableAiMatching && (
            <div className="detail-empty">
              <span>{aiOffMessage}</span>
            </div>
          )}

          {!isLoading && !error && tab === 'heatmap' && !hasHeatmap && enableAiMatching && (
            <div className="detail-empty">
              {loading ? (
                <span>Đang tải heatmap...</span>
              ) : (
                <span>Đang phân tích CV vs JD để tạo heatmap...</span>
              )}
            </div>
          )}

          {!isLoading && !error && tab === 'xai' && hasXai && displayResult && (
            <div className="ranking-detail-section">
              <XaiExplanation matches={displayResult.view_matches!} />
            </div>
          )}

          {!isLoading && !error && tab === 'xai' && !hasXai && !enableAiMatching && (
            <div className="detail-empty">
              <span>{aiOffMessage}</span>
            </div>
          )}

          {!isLoading && !error && tab === 'xai' && !hasXai && enableAiMatching && (
            <div className="detail-empty">
              {loading ? <span>Đang tải XAI...</span> : <span>Chưa có dữ liệu XAI.</span>}
            </div>
          )}

          {!isLoading && !error && tab === 'pdf' && pdfUrl && (
            <div className="ranking-detail-section" style={{ height: '100%' }}>
              <iframe
                src={pdfUrl}
                title={`PDF ${result.filename}`}
                width="100%"
                height="100%"
                style={{ border: 'none', minHeight: '500px' }}
              />
            </div>
          )}

          {!isLoading && !error && tab === 'overview' && (
            <div className="ranking-detail-section">
              {displayResult?.cv_structured && (
                <div>
                  <h4>CV structured</h4>
                  <StructuredDataViewer data={displayResult.cv_structured} />
                </div>
              )}
              {displayResult?.jd_structured && (
                <div>
                  <h4>JD structured</h4>
                  <StructuredDataViewer data={displayResult.jd_structured} />
                </div>
              )}
              {hasCvText && (
                <div>
                  <h4>Profile text</h4>
                  <pre className="web-profile-text-pre">{cvText}</pre>
                </div>
              )}
              {!displayResult && !hasCvText && (
                <div className="detail-empty">
                  <span>Không có dữ liệu structured.</span>
                </div>
              )}
              {displayResult && pdfUrl && (
                <div style={{ marginTop: 16 }}>
                  <h4>CV PDF</h4>
                  <iframe
                    src={pdfUrl}
                    title={`PDF ${result.filename}`}
                    width="100%"
                    height="600"
                    style={{ border: '1px solid #e2e8f0', borderRadius: 12 }}
                  />
                </div>
              )}
            </div>
          )}

          {!isLoading && !error && tab === 'json' && (
            <div className="ranking-detail-section ranking-detail-json">
              {displayResult?.cv_structured && (
                <div>
                  <h4>CV structured</h4>
                  <StructuredDataViewer data={displayResult.cv_structured} />
                </div>
              )}
              {displayResult?.jd_structured && (
                <div>
                  <h4>JD structured</h4>
                  <StructuredDataViewer data={displayResult.jd_structured} />
                </div>
              )}
              {!hasStructured && (
                <div className="detail-empty">
                  <span>{enableAiMatching ? 'Chua co du lieu structured.' : aiOffMessage}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style>{`
        .search-detail-modal {
          max-width: 1100px;
        }
        .detail-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          padding: 60px 24px;
          color: #64748b;
          font-size: 14px;
        }
        .detail-spinner {
          width: 36px;
          height: 36px;
          border: 3px solid #e2e8f0;
          border-top-color: #0891b2;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        .detail-error {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 24px;
          color: #dc2626;
          font-size: 14px;
          font-weight: 600;
        }
        .detail-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 24px;
          color: #94a3b8;
          font-size: 14px;
        }
        .web-profile-text-pre {
          margin: 0;
          padding: 18px;
          min-height: 420px;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          background: #f8fafc;
          color: #0f172a;
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 13px;
          line-height: 1.65;
          white-space: pre-wrap;
          overflow: auto;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
      <CellDetailModal detail={cellDetail} onClose={() => setCellDetail(null)} />
    </div>
  );
}
