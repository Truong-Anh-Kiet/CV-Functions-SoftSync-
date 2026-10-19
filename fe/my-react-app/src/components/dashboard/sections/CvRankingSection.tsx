import { useMemo, useState } from 'react';
import type { ModelOption } from '../../../types/model';
import type { RankingResultItem } from '../../../types/ranking';
import { useCvRanking } from '../../../hooks/useCvRanking';
import JdInputPanel from '../ranking/JdInputPanel';
import CvSourcePanel from '../ranking/CvSourcePanel';
import RankingSummaryPanel from '../ranking/RankingSummaryPanel';
import RankingResultsTable from '../ranking/RankingResultsTable';
import RankingProgressBar from '../ranking/RankingProgressBar';
import RankingDetailModal from '../modals/RankingDetailModal';

interface CvRankingSectionProps {
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  showNotify: (msg: string) => void;
}

const buildJdSummary = (mode: 'text' | 'file', text: string, file: File | null) => {
  if (mode === 'text') {
    const trimmed = text.trim();
    if (!trimmed) return '';
    return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed;
  }
  return file?.name ?? '';
};

const escapeCsv = (value: string) => `"${value.replace(/"/g, '""')}"`;

const buildCsv = (results: RankingResultItem[]) => {
  const header = ['Rank', 'CV', 'Source', 'Score', 'Confidence', 'Match', 'CV coverage', 'JD coverage'];
  const rows = results.map((r) => [
    String(r.rank),
    escapeCsv(r.cv_file),
    escapeCsv(r.cv_source ?? 'uploaded'),
    r.score.toFixed(4),
    r.confidence.toFixed(4),
    r.match ? 'matched' : 'mismatch',
    escapeCsv(r.cv_view_coverage ?? ''),
    escapeCsv(r.jd_view_coverage ?? ''),
  ].join(','));
  return [header.join(','), ...rows].join('\n');
};

export default function CvRankingSection({
  modelOptions,
  selectedModel,
  setSelectedModel,
  showNotify,
}: CvRankingSectionProps) {
  const ranking = useCvRanking();
  const [detailResult, setDetailResult] = useState<RankingResultItem | null>(null);

  const jdSummary = useMemo(
    () => buildJdSummary(ranking.jdMode, ranking.jdText, ranking.jdFile),
    [ranking.jdMode, ranking.jdText, ranking.jdFile],
  );

  const handleRun = () => {
    ranking.handleRunRanking({ modelId: selectedModel, showNotify });
  };

  const handleExportCsv = () => {
    if (!ranking.results.length) return;
    const csv = buildCsv(ranking.results);
    const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `ranking_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="ranking-workspace">
      <RankingSummaryPanel
        totalCvCount={ranking.totalCvCount}
        modelOptions={modelOptions}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        jdSummary={jdSummary}
        loading={ranking.loading}
        meta={ranking.meta}
        onRun={handleRun}
        onClearResults={ranking.clearResults}
        hasResults={ranking.results.length > 0}
      />

      <div className="ranking-inputs-grid">
        <JdInputPanel
          jdMode={ranking.jdMode}
          setJdMode={ranking.setJdMode}
          jdText={ranking.jdText}
          setJdText={ranking.setJdText}
          jdFile={ranking.jdFile}
          onJdFileChange={ranking.handleJdFileChange}
          disabled={ranking.loading}
        />

        <CvSourcePanel
          cvSource={ranking.cvSource}
          setCvSource={ranking.setCvSource}
          uploadedCvs={ranking.uploadedCvs}
          onCvFilesChange={ranking.handleCvFilesChange}
          removeUploadedCv={ranking.removeUploadedCv}
          savedCvs={ranking.savedCvs}
          savedCvsLoading={ranking.savedCvsLoading}
          selectedSavedIds={ranking.selectedSavedIds}
          toggleSavedCv={ranking.toggleSavedCv}
          onRefreshSaved={ranking.refreshSavedCvs}
          onClearAll={ranking.clearSelections}
          disabled={ranking.loading}
        />
      </div>

      <RankingProgressBar active={ranking.loading} cvCount={ranking.totalCvCount} />

      <RankingResultsTable
        results={ranking.results}
        loading={ranking.loading}
        onViewDetail={setDetailResult}
        onExportCsv={handleExportCsv}
      />

      <RankingDetailModal result={detailResult} onClose={() => setDetailResult(null)} />
    </div>
  );
}
