import type { MatchingResult } from '../../../types/matching';
import { CV_VIEW_KEYS, JD_VIEW_KEYS, VIEW_LABEL_MAP } from '../../../constants/views';

export type CrossViewTopK = '5' | '10' | '20' | 'all';

interface CrossViewRankingModalProps {
  open: boolean;
  result: MatchingResult | null;
  topK: CrossViewTopK;
  onTopKChange: (value: CrossViewTopK) => void;
  onClose: () => void;
}

export default function CrossViewRankingModal({ open, result, topK, onTopKChange, onClose }: CrossViewRankingModalProps) {
  if (!open || !result) return null;
  const matrix = result.alignment_matrix_raw ?? [];
  type CrossPair = { cvLabel: string; jdLabel: string; similarity: number };
  const pairs: CrossPair[] = [];
  for (let i = 0; i < CV_VIEW_KEYS.length; i++) {
    for (let j = 0; j < JD_VIEW_KEYS.length; j++) {
      const cvKey = CV_VIEW_KEYS[i];
      const jdKey = JD_VIEW_KEYS[j];
      pairs.push({ cvLabel: VIEW_LABEL_MAP[cvKey] ?? cvKey, jdLabel: VIEW_LABEL_MAP[jdKey] ?? jdKey, similarity: matrix[i]?.[j] ?? 0 });
    }
  }
  pairs.sort((a, b) => b.similarity - a.similarity);
  const visible = pairs.slice(0, topK === 'all' ? pairs.length : Number(topK));
  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content cross-view-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header cross-view-modal-head">
          <div><h3>Cross-View Ranking</h3><span className="modal-subtitle">{pairs.length} cặp · sắp xếp theo score</span></div>
          <div className="cross-view-controls">
            <label className="cross-view-topk-label">Hiển thị:&nbsp;<select value={topK} onChange={(e) => onTopKChange(e.target.value as CrossViewTopK)}><option value="5">Top 5</option><option value="10">Top 10</option><option value="20">Top 20</option><option value="all">Tất cả ({pairs.length})</option></select></label>
            <button className="close-modal" onClick={onClose}>&times;</button>
          </div>
        </div>
        <div className="modal-body cross-view-modal-body">
          <table className="cross-view-table">
            <thead><tr><th style={{ width: '60px' }}>Rank</th><th>CV View Component</th><th>JD Requirement Component</th><th style={{ width: '100px', textAlign: 'right' }}>Score</th></tr></thead>
            <tbody>{visible.map((m, i) => {
              const pass = m.similarity >= 0.5;
              return (<tr key={`${m.cvLabel}-${m.jdLabel}-${i}`}><td className="cv-rank-cell">#{i + 1}</td><td>{m.cvLabel}</td><td>{m.jdLabel}</td><td className="cv-score-cell"><span className={`score-badge table-badge ${pass ? 'green' : 'red'}`}>{m.similarity.toFixed(4)}</span></td></tr>);
            })}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
