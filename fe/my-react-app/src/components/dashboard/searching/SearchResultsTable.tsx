import type { ReactNode } from 'react';
import type { SearchCvResult, SearchApiResponse } from '../../../types/search';
import type { MatchingResult } from '../../../types/matching';
import { IconBriefcase, IconClock, IconEye, IconPin, IconTimeline, IconWallet } from '../icons';

interface SearchResultsTableProps {
  searchResults: SearchCvResult[];
  searchMeta: SearchApiResponse['data'] | null;
  searchLoading: boolean;
  savedCvsLength: number;
  onViewDbCv: (result: SearchCvResult) => void;
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

function RerankBadge({ score, label, match }: { score: number; label: string; match: boolean }) {
  return (
    <div className="cv-rerank-badge-row">
      <span className="cv-rerank-score">{score.toFixed(1)}<small>/10</small></span>
      <span className={`cv-rerank-tag ${match ? 'pass' : 'fail'}`}>{label}</span>
    </div>
  );
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

export default function SearchResultsTable({
  searchResults,
  searchMeta,
  searchLoading,
  savedCvsLength,
  onViewDbCv,
}: SearchResultsTableProps) {
  const normalizeCvName = (value: string | number | null | undefined) => String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/(\.(pdf|txt))+$/i, '')
    .replace(/[^a-z0-9]+/gi, ' ')
    .trim()
    .toLowerCase();

  const getSearchRerankResult = (item: SearchCvResult): MatchingResult | undefined => (
    searchMeta?.rerank?.results?.find(result => {
      const sameDocument = result.document_id !== undefined && result.document_id !== null && String(result.document_id) === String(item.id);
      const sameName = [result.cv_file, result.source_cv_file]
        .filter(Boolean)
        .some(value => normalizeCvName(value) === normalizeCvName(item.filename));
      return sameDocument || sameName;
    })
  );

  const skippedCvs = searchMeta?.skipped_cvs ?? [];
  const rerankResultCount = searchMeta?.rerank?.results?.length ?? 0;
  const shouldShowRerankWarning = !searchLoading && skippedCvs.length > 0 && rerankResultCount === 0;
  const hasRerank = Boolean(searchMeta?.rerank?.results?.length);
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
      {shouldShowRerankWarning && (
        <div className="index-status warning" style={{ marginBottom: 12 }}>
          <div className="index-status-header">
            <strong>AI rerank could not run for the selected shortlist.</strong>
          </div>
          {skippedCvs.slice(0, 3).map(item => (
            <p key={`${item.id}-${item.filename}`}>{item.filename}: {item.reason}</p>
          ))}
        </div>
      )}

      {searchResults.length === 0 ? (
        <div className="empty-search-state">
          <strong>{searchLoading ? 'Dang xu ly...' : 'Chua co ket qua'}</strong>
          <span>{searchMeta ? 'Khong co CV vuot qua nguong diem.' : `${savedCvsLength} CV trong kho.`}</span>
        </div>
      ) : (
        <div className="cv-results-list db-cv-results-list">
          {searchResults.map((result, index) => {
            const rerankResult = getSearchRerankResult(result);
            const matchedSkills = result.matched_required_skills ?? [];
            const missingSkills = result.missing_required_skills ?? [];
            const hasBusinessData = Boolean(result.candidate_name || result.total_score !== undefined);
            return (
              <div
                key={`${result.id}-${result.filename}`}
                className="cv-result-card db-cv-result-card"
                onClick={() => onViewDbCv(result)}
                role="button"
                tabIndex={0}
                onKeyDown={event => event.key === 'Enter' && onViewDbCv(result)}
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
                        {result.experience_years !== undefined && result.experience_years !== null && (
                          <MetaItem icon={<IconTimeline />} text={`${result.experience_years} years`} />
                        )}
                        {result.location && <MetaItem icon={<IconPin />} text={result.location} />}
                        {result.last_updated_date && <MetaItem icon={<IconClock />} text={`Updated: ${result.last_updated_date}`} />}
                      </div>
                      {(matchedSkills.length > 0 || missingSkills.length > 0) && (
                        <div className="cv-result-extra">
                          {matchedSkills.length > 0 && (
                            <div className="cv-result-extra-line">
                              <strong>Matched:</strong> {matchedSkills.join(', ')}
                            </div>
                          )}
                          {missingSkills.length > 0 && (
                            <div className="cv-result-extra-line">
                              <strong>Missing:</strong> {missingSkills.join(', ')}
                            </div>
                          )}
                        </div>
                      )}
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

                {hasRerank && (
                  <div className="cv-result-rerank">
                    {rerankResult ? (
                      <RerankBadge
                        score={rerankResult.score}
                        label={rerankResult.label}
                        match={rerankResult.match}
                      />
                    ) : (
                      <span className="cv-result-no-rerank">-</span>
                    )}
                  </div>
                )}

                <button
                  className="cv-result-view-btn"
                  title="Xem chi tiet"
                  aria-label={`Xem chi tiet ${result.filename}`}
                  onClick={event => { event.stopPropagation(); onViewDbCv(result); }}
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
