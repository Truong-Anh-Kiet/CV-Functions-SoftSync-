import type { RankingResultItem } from './ranking';

export interface DimensionRow {
  jdKey: string;
  label: string;
  scoreA: number; // 0..1 similarity for CV A (leading)
  scoreB: number; // 0..1 similarity for CV B
  winner: 'A' | 'B' | 'tie';
}

export interface ComparisonVerdict {
  cvA: RankingResultItem; // CV vị trí thứ nhất (theo thứ tự người dùng chọn)
  cvB: RankingResultItem; // CV vị trí thứ hai
  winnerIndex: 0 | 1 | null; // 0 = cvA, 1 = cvB, null = quá sát / cần review
  isClose: boolean;
  margin: number; // |scoreA - scoreB| on the 0..10 score scale
  dimensionRows: DimensionRow[];
  advantagesA: string[]; // tiêu chí cvA nhỉnh hơn
  advantagesB: string[]; // tiêu chí cvB nhỉnh hơn
}
