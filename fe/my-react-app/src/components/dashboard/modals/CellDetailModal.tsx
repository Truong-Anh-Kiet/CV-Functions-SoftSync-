import { getHeatmapColor, getHeatmapTextColor } from '../../../utils/heatmap';

export interface CellDetailState {
  cvKey: string;
  jdKey: string;
  cvLabel: string;
  jdLabel: string;
  score: number;
  cvEvidence: string;
  jdEvidence: string;
  rowIndex: number;
  colIndex: number;
}

interface CellDetailModalProps {
  detail: CellDetailState | null;
  onClose: () => void;
}

const getScoreBadgeClass = (score: number) => {
  if (score >= 0.75) return 'cell-score-high';
  if (score >= 0.5) return 'cell-score-mid';
  return 'cell-score-low';
};

const isMissingEvidence = (text: string) =>
  text === '(Không có trường này)' || text === '(Không có dữ liệu)';

export default function CellDetailModal({ detail, onClose }: CellDetailModalProps) {
  if (!detail) return null;
  const scoreLabel =
    detail.score >= 0.75 ? 'Khớp mạnh' : detail.score >= 0.5 ? 'Khớp một phần' : 'Không khớp';

  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content cell-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header cell-detail-modal-header">
          <div className="cell-detail-title-group">
            <h3>Chi tiết điểm tương đồng</h3>
            <span className="modal-subtitle">
              CV: <strong>{detail.cvLabel}</strong> &nbsp;↔&nbsp; JD: <strong>{detail.jdLabel}</strong>
            </span>
          </div>
          <div className="cell-detail-header-right">
            <div className={`cell-detail-score-badge ${getScoreBadgeClass(detail.score)}`}>
              <span className="cell-detail-score-num">{detail.score.toFixed(4)}</span>
              <span className="cell-detail-score-label">{scoreLabel}</span>
            </div>
            <button className="close-modal" onClick={onClose}>&times;</button>
          </div>
        </div>

        <div className="cell-detail-score-bar-wrap">
          <div
            className="cell-detail-score-bar-fill"
            style={{
              width: `${Math.round(detail.score * 100)}%`,
              backgroundColor: getHeatmapColor(detail.score),
            }}
          />
          <span className="cell-detail-score-bar-pct">{Math.round(detail.score * 100)}%</span>
        </div>

        <div className="modal-body cell-detail-modal-body">
          <div className="cell-detail-pane">
            <div className="cell-detail-pane-head cv-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M7 8h10M7 12h6M7 16h8" />
              </svg>
              CV — {detail.cvLabel}
            </div>
            <div className="cell-detail-evidence-box">
              {isMissingEvidence(detail.cvEvidence) ? (
                <span className="cell-detail-missing">{detail.cvEvidence}</span>
              ) : (
                <pre className="cell-detail-pre">{detail.cvEvidence}</pre>
              )}
            </div>
          </div>

          <div className="cell-detail-divider">
            <div className="cell-detail-divider-line" />
            <span
              className="cell-detail-divider-score"
              style={{
                backgroundColor: getHeatmapColor(detail.score),
                color: getHeatmapTextColor(detail.score),
              }}
            >
              {detail.score.toFixed(2)}
            </span>
            <div className="cell-detail-divider-line" />
          </div>

          <div className="cell-detail-pane">
            <div className="cell-detail-pane-head jd-head">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1={16} y1={13} x2={8} y2={13} />
                <line x1={16} y1={17} x2={8} y2={17} />
                <line x1={10} y1={9} x2={8} y2={9} />
              </svg>
              JD — {detail.jdLabel}
            </div>
            <div className="cell-detail-evidence-box">
              {isMissingEvidence(detail.jdEvidence) ? (
                <span className="cell-detail-missing">{detail.jdEvidence}</span>
              ) : (
                <pre className="cell-detail-pre">{detail.jdEvidence}</pre>
              )}
            </div>
          </div>
        </div>

        <div className="cell-detail-footer">
          <span>
            Điểm <strong>{detail.score.toFixed(4)}</strong> thể hiện mức độ tương đồng semantic giữa trường <em>{detail.cvLabel}</em> của CV và yêu cầu <em>{detail.jdLabel}</em> của JD.
          </span>
        </div>
      </div>
    </div>
  );
}
