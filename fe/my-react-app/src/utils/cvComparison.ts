import { JD_VIEW_KEYS, VIEW_LABEL_MAP } from '../constants/views';
import type { RankingResultItem } from '../types/ranking';
import type { ComparisonVerdict, DimensionRow } from '../types/comparison';

// Score is on a 0..10 scale (see RankingDetailModal). Nếu chênh lệch nhỏ hơn
// ngưỡng này thì coi là "quá sát" → không khẳng định người thắng chắc chắn.
export const CLOSE_CALL_THRESHOLD = 0.3;

// Ngưỡng coi như một bên vượt trội ở 1 tiêu chí (similarity 0..1).
const DIMENSION_MARGIN = 0.05;

/**
 * Điểm 1 ứng viên ở 1 cột JD = similarity lớn nhất trong các view_matches
 * có jd_view trùng key (max-over-CV-views). Thiếu match → 0.
 */
function dimensionScore(result: RankingResultItem, jdKey: string): number {
  const matches = result.view_matches ?? [];
  let best = 0;
  let found = false;
  for (const match of matches) {
    if (match.jd_view === jdKey) {
      found = true;
      if (match.similarity > best) best = match.similarity;
    }
  }
  return found ? best : 0;
}

const pct = (value: number) => `${Math.round(value * 100)}%`;

/**
 * Suy ra verdict head-to-head từ kết quả ranking.
 *
 * cvA/cvB là danh tính ổn định theo thứ tự người dùng chọn (orderNames) để
 * khớp với preview; người thắng được trỏ qua winnerIndex (không giả định
 * cvA luôn dẫn đầu). Nếu không khớp được tên thì rơi về thứ tự score.
 * Trả về null nếu chưa đủ 2 kết quả.
 */
export function buildVerdict(
  results: RankingResultItem[],
  orderNames?: string[],
): ComparisonVerdict | null {
  if (results.length < 2) return null;

  let ordered: RankingResultItem[] = results.slice(0, 2);
  if (orderNames && orderNames.length >= 2) {
    const byName = new Map(results.map((r) => [r.cv_file, r]));
    const a = byName.get(orderNames[0]);
    const b = byName.get(orderNames[1]);
    if (a && b && a !== b) ordered = [a, b];
  }
  const [cvA, cvB] = ordered;

  const margin = Math.abs(cvA.score - cvB.score);
  const isClose = margin < CLOSE_CALL_THRESHOLD;
  const winnerIndex: 0 | 1 | null = isClose ? null : cvA.score >= cvB.score ? 0 : 1;

  const dimensionRows: DimensionRow[] = JD_VIEW_KEYS.map((jdKey) => {
    const scoreA = dimensionScore(cvA, jdKey);
    const scoreB = dimensionScore(cvB, jdKey);
    let winner: 'A' | 'B' | 'tie' = 'tie';
    if (scoreA - scoreB > DIMENSION_MARGIN) winner = 'A';
    else if (scoreB - scoreA > DIMENSION_MARGIN) winner = 'B';
    return { jdKey, label: VIEW_LABEL_MAP[jdKey] ?? jdKey, scoreA, scoreB, winner };
  });

  const advantagesA: string[] = [];
  const advantagesB: string[] = [];
  for (const row of dimensionRows) {
    if (row.winner === 'A') {
      advantagesA.push(`${row.label} (${pct(row.scoreA)} vs ${pct(row.scoreB)})`);
    } else if (row.winner === 'B') {
      advantagesB.push(`${row.label} (${pct(row.scoreB)} vs ${pct(row.scoreA)})`);
    }
  }

  return { cvA, cvB, winnerIndex, isClose, margin, dimensionRows, advantagesA, advantagesB };
}
