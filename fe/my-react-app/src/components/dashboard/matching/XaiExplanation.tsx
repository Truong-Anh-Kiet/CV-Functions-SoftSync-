import type { ViewMatch } from '../../../types/matching';
import { stringifyEvidence } from '../../../utils/format';

interface XaiExplanationProps {
  matches: ViewMatch[] | undefined;
}

export default function XaiExplanation({ matches }: XaiExplanationProps) {
  if (!matches || matches.length === 0) return null;
  return (
    <section className="xai-panel">
      <div className="xai-header">
        <h3>XAI View Explanation</h3>
        <div className="xai-legend">
          <span><i className="legend-dot green" /> Khớp mạnh</span>
          <span><i className="legend-dot orange" /> Khớp một phần</span>
          <span><i className="legend-dot red" /> Không khớp / thiếu</span>
        </div>
      </div>
      <div className="xai-list">
        {matches.map(match => (
          <article className={`xai-item ${match.color}`} key={`${match.cv_view}-${match.jd_view}`}>
            <div className="xai-item-head">
              <strong className="xai-title-label">{match.cv_label} ↔ {match.jd_label}</strong>
              <span className="xai-score-tag">{match.similarity.toFixed(4)}</span>
            </div>
            <p className="xai-reason-text">{match.reason}</p>
            <div className="xai-evidence-grid">
              <div><span>CV evidence</span><p>{stringifyEvidence(match.cv_evidence)}</p></div>
              <div><span>JD evidence</span><p>{stringifyEvidence(match.jd_evidence)}</p></div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
