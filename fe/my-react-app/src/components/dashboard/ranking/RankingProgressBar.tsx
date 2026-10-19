import { useEffect, useState } from 'react';

interface RankingProgressBarProps {
  active: boolean;
  cvCount: number;
}

const PER_CV_ESTIMATE_SEC = 8;

export default function RankingProgressBar({ active, cvCount }: RankingProgressBarProps) {
  const [percent, setPercent] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) {
      setPercent(0);
      setElapsed(0);
      return;
    }
    const startedAt = Date.now();
    const estimateSec = Math.max(6, cvCount * PER_CV_ESTIMATE_SEC * 0.5);
    const id = setInterval(() => {
      const seconds = (Date.now() - startedAt) / 1000;
      setElapsed(seconds);
      const ratio = Math.min(0.92, seconds / estimateSec);
      setPercent(ratio * 100);
    }, 250);
    return () => clearInterval(id);
  }, [active, cvCount]);

  if (!active) return null;

  return (
    <div className="ranking-progress">
      <div className="ranking-progress-bar">
        <div className="ranking-progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="ranking-progress-label">Đang xếp hạng {cvCount} CV · {elapsed.toFixed(0)}s</span>
    </div>
  );
}
