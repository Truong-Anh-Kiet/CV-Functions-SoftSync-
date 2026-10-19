import type { ReactNode } from 'react';
import type { SearchApiResponse, SearchCvResult } from '../../../types/search';
import { IconBriefcase, IconClock, IconEye, IconPin, IconTimeline, IconWallet } from '../icons';

interface WebSearchResultsTableProps {
  searchResults: SearchCvResult[];
  searchMeta?: SearchApiResponse['data'] | null;
  searchLoading: boolean;
  loadingLabel?: string;
  onViewCv: (result: SearchCvResult) => void;
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score * 100));
  const color = pct >= 70 ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626';
  return (
    <div className="cv-score-bar-row">
      <div className="cv-score-bar-track">
        <div className="cv-score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="cv-score-bar-label" style={{ color }}>{Math.round(pct)}%</span>
    </div>
  );
}

function BusinessScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color = pct >= 70 ? '#16a34a' : pct >= 40 ? '#d97706' : '#dc2626';
  return (
    <div className="cv-score-bar-row">
      <div className="cv-score-bar-track">
        <div className="cv-score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="cv-score-bar-label" style={{ color }}>{Math.round(pct)}</span>
    </div>
  );
}

function formatBreakdownScore(value: number | undefined, weight: number | undefined) {
  if ((weight ?? 0) <= 0) return 'N/A';
  return Math.round(value ?? 0);
}

function BreakdownChip({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <span className="cv-breakdown-chip">
      <span className="cv-breakdown-icon" aria-hidden="true">{icon}</span>
      <strong>{label}</strong>
      {value}
    </span>
  );
}

function MetaItem({
  icon,
  text,
}: {
  icon: ReactNode;
  text: string;
}) {
  return (
    <span className="cv-meta-item">
      <span className="cv-meta-icon" aria-hidden="true">{icon}</span>
      <span>{text}</span>
    </span>
  );
}

export default function WebSearchResultsTable({
  searchResults,
  searchMeta,
  searchLoading,
  loadingLabel = 'Dang tim kiem...',
  onViewCv,
}: WebSearchResultsTableProps) {
  const breakdownLabels = {
    job_title_match_score: searchMeta?.score_breakdown_labels?.job_title_match_score || 'Vi tri',
    skill_match_score: searchMeta?.score_breakdown_labels?.skill_match_score || 'Ky nang',
    experience_match_score: searchMeta?.score_breakdown_labels?.experience_match_score || 'Kinh nghiem',
    location_match_score: searchMeta?.score_breakdown_labels?.location_match_score || 'Dia diem',
    cv_recency_score: searchMeta?.score_breakdown_labels?.cv_recency_score || 'Do moi',
  };
  const breakdownWeights = {
    job_title_match_score: searchMeta?.ranking_weights?.job_title_match_score,
    skill_match_score: searchMeta?.ranking_weights?.skill_match_score,
    experience_match_score: searchMeta?.ranking_weights?.experience_match_score,
    location_match_score: searchMeta?.ranking_weights?.location_match_score,
    cv_recency_score: searchMeta?.ranking_weights?.cv_recency_score,
  };
  return (
    <div>
      {searchResults.length === 0 ? (
        <div className="empty-search-state">
          <strong>{searchLoading ? loadingLabel : 'Chua co ket qua'}</strong>
          <span>Tim kiem CV tren cac trang tuyen dung.</span>
        </div>
      ) : (
        <div className="cv-results-list">
          {searchResults.map((result, index) => {
            const hasBusinessData = Boolean(result.candidate_name || result.total_score !== undefined);
            return (
              <div
                key={`${result.id}-${result.filename}`}
                className="cv-result-card"
                onClick={() => onViewCv(result)}
                role="button"
                tabIndex={0}
                onKeyDown={event => event.key === 'Enter' && onViewCv(result)}
              >
                <div className="cv-result-rank">{index + 1}</div>
                <div className="cv-result-info">
                  <div className="cv-result-name" title={result.candidate_name || result.filename}>
                    {result.candidate_name || result.filename}
                  </div>
                  {hasBusinessData && (
                    <>
                      <div className="cv-result-title" title={result.current_job_title || result.desired_job_title || result.filename}>
                        {result.current_job_title || result.desired_job_title || result.filename}
                      </div>
                      <div className="cv-result-meta">
                        {result.location && <MetaItem icon={<IconPin />} text={result.location} />}
                        {result.last_updated_date && <MetaItem icon={<IconClock />} text={`Updated: ${result.last_updated_date}`} />}
                      </div>
                      {result.recommendation_reason && (
                        <div className="cv-result-extra-line cv-result-reason">{result.recommendation_reason}</div>
                      )}
                      {result.score_breakdown && (
                        <div className="cv-result-breakdown">
                          <BreakdownChip
                            icon={<IconBriefcase />}
                            label={breakdownLabels.job_title_match_score}
                            value={String(formatBreakdownScore(result.score_breakdown.job_title_match_score, breakdownWeights.job_title_match_score))}
                          />
                          <BreakdownChip
                            icon={<IconWallet />}
                            label={breakdownLabels.skill_match_score}
                            value={String(formatBreakdownScore(result.score_breakdown.skill_match_score, breakdownWeights.skill_match_score))}
                          />
                          <BreakdownChip
                            icon={<IconTimeline />}
                            label={breakdownLabels.experience_match_score}
                            value={String(formatBreakdownScore(result.score_breakdown.experience_match_score, breakdownWeights.experience_match_score))}
                          />
                          <BreakdownChip
                            icon={<IconPin />}
                            label={breakdownLabels.location_match_score}
                            value={String(formatBreakdownScore(result.score_breakdown.location_match_score, breakdownWeights.location_match_score))}
                          />
                          <BreakdownChip
                            icon={<IconClock />}
                            label={breakdownLabels.cv_recency_score}
                            value={String(formatBreakdownScore(result.score_breakdown.cv_recency_score, breakdownWeights.cv_recency_score))}
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
                <div className="cv-result-score">
                  <div className="cv-result-score-label">{hasBusinessData ? 'Best match' : 'Match'}</div>
                  {hasBusinessData && result.total_score !== undefined ? (
                    <BusinessScoreBar score={result.total_score} />
                  ) : (
                    <ScoreBar score={result.search_score} />
                  )}
                </div>
                <button
                  className="cv-result-view-btn"
                  title="Xem CV"
                  aria-label={`Xem ${result.filename}`}
                  onClick={event => { event.stopPropagation(); onViewCv(result); }}
                >
                  <IconEye />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
