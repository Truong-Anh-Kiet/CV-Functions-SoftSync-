import { useState } from 'react';
import HeatmapSection from '../matching/HeatmapSection';
import XaiExplanation from '../matching/XaiExplanation';
import StructuredDataViewer from '../matching/StructuredDataViewer';
import CellDetailModal, { type CellDetailState } from './CellDetailModal';
import type { RankingResultItem } from '../../../types/ranking';

interface RankingDetailModalProps {
  result: RankingResultItem | null;
  onClose: () => void;
}

type Tab = 'heatmap' | 'xai' | 'pdf' | 'json';

const scorePercent = (score10: number) => Math.max(0, Math.min(100, (score10 / 10) * 100));

const CV_VIEW_KEYS = ['skills', 'education', 'year_experience', 'experience', 'responsibilities', 'projects', 'publications', 'achievement', 'certification', 'employment_history'];
const JD_VIEW_KEYS = ['skills', 'education', 'year_experience_requirement', 'experience_requirement', 'responsibilities'];
const VIEW_LABEL_MAP: Record<string, string> = {
  skills: 'Skills',
  education: 'Education',
  year_experience: 'Years of Experience',
  experience: 'Experience',
  responsibilities: 'Responsibilities',
  projects: 'Projects',
  publications: 'Publications',
  achievement: 'Achievement',
  certification: 'Certification',
  employment_history: 'Employment History',
  job_title: 'Job Title',
  company_info: 'Company Info',
  required_skills: 'Required Skills',
  education_requirement: 'Education Requirement',
  year_experience_requirement: 'Years Exp. Requirement',
  experience_requirement: 'Experience Requirement',
  benefits: 'Benefits',
};

const extractStructuredField = (structured: unknown, key: string): string => {
  if (!structured || typeof structured !== 'object') return '(Không có dữ liệu)';
  const val = (structured as Record<string, unknown>)[key];
  if (val === undefined || val === null) return '(Không có trường này)';
  if (typeof val === 'string') return val.trim() || '(Trống)';
  if (Array.isArray(val)) return val.join('\n') || '(Trống)';
  return String(val);
};

export default function RankingDetailModal({ result, onClose }: RankingDetailModalProps) {
  const [tab, setTab] = useState<Tab>('heatmap');
  const [cellDetail, setCellDetail] = useState<CellDetailState | null>(null);

  if (!result) return null;

  const pdfUrl = result.cv_cloudinary_url || result.cv_preview_url || '';
  const hasHeatmap = Boolean(result.alignment_matrix_raw && result.alignment_matrix_masked && result.heatmap_labels);
  const hasXai = Array.isArray(result.view_matches) && result.view_matches.length > 0;
  const hasStructured = Boolean(result.cv_structured);
  const hasJdStructured = Boolean(result.jd_structured);

  const handleCellClick = (rowIndex: number, colIndex: number, score: number) => {
    const cvKey = CV_VIEW_KEYS[rowIndex];
    const jdKey = JD_VIEW_KEYS[colIndex];
    if (!cvKey || !jdKey) return;
    setCellDetail({
      cvKey,
      jdKey,
      cvLabel: VIEW_LABEL_MAP[cvKey] ?? cvKey,
      jdLabel: VIEW_LABEL_MAP[jdKey] ?? jdKey,
      score,
      cvEvidence: extractStructuredField(result.cv_structured, cvKey),
      jdEvidence: extractStructuredField(result.jd_structured, jdKey),
      rowIndex,
      colIndex,
    });
  };

  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content ranking-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header ranking-detail-header">
          <div className="ranking-detail-title">
            <span className="ranking-detail-rank">#{result.rank}</span>
            <div>
              <h3 title={result.cv_file}>{result.cv_file}</h3>
              <div className="ranking-detail-meta">
                <span className={`ranking-match-badge ${result.match ? 'matched' : 'mismatch'}`}>{result.label}</span>
                <span>Score <strong>{result.score.toFixed(2)} / 10</strong></span>
                <span>Confidence {(result.confidence * 100).toFixed(1)}%</span>
                <div className="ranking-detail-meter">
                  <div style={{ width: `${scorePercent(result.score)}%` }} />
                </div>
              </div>
            </div>
          </div>
          <button className="close-modal" onClick={onClose} aria-label="Đóng">&times;</button>
        </div>

        <div className="ranking-detail-tabs" role="tablist">
          <button
            type="button"
            className={tab === 'heatmap' ? 'active' : ''}
            onClick={() => setTab('heatmap')}
            disabled={!hasHeatmap}
          >Heatmap</button>
          <button
            type="button"
            className={tab === 'xai' ? 'active' : ''}
            onClick={() => setTab('xai')}
            disabled={!hasXai}
          >XAI giải thích</button>
          <button
            type="button"
            className={tab === 'pdf' ? 'active' : ''}
            onClick={() => setTab('pdf')}
            disabled={!pdfUrl}
          >CV PDF</button>
          <button
            type="button"
            className={tab === 'json' ? 'active' : ''}
            onClick={() => setTab('json')}
            disabled={!hasStructured && !hasJdStructured}
          >Structured JSON</button>
        </div>

        <div className="modal-body ranking-detail-body">
          {tab === 'heatmap' && hasHeatmap && (
            <div className="ranking-detail-section">
              <HeatmapSection
                result={result}
                onCellClick={(i, j, score) => handleCellClick(i, j, score)}
              />
            </div>
          )}
          {tab === 'xai' && hasXai && (
            <div className="ranking-detail-section">
              <XaiExplanation matches={result.view_matches} />
            </div>
          )}
          {tab === 'pdf' && pdfUrl && (
            <iframe src={pdfUrl} title={`PDF ${result.cv_file}`} width="100%" height="100%" />
          )}
          {tab === 'json' && (
            <div className="ranking-detail-section ranking-detail-json">
              {hasStructured && (
                <div>
                  <h4>CV structured</h4>
                  <StructuredDataViewer data={result.cv_structured} />
                </div>
              )}
              {hasJdStructured && (
                <div>
                  <h4>JD structured</h4>
                  <StructuredDataViewer data={result.jd_structured} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <CellDetailModal detail={cellDetail} onClose={() => setCellDetail(null)} />
    </div>
  );
}
