import type { UploadedFile } from '../../../types/dashboard';
import type { MatchingResult } from '../../../types/matching';
import type { MatchingMeta } from '../../../hooks/useMatching';
import type { ModelOption } from '../../../types/model';
import FullDocumentPanel from '../matching/FullDocumentPanel';
import HeatmapSection from '../matching/HeatmapSection';
import XaiExplanation from '../matching/XaiExplanation';

interface CvJdMatchingSectionProps {
  matchingCv: UploadedFile | undefined;
  matchingJd: UploadedFile | undefined;
  primaryMatchingResult: MatchingResult | undefined;
  matchingLoading: boolean;
  saveCv: boolean;
  setSaveCv: (value: boolean) => void;
  jdMode: 'file' | 'text';
  setJdMode: (mode: 'file' | 'text') => void;
  jdText: string;
  setJdText: (value: string) => void;
  matchingMeta: MatchingMeta | null;
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  onPreviewUpload: (e: React.ChangeEvent<HTMLInputElement>, category: 'CV' | 'JD') => void;
  onRemove: (id: string) => void;
  onRunMatching: () => void;
  onOpenCrossView: (result: MatchingResult) => void;
  onOpenStructured: () => void;
  selectedHeatmapCell?: { rowIndex: number; colIndex: number } | null;
  onHeatmapCellClick?: (rowIndex: number, colIndex: number, score: number, result: MatchingResult) => void;
}

export default function CvJdMatchingSection({
  matchingCv,
  matchingJd,
  primaryMatchingResult,
  matchingLoading,
  saveCv,
  setSaveCv,
  jdMode,
  setJdMode,
  jdText,
  setJdText,
  matchingMeta,
  modelOptions,
  selectedModel,
  setSelectedModel,
  onPreviewUpload,
  onRemove,
  onRunMatching,
  onOpenCrossView,
  onOpenStructured,
  selectedHeatmapCell,
  onHeatmapCellClick,
}: CvJdMatchingSectionProps) {
  const timingTitle = matchingMeta
    ? `Trích xuất (OpenAI) ${matchingMeta.extraction_seconds?.toFixed(2) ?? '—'}s · Model ${matchingMeta.inference_seconds?.toFixed(2) ?? '—'}s${matchingMeta.model_used ? ` · ${matchingMeta.model_used}` : ''}`
    : undefined;

  return (
    <div className="matching-workspace">
      <div className="single-match-toolbar">
        <input type="file" accept=".pdf" onChange={(e) => onPreviewUpload(e, 'CV')} id="sm-cv" hidden />
        <input type="file" accept=".pdf" onChange={(e) => onPreviewUpload(e, 'JD')} id="sm-jd" hidden />

        <div className="toolbar-group toolbar-left">
          <label className="model-selector-label">
            <span>Model AI</span>
            <select
              className="model-selector"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={matchingLoading || modelOptions.length === 0}
              title="Chọn model AI để matching"
            >
              {modelOptions.length === 0 ? (
                <option value="">Đang tải model...</option>
              ) : (
                modelOptions.map(opt => (
                  <option key={opt.id} value={opt.id}>{opt.display_name}</option>
                ))
              )}
            </select>
          </label>
        </div>

        <div className="toolbar-group toolbar-right">
          {matchingMeta?.elapsed_seconds != null && (
            <span className="cmp-elapsed" title={timingTitle}>⏱ {matchingMeta.elapsed_seconds.toFixed(2)}s</span>
          )}
          <label className="save-cv-toggle">
            <input type="checkbox" checked={saveCv} onChange={(e) => setSaveCv(e.target.checked)} disabled={matchingLoading} />
            Lưu CV
          </label>
          <button className="save-btn run-match-btn" onClick={onRunMatching} disabled={matchingLoading}>
            {matchingLoading ? "Đang chạy AI..." : saveCv ? "Lưu CV & Matching" : "Chạy Matching"}
          </button>
        </div>
      </div>

      <div className="full-doc-split">
        <FullDocumentPanel title="CV" file={matchingCv} previewUrl={primaryMatchingResult?.highlighted_cv_url} inputId="sm-cv" onRemove={onRemove} />

        {/* JD panel: compact Text/PDF toggle in the header (like CV Ranking / Comparison) */}
        <section className="full-doc-panel">
          <div className="full-doc-header">
            <h3>JD</h3>
            <div className="search-mode-tabs" role="tablist" aria-label="Chế độ nhập JD">
              <button type="button" className={jdMode === 'text' ? 'active' : ''} onClick={() => setJdMode('text')} disabled={matchingLoading}>Text</button>
              <button type="button" className={jdMode === 'file' ? 'active' : ''} onClick={() => setJdMode('file')} disabled={matchingLoading}>PDF</button>
            </div>
            {jdMode === 'file' && matchingJd && (
              <div className="full-doc-meta">
                <span title={matchingJd.filename}>{matchingJd.filename}</span>
                <button className="delete-btn compact-btn" onClick={() => onRemove(matchingJd.id)}>Gỡ bỏ</button>
              </div>
            )}
          </div>

          {jdMode === 'text' ? (
            <textarea
              className="search-textarea"
              style={{ width: '100%', flex: 1, minHeight: '320px', resize: 'vertical', boxSizing: 'border-box' }}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Dán nội dung Job Description vào đây. Ví dụ: Senior Backend Engineer, 5+ năm kinh nghiệm Python, FastAPI, PostgreSQL, Docker..."
              spellCheck={false}
              disabled={matchingLoading}
            />
          ) : matchingJd ? (
            <iframe
              src={primaryMatchingResult?.highlighted_jd_url || matchingJd.preview_url}
              title={matchingJd.filename}
              className="full-doc-frame"
            />
          ) : (
            <label htmlFor="sm-jd" className="empty-doc-panel upload-dropzone" aria-label="Tải lên JD PDF">
              <div className="upload-icon-circle large">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <span className="upload-dropzone-text">Bấm để tải lên JD (PDF)</span>
            </label>
          )}
        </section>
      </div>

      {primaryMatchingResult && (
        <>
          <div className="match-summary">
            <div><span>Score</span><strong className="score-badge main">{primaryMatchingResult.score.toFixed(2)} / 10</strong></div>
            <div><span>Label</span><strong className={primaryMatchingResult.match ? 'match-label matched' : 'match-label mismatch'}>{primaryMatchingResult.label}</strong></div>
            <div><span>Coverage</span><strong>{primaryMatchingResult.cv_view_coverage} CV | {primaryMatchingResult.jd_view_coverage} JD</strong></div>
          </div>

          <div className="result-actions">
            <button type="button" className="result-action-btn primary" onClick={() => onOpenCrossView(primaryMatchingResult)} disabled={!primaryMatchingResult.alignment_matrix_raw?.length}>Xem ranking cross-views (50 cặp)</button>
            <button type="button" className="result-action-btn" onClick={onOpenStructured} disabled={!primaryMatchingResult.cv_structured && !primaryMatchingResult.jd_structured}>Xem Structured (JSON)</button>
          </div>

          <HeatmapSection
            result={primaryMatchingResult}
            selectedCell={selectedHeatmapCell}
            onCellClick={onHeatmapCellClick}
          />
          <XaiExplanation matches={primaryMatchingResult.view_matches} />
        </>
      )}
    </div>
  );
}
