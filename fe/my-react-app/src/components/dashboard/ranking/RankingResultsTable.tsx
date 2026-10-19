import type { RankingResultItem } from '../../../types/ranking';
import { IconEye } from '../icons';

interface RankingResultsTableProps {
  results: RankingResultItem[];
  loading: boolean;
  onViewDetail: (result: RankingResultItem) => void;
  onExportCsv?: () => void;
}

const scorePercent = (score10: number) => Math.max(0, Math.min(100, (score10 / 10) * 100));

export default function RankingResultsTable({
  results,
  loading,
  onViewDetail,
  onExportCsv,
}: RankingResultsTableProps) {
  return (
    <section className="search-results-panel ranking-results-panel">
      <div className="results-panel-head ranking-results-head">
        <h2>Kết quả <span>· {results.length}</span></h2>
        {results.length > 0 && onExportCsv && (
          <button type="button" className="ranking-link-btn" onClick={onExportCsv}>
            Tải CSV
          </button>
        )}
      </div>

      {results.length === 0 ? (
        <div className="empty-search-state">
          <strong>{loading ? 'Đang xếp hạng…' : 'Chưa có kết quả'}</strong>
          <span>Nhập JD, chọn CV và bấm "Bắt đầu xếp hạng".</span>
        </div>
      ) : (
        <div className="search-results-table-wrap">
          <table className="search-results-table ranking-results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>CV</th>
                <th>Score</th>
                <th aria-label="Actions"></th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={`${result.rank}-${result.cv_file}`}>
                  <td className="search-rank">{result.rank}</td>
                  <td className="search-cv-name">
                    <strong title={result.cv_file}>{result.cv_file}</strong>
                  </td>
                  <td>
                    <div className="ranking-score-cell">
                      <div className="score-meter">
                        <div style={{ width: `${scorePercent(result.score)}%` }} />
                      </div>
                      <span className="score-value">{result.score.toFixed(2)}</span>
                      <i
                        className={`ranking-match-dot ${result.match ? 'matched' : 'mismatch'}`}
                        title={result.label}
                      />
                    </div>
                  </td>
                  <td>
                    <button
                      className="icon-action"
                      title="Xem chi tiết"
                      aria-label={`Xem chi tiết ${result.cv_file}`}
                      onClick={() => onViewDetail(result)}
                    >
                      <IconEye />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
