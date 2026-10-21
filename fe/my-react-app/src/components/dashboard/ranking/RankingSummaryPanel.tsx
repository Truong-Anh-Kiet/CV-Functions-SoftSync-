interface RankingSummaryPanelProps {
  totalCvCount: number;
  jdSummary: string;
  loading: boolean;
  meta: { elapsed_seconds?: number } | null;
  onRun: () => void;
  onClearResults: () => void;
  hasResults: boolean;
}

export default function RankingSummaryPanel({
  totalCvCount,
  jdSummary,
  loading,
  meta,
  onRun,
  onClearResults,
  hasResults,
}: RankingSummaryPanelProps) {
  return (
    <div className="ranking-controlbar">
      <div className="ranking-controlbar-stat">
        <strong>{totalCvCount}</strong>
        <span>CV đã chọn</span>
      </div>

      <div className="ranking-controlbar-divider" />

      <div className="ranking-controlbar-field ranking-controlbar-jd">
        <span>JD</span>
        <p title={jdSummary}>{jdSummary || '—'}</p>
      </div>

      {meta?.elapsed_seconds && (
        <span className="ranking-controlbar-elapsed">{meta.elapsed_seconds.toFixed(1)}s</span>
      )}

      <div className="ranking-controlbar-actions">
        {hasResults && (
          <button
            type="button"
            className="ranking-link-btn"
            onClick={onClearResults}
            disabled={loading}
          >
            Xoá kết quả
          </button>
        )}
        <button
          className="save-btn search-primary-btn ranking-run-btn"
          onClick={onRun}
          disabled={loading || totalCvCount === 0}
        >
          {loading ? 'Đang xếp hạng…' : 'Bắt đầu xếp hạng'}
        </button>
      </div>
    </div>
  );
}
