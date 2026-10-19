import type { SearchApiResponse, ReindexApiResponse } from '../../../types/search';
import type { ModelOption } from '../../../types/model';

interface SearchSummaryPanelProps {
  currentCvTotal: number;
  currentSearchMeta: SearchApiResponse['data'] | null;
  currentReindexSummary: ReindexApiResponse['data'] | null;
  searchMeta: SearchApiResponse['data'] | null;
  selectedModel: string;
  modelOptions: ModelOption[];
  showIndexDetails?: boolean;
  headingLabel?: string;
  title?: string;
  summaryCount?: number | string;
  compact?: boolean;
  statusMessage?: string;
  statusActive?: boolean;
}

function formatUsdVndRate(rate: number) {
  return Math.round(rate).toLocaleString('de-DE');
}

export default function SearchSummaryPanel({
  currentCvTotal,
  currentSearchMeta,
  currentReindexSummary,
  searchMeta,
  selectedModel,
  modelOptions,
  showIndexDetails = true,
  headingLabel = 'Trạng thái index',
  title = 'CV database',
  summaryCount,
  compact = false,
  statusMessage = 'San sang chay tim kiem',
  statusActive = false,
}: SearchSummaryPanelProps) {

  const indexedCount = currentSearchMeta?.indexed_cvs ?? currentReindexSummary?.successful ?? 0;
  const totalCount = summaryCount ?? currentCvTotal;
  const progressPercent = Number(totalCount) > 0 ? Math.round((indexedCount / Number(totalCount)) * 100) : 0;

  return (
    <aside className={`search-panel search-summary-panel ${compact ? 'compact' : ''}`}>
      <div className="summary-header">
        <div className="summary-header-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
        </div>
        <div>
          <span>{headingLabel}</span>
          <h2>{title}</h2>
        </div>
      </div>

      <div className="summary-count-badge">
        <div className="summary-count-inner">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          <div>
            <strong>{totalCount}</strong>
            <span>hồ sơ CV</span>
          </div>
        </div>
      </div>

      {compact && (
        <div className={`summary-run-status ${statusActive ? 'active' : ''}`}>
          <span>{statusActive ? 'Dang chay' : 'Trang thai'}</span>
          <strong>{statusMessage}</strong>
        </div>
      )}

      <div className="summary-progress-section">
        <div className="summary-progress-header">
          <span>Tiến trình index</span>
          <strong>{indexedCount}/{totalCount}</strong>
        </div>
        <div className="summary-progress-bar">
          <div
            className="summary-progress-fill"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className="summary-progress-label">{progressPercent}% đã hoàn tất</span>
      </div>

      <div className="search-metric-grid">
        <div className="metric-card">
          <div className="metric-icon metric-icon--blue">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
          <div>
            <span>Indexed</span>
            <strong>{currentSearchMeta?.indexed_cvs ?? currentReindexSummary?.successful ?? '—'}</strong>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon metric-icon--green">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
          </div>
          <div>
            <span>Trả về</span>
            <strong>{currentSearchMeta?.returned ?? '—'}</strong>
          </div>
        </div>
        {showIndexDetails && (
          <>
            <div className="metric-card">
              <div className="metric-icon metric-icon--purple">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/>
                  <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
              </div>
              <div>
                <span>Index mới</span>
                <strong>{currentSearchMeta?.indexed_missing ?? '—'}</strong>
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-icon metric-icon--gray">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="1 4 1 10 7 10"/>
                  <path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
                </svg>
              </div>
              <div>
                <span>Bỏ qua</span>
                <strong>{currentSearchMeta?.skipped_cvs?.length ?? currentReindexSummary?.failed ?? '—'}</strong>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="search-index-info">
        <div className="index-info-header">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/>
          </svg>
          <span>Embedding model</span>
        </div>
        <div className="index-info-body">
          <strong>{searchMeta?.embedding_model_id || selectedModel || 'default'}</strong>
          <small>{searchMeta?.sbert_id || modelOptions.find(option => option.id === selectedModel)?.sbert_id || 'AI service'}</small>
        </div>
      </div>

      {!compact && currentReindexSummary && (
        <div className={`index-status ${currentReindexSummary.failed > 0 ? 'warning' : 'success'}`}>
          <div className="index-status-header">
            <strong>{currentReindexSummary.successful}/{currentReindexSummary.total_cvs} CV đã index</strong>
            {currentReindexSummary.failed > 0 && (
              <span className="index-fail-badge">{currentReindexSummary.failed} lỗi</span>
            )}
          </div>
          {currentReindexSummary.failures?.slice(0, 3).map(item => (
            <p key={`${item.id}-${item.filename}`}>{item.filename}: {item.reason}</p>
          ))}
        </div>
      )}

      {searchMeta?.jd_analysis && (
        <div className="index-status success">
          <div className="index-status-header">
            <strong>{searchMeta.jd_analysis.job_title}</strong>
            <span className="index-fail-badge" style={{ background: '#ecfeff', color: '#0e7490', borderColor: '#a5f3fc' }}>
              {(Math.round((searchMeta.jd_analysis.confidence ?? 0) * 100))}%
            </span>
          </div>
          <p>Category: {searchMeta.jd_analysis.job_category}</p>
          <p>Experience: {searchMeta.jd_analysis.required_experience_years ?? 'N/A'} years</p>
          <p>Salary: {searchMeta.jd_analysis.salary_text || 'Khong trich xuat duoc'}</p>
          <p>Location: {searchMeta.jd_analysis.work_location || 'N/A'} | Mode: {searchMeta.jd_analysis.work_mode || 'unknown'}</p>
          <p>Required: {(searchMeta.jd_analysis.required_skills || []).join(', ') || 'N/A'}</p>
          {searchMeta.jd_analysis.preferred_skills?.length ? (
            <p>Preferred: {searchMeta.jd_analysis.preferred_skills.join(', ')}</p>
          ) : null}
          {searchMeta.usd_vnd_rate ? (
            <div className="index-status-footer-note">
              Ty gia dang dung: 1 USD = {formatUsdVndRate(searchMeta.usd_vnd_rate)} VND
            </div>
          ) : null}
        </div>
      )}
    </aside>
  );
}
