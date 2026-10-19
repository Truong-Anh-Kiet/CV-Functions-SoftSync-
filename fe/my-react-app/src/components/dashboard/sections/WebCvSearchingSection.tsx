import { useEffect, useState } from 'react';
import type { SearchApiResponse, SearchCvResult } from '../../../types/search';
import type { ModelOption } from '../../../types/model';
import type { MatchingResult } from '../../../types/matching';
import {
  analyzeJd,
  academicProfileFileUrl,
  careerVietProfileFileUrl,
  fetchUsdVndRate,
  getAcademicProfile,
  getCareerVietProfile,
  getVietnamWorksProfile,
  searchAcademicProfiles,
  searchAcademicProfilesByJd,
  searchAcademicProfilesWithMatching,
  searchCareerVietProfiles,
  searchCareerVietProfilesByJd,
  searchCareerVietProfilesWithMatching,
  searchVietnamWorksProfiles,
  searchVietnamWorksProfilesByJd,
  searchVietnamWorksProfilesWithMatching,
  vietnamWorksProfileFileUrl,
  type AcademicProfile,
  type CareerVietProfile,
  type VietnamWorksProfile,
} from '../../../services/api';
import { getCvHeatmap } from '../../../services/api/matching';
import { buildWebSearchQuery, rankWebProfilesFromJd, resolveWebBreakdownLabels, resolveWebRankingWeights } from '../../../utils/webCvRanking';
import SearchResultsTable from '../searching/SearchResultsTable';
import HeatmapSection from '../matching/HeatmapSection';
import XaiExplanation from '../matching/XaiExplanation';
import CellDetailModal from '../modals/CellDetailModal';

type WebSource = 'careerviet' | 'vietnamworks' | 'scholar';
type WebProfile = AcademicProfile | CareerVietProfile | VietnamWorksProfile;

interface WebCvSearchingSectionProps {
  searchMode: 'text' | 'file';
  setSearchMode: (mode: 'text' | 'file') => void;
  searchJdText: string;
  setSearchJdText: (text: string) => void;
  searchJdFile: File | null;
  searchTopK: number;
  setSearchTopK: (value: number) => void;
  searchMinScore: number;
  setSearchMinScore: (value: number) => void;
  searchRerank: boolean;
  setSearchRerank: (value: boolean) => void;
  searchRerankTopN: number;
  setSearchRerankTopN: (value: number) => void;
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  onSearchJdFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const CV_VIEW_KEYS = ['skills', 'education', 'year_experience', 'experience', 'responsibilities', 'projects', 'publications', 'achievement', 'certification', 'employment_history'];
const JD_VIEW_KEYS = ['skills', 'education', 'year_experience_requirement', 'experience_requirement', 'responsibilities'];
const VIEW_LABEL_MAP: Record<string, string> = {
  skills: 'Kỹ năng',
  education: 'Học vấn',
  year_experience: 'Số năm kinh nghiệm',
  experience: 'Kinh nghiệm làm việc',
  responsibilities: 'Trách nhiệm',
  projects: 'Dự án',
  publications: 'Công trình',
  achievement: 'Thành tích',
  certification: 'Chứng chỉ',
  employment_history: 'Lịch sử công việc',
  year_experience_requirement: 'Yêu cầu kinh nghiệm',
  experience_requirement: 'Yêu cầu kinh nghiệm (loại)',
};

const extractStructuredField = (structured: unknown, key: string): string => {
  if (!structured || typeof structured !== 'object') return '(Không có dữ liệu)';
  const val = (structured as Record<string, unknown>)[key];
  if (val === undefined || val === null) return '(Không có trường này)';
  if (typeof val === 'string') return val.trim() || '(Trống)';
  if (Array.isArray(val)) return val.join('\n') || '(Trống)';
  return String(val);
};

const WEB_SOURCE_OPTIONS: { id: WebSource; label: string; description: string }[] = [
  { id: 'careerviet', label: 'CareerViet', description: 'IT profiles from HR Central' },
  { id: 'vietnamworks', label: 'VietnamWorks', description: 'Employer candidate search' },
  { id: 'scholar', label: 'Google Scholar', description: 'Academic profiles via OpenAlex' },
];

const WEB_SOURCE_LABELS: Record<WebSource, string> = {
  careerviet: 'CareerViet',
  vietnamworks: 'VietnamWorks',
  scholar: 'Google Scholar',
};

const isVietnamWorksProfile = (profile: WebProfile) => (
  profile.source === 'VietnamWorks' || String(profile.id).startsWith('vietnamworks-')
);

const isAcademicProfile = (profile: WebProfile) => (
  profile.source === 'Google Scholar' || String(profile.id).startsWith('scholar-')
);

const sourceApiFor = (source: WebSource) => {
  if (source === 'vietnamworks') {
    return {
      search: searchVietnamWorksProfiles,
      searchByJd: searchVietnamWorksProfilesByJd,
      searchWithMatching: searchVietnamWorksProfilesWithMatching,
    };
  }
  if (source === 'scholar') {
    return {
      search: searchAcademicProfiles,
      searchByJd: searchAcademicProfilesByJd,
      searchWithMatching: searchAcademicProfilesWithMatching,
    };
  }
  return {
    search: searchCareerVietProfiles,
    searchByJd: searchCareerVietProfilesByJd,
    searchWithMatching: searchCareerVietProfilesWithMatching,
  };
};

export default function WebCvSearchingSection({
  searchMode,
  setSearchMode,
  searchJdText,
  setSearchJdText,
  searchJdFile,
  searchTopK,
  setSearchTopK,
  searchMinScore,
  setSearchMinScore,
  searchRerank,
  setSearchRerank,
  searchRerankTopN,
  setSearchRerankTopN: _setSearchRerankTopN,
  modelOptions,
  selectedModel,
  setSelectedModel,
  onSearchJdFileChange,
}: WebCvSearchingSectionProps) {
  const [selectedSource, setSelectedSource] = useState<WebSource>('careerviet');
  const [webLoading, setWebLoading] = useState(false);
  const [webResults, setWebResults] = useState<SearchCvResult[]>([]);
  const [webMeta, setWebMeta] = useState<SearchApiResponse['data'] | null>(null);
  const [_currentCvTotal, setCurrentCvTotal] = useState(0);
  const [sourceTotal, setSourceTotal] = useState<number | null>(null);
  const [sourceTotalLoading, setSourceTotalLoading] = useState(false);
  const [webError, setWebError] = useState('');
  const [profilesByResultId, setProfilesByResultId] = useState<Record<string, WebProfile>>({});
  const [viewingProfile, setViewingProfile] = useState<WebProfile | null>(null);
  const [profileDetailLoading, setProfileDetailLoading] = useState(false);
  const [profileDetailError, setProfileDetailError] = useState('');
  const [profileHeatmapResult, setProfileHeatmapResult] = useState<MatchingResult | null>(null);
  const [profileHeatmapLoading, setProfileHeatmapLoading] = useState(false);
  const [profileHeatmapError, setProfileHeatmapError] = useState('');
  const [profileCellDetail, setProfileCellDetail] = useState<{
    cvKey: string;
    jdKey: string;
    cvLabel: string;
    jdLabel: string;
    score: number;
    cvEvidence: string;
    jdEvidence: string;
    rowIndex: number;
    colIndex: number;
  } | null>(null);

  const currentQuery = searchMode === 'text' ? searchJdText : '';
  const selectedSourceOption = WEB_SOURCE_OPTIONS.find(source => source.id === selectedSource) ?? WEB_SOURCE_OPTIONS[0];
  const selectedModelOption = modelOptions.find(model => model.id === selectedModel);

  useEffect(() => {
    let ignore = false;

    const loadSourceTotal = async () => {
      setSourceTotalLoading(true);
      try {
        const { ok, result } = await sourceApiFor(selectedSource).search({ page: 1, pageSize: 1 });
        if (!ignore) {
          setSourceTotal(ok && result.data ? result.data.total : null);
        }
      } catch {
        if (!ignore) setSourceTotal(null);
      } finally {
        if (!ignore) setSourceTotalLoading(false);
      }
    };

    loadSourceTotal();
    return () => {
      ignore = true;
    };
  }, [selectedSource]);

  const handleRunWebSearch = async () => {
    const query = currentQuery.trim();
    setWebLoading(true);
    setWebError('');

    try {
      if (searchMode === 'file' && !searchJdFile) {
        throw new Error('Please select a JD PDF file.');
      }
      if (searchMode === 'text' && !query) {
        throw new Error('Please enter JD text.');
      }

      const safeTopK = Math.max(1, Math.min(100, searchTopK));
      const safeRerankTopN = Math.max(1, Math.min(safeTopK, searchRerankTopN));
      const fetchPoolSize = 100;
      const sourceApi = sourceApiFor(selectedSource);
      const jdAnalysisResponse = await analyzeJd({
        mode: searchMode,
        jdText: searchMode === 'text' ? query : undefined,
        jdFile: searchMode === 'file' ? searchJdFile : null,
      });
      if (!jdAnalysisResponse.ok || !jdAnalysisResponse.result.data) {
        throw new Error(jdAnalysisResponse.result.detail || 'Khong the phan tich JD.');
      }
      const jdAnalysis = jdAnalysisResponse.result.data;
      const usdVndRate = await fetchUsdVndRate();
      const webQuery = buildWebSearchQuery(jdAnalysis) || query;
      let { ok, result } = searchRerank
        ? await sourceApi.searchWithMatching({
          mode: searchMode,
          query: webQuery,
          jdText: searchMode === 'text' ? query : undefined,
          jdFile: searchMode === 'file' ? searchJdFile : null,
          page: 1,
          pageSize: fetchPoolSize,
          minScore: searchMinScore,
          rerank: searchRerank,
          rerankTopN: safeRerankTopN,
          modelId: selectedModel,
        })
        : await sourceApi.search({
          query: webQuery,
          page: 1,
          pageSize: fetchPoolSize,
        });

      if (ok && result.data && (result.data.items?.length ?? 0) === 0) {
        const fallbackResponse = await sourceApi.searchByJd({
          jdText: searchMode === 'text' ? query : undefined,
          jdFile: searchMode === 'file' ? searchJdFile : null,
          page: 1,
          pageSize: fetchPoolSize,
        });
        if (fallbackResponse.ok && fallbackResponse.result.data) {
          ({ ok, result } = fallbackResponse);
        }
      }

      if (!ok || !result.data) {
        throw new Error(result.detail || `${WEB_SOURCE_LABELS[selectedSource]} search failed.`);
      }

      const ranking = rankWebProfilesFromJd(
        result.data.items,
        jdAnalysis,
        selectedModel,
        selectedModelOption?.sbert_id,
        safeTopK,
        usdVndRate,
      );
      const mappedResults = ranking.toppedUp
        .filter(item => (item.total_score ?? 0) >= searchMinScore * 100)
        .slice(0, safeTopK);
      const nextProfilesByResultId = result.data.items.reduce<Record<string, WebProfile>>((acc, profile) => {
        acc[profile.id] = profile;
        return acc;
      }, {});

      const meta: SearchApiResponse['data'] = {
        success: true,
        jd_analysis: jdAnalysis,
        total_candidates: mappedResults.length,
        total_cvs: result.data.total,
        search_mode: searchMode,
        embedding_model_id: selectedModel || 'web-search',
        sbert_id: selectedModelOption?.sbert_id,
        indexed_cvs: result.data.total,
        indexed_missing: 0,
        skipped_cvs: result.data.skipped_cvs ?? [],
        returned: mappedResults.length,
        top_k: searchTopK,
        min_score: searchMinScore,
        auto_index_missing: false,
        ranking_weights: {
          ...resolveWebRankingWeights(jdAnalysis, usdVndRate).normalized,
        },
        score_breakdown_labels: resolveWebBreakdownLabels(jdAnalysis, usdVndRate),
        usd_vnd_rate: usdVndRate,
        filtered_out: ranking.filtered.length,
        results: mappedResults,
        rerank: result.data.rerank ?? null,
      };

      setCurrentCvTotal(result.data.total);
      setSourceTotal(result.data.total);
      setWebResults(mappedResults);
      setWebMeta(meta);
      setProfilesByResultId(nextProfilesByResultId);
      setWebError('');
    } catch (error) {
      const sourceLabel = WEB_SOURCE_LABELS[selectedSource];
      const message = error instanceof Error ? error.message : `Cannot connect to ${sourceLabel} search API.`;
      setWebResults([]);
      setCurrentCvTotal(0);
      setProfilesByResultId({});
      setWebMeta({
        success: false,
        total_cvs: 0,
        search_mode: searchMode,
        embedding_model_id: selectedModel || selectedSource,
        sbert_id: selectedModelOption?.sbert_id,
        indexed_cvs: 0,
        indexed_missing: 0,
        skipped_cvs: [{ id: selectedSource, filename: WEB_SOURCE_LABELS[selectedSource], reason: message }],
        returned: 0,
        top_k: searchTopK,
        min_score: searchMinScore,
        auto_index_missing: false,
        results: [],
        rerank: null,
      });
      setWebError(message);
    } finally {
      setWebLoading(false);
    }
  };

  const handleReindexWeb = () => {
    setWebResults([]);
    setWebMeta(null);
    setCurrentCvTotal(0);
    setWebError('');
    setProfilesByResultId({});
  };

  const handleViewWebCv = async (result: SearchCvResult) => {
    const profile = profilesByResultId[String(result.id)];
    if (!profile) return;

    setViewingProfile(profile);
    setProfileDetailError('');
    setProfileDetailLoading(true);
    setProfileHeatmapResult(null);
    setProfileHeatmapError('');
    try {
      const getProfile = isAcademicProfile(profile)
        ? getAcademicProfile
        : isVietnamWorksProfile(profile)
          ? getVietnamWorksProfile
          : getCareerVietProfile;
      const { ok, result: detailResult } = await getProfile(
        profile.id,
        profile.profile_url,
        isAcademicProfile(profile) || isVietnamWorksProfile(profile) ? undefined : profile.salary,
      );
      if (ok && detailResult.data) {
        setViewingProfile(detailResult.data);
      } else if (detailResult.detail) {
        setProfileDetailError(detailResult.detail);
      }
    } catch {
      setProfileDetailError(`Cannot load full ${profile.source || 'web'} profile detail.`);
    } finally {
      setProfileDetailLoading(false);
    }

    // Fetch heatmap data for this profile if we have JD text or JD file
    const jdText = currentQuery.trim();
    const rawText = profile.raw_text || profile.summary || '';
    if (!jdText && !searchJdFile) return;
    if (!rawText) return;

    setProfileHeatmapLoading(true);
    setProfileHeatmapError('');
    try {
      const apiResult = await getCvHeatmap({
        jdText: jdText || undefined,
        jdFile: jdText ? undefined : (searchJdFile || undefined),
        cvText: rawText,
        cvFilename: profile.title || profile.candidate_name || 'profile.txt',
        modelId: selectedModel,
      });
      if (apiResult.ok && apiResult.result.data) {
        const data = apiResult.result.data as MatchingResult;
        setProfileHeatmapResult(data);
      } else {
        setProfileHeatmapError(apiResult.result.detail || 'Failed to load heatmap');
      }
    } catch (e) {
      setProfileHeatmapError('Cannot connect to matching service');
    } finally {
      setProfileHeatmapLoading(false);
    }
  };

  const closeProfileModal = () => {
    setViewingProfile(null);
    setProfileDetailError('');
    setProfileDetailLoading(false);
    setProfileHeatmapResult(null);
    setProfileHeatmapError('');
    setProfileCellDetail(null);
  };

  return (
    <div className="web-searching-workspace">
      <div className="web-search-bar">
        <div className="web-source-inline">
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value as WebSource)}
            disabled={webLoading}
            className="web-source-select-compact"
            aria-label="Select web source"
          >
            {WEB_SOURCE_OPTIONS.map(source => (
              <option key={source.id} value={source.id}>
                {source.label}
              </option>
            ))}
          </select>
          <span className="web-source-badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="2" y1="12" x2="22" y2="12"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
            {selectedSourceOption.label}
          </span>
        </div>

        <div className="search-input-row">
          <div className="search-input-main">
            <div className="search-mode-tabs-container">
              <div className="web-search-mode-tabs" role="tablist">
                <button type="button" className={searchMode === 'text' ? 'active' : ''} onClick={() => setSearchMode('text')}>Theo từ khóa</button>
                <button type="button" className={searchMode === 'file' ? 'active' : ''} onClick={() => setSearchMode('file')}>Theo JD File</button>
              </div>
            </div>

            {searchMode === 'text' ? (
              <textarea
                className="search-textarea"
                value={searchJdText}
                onChange={(event) => setSearchJdText(event.target.value)}
                placeholder="Nhập từ khóa tìm kiếm: Java Spring Boot, Python Django..."
                disabled={webLoading}
              />
            ) : (
              <label className="search-file-drop" htmlFor="web-search-jd-file">
                <input id="web-search-jd-file" type="file" accept=".pdf" hidden onChange={onSearchJdFileChange} />
                <div className="upload-icon-circle">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <strong>{searchJdFile ? searchJdFile.name : 'Chọn JD PDF'}</strong>
                {searchJdFile && <span>{(searchJdFile.size / 1024 / 1024).toFixed(2)} MB</span>}
              </label>
            )}

            <div className="search-controls-inline">
              <label className="search-field">
                <span>Model</span>
                <select
                  className="search-select"
                  value={selectedModel}
                  onChange={(event) => setSelectedModel(event.target.value)}
                  disabled={webLoading || modelOptions.length === 0}
                >
                  {modelOptions.length === 0 ? (
                    <option value="">Default</option>
                  ) : (
                    modelOptions.map(option => (
                      <option key={option.id} value={option.id}>{option.display_name}</option>
                    ))
                  )}
                </select>
              </label>
              <label className="search-field">
                <span>Top K</span>
                <input
                  type="number"
                  className="search-input"
                  min={1}
                  max={500}
                  value={searchTopK}
                  onChange={(e) => setSearchTopK(Number(e.target.value))}
                />
              </label>
              <label className="search-field">
                <span>Min score</span>
                <input
                  type="number"
                  className="search-input"
                  min={0}
                  max={1}
                  step={0.05}
                  value={searchMinScore}
                  onChange={(e) => setSearchMinScore(Number(e.target.value))}
                />
              </label>
              <label className="search-toggle">
                <input type="checkbox" checked={searchRerank} onChange={(e) => setSearchRerank(e.target.checked)} />
                Rerank
              </label>
            </div>
          </div>

          <div className="search-actions">
            <button className="save-btn search-primary-btn" onClick={handleRunWebSearch} disabled={webLoading}>
              {webLoading ? (searchRerank ? 'Đang matching...' : 'Đang tìm...') : 'Tìm kiếm'}
            </button>
            <button className="search-secondary-btn" onClick={handleReindexWeb} disabled={webLoading}>
              Xóa
            </button>
          </div>
        </div>
      </div>

      <SearchResultsTable
        searchResults={webResults}
        searchMeta={webMeta}
        searchLoading={webLoading}
        savedCvsLength={sourceTotalLoading ? 0 : sourceTotal ?? 0}
        onViewDbCv={handleViewWebCv}
      />

      {webError && <div className="web-error">{webError}</div>}

      <WebProfileModal
        profile={viewingProfile}
        loading={profileDetailLoading}
        error={profileDetailError}
        jdText={currentQuery}
        heatmapResult={profileHeatmapResult}
        heatmapLoading={profileHeatmapLoading}
        heatmapError={profileHeatmapError}
        onClose={closeProfileModal}
        onCellClick={setProfileCellDetail}
      />
      <CellDetailModal
        detail={profileCellDetail}
        onClose={() => setProfileCellDetail(null)}
      />
    </div>
  );
}

interface WebProfileModalProps {
  profile: WebProfile | null;
  loading: boolean;
  error: string;
  jdText: string;
  heatmapResult: MatchingResult | null;
  heatmapLoading: boolean;
  heatmapError: string;
  onClose: () => void;
  onCellClick: (state: {
    cvKey: string;
    jdKey: string;
    cvLabel: string;
    jdLabel: string;
    score: number;
    cvEvidence: string;
    jdEvidence: string;
    rowIndex: number;
    colIndex: number;
  }) => void;
}

type ProfileTab = 'heatmap' | 'xai' | 'pdf' | 'overview';

function WebProfileModal({
  profile,
  loading,
  error,
  jdText,
  heatmapResult,
  heatmapLoading,
  heatmapError,
  onClose,
  onCellClick,
}: WebProfileModalProps) {
  if (!profile) return null;

  const [tab, setTab] = useState<ProfileTab>('overview');

  const facts = [
    ['Candidate', profile.candidate_name],
    ['Experience', profile.experience],
    ['Education', profile.education],
    ['Level', profile.level],
    ['Salary', profile.salary],
    ['Location', profile.location],
    ['Last access', profile.last_access],
  ].filter(([, value]) => Boolean(value));
  const rawText = profile.raw_text || profile.summary || '';
  const sourceLabel = profile.source || 'CareerViet';
  const fileUrl = profile.attachment_url
    ? isAcademicProfile(profile)
      ? academicProfileFileUrl(profile.id, profile.profile_url)
      : isVietnamWorksProfile(profile)
      ? vietnamWorksProfileFileUrl(profile.id, profile.profile_url)
      : careerVietProfileFileUrl(profile.id, profile.profile_url, profile.salary)
    : '';
  const hasHeatmap = Boolean(
    heatmapResult?.alignment_matrix_raw
    && heatmapResult?.alignment_matrix_masked
    && heatmapResult?.heatmap_labels,
  );
  const hasXai = Array.isArray(heatmapResult?.view_matches) && heatmapResult.view_matches.length > 0;
  const handleCellClick = (rowIndex: number, colIndex: number, score: number, _result?: MatchingResult, cvKey?: string, jdKey?: string) => {
    if (!heatmapResult) return;
    const cv = cvKey || CV_VIEW_KEYS[rowIndex];
    const jd = jdKey || JD_VIEW_KEYS[colIndex];
    if (!cv || !jd) return;
    onCellClick({
      cvKey: cv,
      jdKey: jd,
      cvLabel: VIEW_LABEL_MAP[cv] ?? cv,
      jdLabel: VIEW_LABEL_MAP[jd] ?? jd,
      score,
      cvEvidence: extractStructuredField(heatmapResult.cv_structured, cv),
      jdEvidence: extractStructuredField(heatmapResult.jd_structured, jd),
      rowIndex,
      colIndex,
    });
  };

  const renderLoadingOverlay = (msg: string) => (
    <div className="web-profile-analysis-loading">
      <div className="detail-spinner" />
      <span>{msg}</span>
    </div>
  );

  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className={`file-modal-content web-profile-modal ${fileUrl ? 'has-file' : ''}`} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header web-profile-modal-header">
          <div>
            <span className="modal-subtitle">{fileUrl ? `${sourceLabel} CV` : `${sourceLabel} profile`}</span>
            <h3>{profile.title}</h3>
          </div>
          {heatmapResult && (
            <div className="web-profile-score-badge">
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: heatmapResult.match ? '#16a34a' : '#dc2626', flexShrink: 0 }} />
              <span style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800, fontSize: 16 }}>
                {heatmapResult.score.toFixed(1)}<small style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>/10</small>
              </span>
              <span style={{
                padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 800,
                background: heatmapResult.match ? '#f0fdf4' : '#fef2f2',
                color: heatmapResult.match ? '#15803d' : '#b91c1c',
                border: `1px solid ${heatmapResult.match ? '#bbf7d0' : '#fecaca'}`,
              }}>
                {heatmapResult.label}
              </span>
            </div>
          )}
          <button className="close-modal" onClick={onClose}>&times;</button>
        </div>

        {/* Analysis tabs — only shown when profile loaded and has raw text */}
        {profile && rawText && (
          <div className="ranking-detail-tabs" role="tablist">
            <button
              type="button"
              className={tab === 'heatmap' ? 'active' : ''}
              onClick={() => setTab('heatmap')}
            >
              Heatmap
              {!hasHeatmap && !heatmapLoading && heatmapError && <span className="tab-badge">off</span>}
              {heatmapLoading && <span className="tab-badge loading">...</span>}
            </button>
            <button
              type="button"
              className={tab === 'xai' ? 'active' : ''}
              onClick={() => setTab('xai')}
            >
              XAI giải thích
              {!hasXai && !heatmapLoading && heatmapError && <span className="tab-badge">off</span>}
            </button>
            <button
              type="button"
              className={tab === 'pdf' ? 'active' : ''}
              onClick={() => setTab('pdf')}
            >
              CV PDF
              {!fileUrl && <span className="tab-badge">off</span>}
            </button>
            <button
              type="button"
              className={tab === 'overview' ? 'active' : ''}
              onClick={() => setTab('overview')}
            >
              Tổng quan
            </button>
          </div>
        )}

        <div className="web-profile-modal-body">
          {tab === 'heatmap' && (
            <section className="web-profile-analysis">
              {heatmapLoading && renderLoadingOverlay('Đang phân tích CV vs JD để tạo heatmap...')}
              {heatmapError && !heatmapLoading && (
                <div className="web-profile-analysis-error">
                  <span>Không thể tạo heatmap: {heatmapError}</span>
                  {!jdText && (                    <p style={{ marginTop: 8, color: '#94a3b8', fontSize: 13 }}>
                      Nhập JD text hoặc chọn JD file để kích hoạt heatmap.
                    </p>
                  )}
                </div>
              )}
              {!heatmapLoading && !heatmapError && hasHeatmap && heatmapResult && (
                <HeatmapSection
                  result={heatmapResult}
                  onCellClick={handleCellClick}
                />
              )}
              {!heatmapLoading && !heatmapError && !hasHeatmap && !rawText && (
                <div className="web-profile-analysis-empty">
                  <span>Không có dữ liệu profile để phân tích.</span>
                </div>
              )}
              {!heatmapLoading && !heatmapError && !hasHeatmap && rawText && (
                <div className="web-profile-analysis-empty">
                  <span>Đang chờ AI phân tích heatmap...</span>
                </div>
              )}
            </section>
          )}

          {tab === 'xai' && (
            <section className="web-profile-analysis">
              {heatmapLoading && renderLoadingOverlay('Đang phân tích XAI...')}
              {heatmapError && !heatmapLoading && (
                <div className="web-profile-analysis-error">
                  <span>Không thể tạo XAI: {heatmapError}</span>
                </div>
              )}
              {!heatmapLoading && !heatmapError && hasXai && heatmapResult && (
                <XaiExplanation matches={heatmapResult.view_matches!} />
              )}
              {!heatmapLoading && !heatmapError && !hasXai && (
                <div className="web-profile-analysis-empty">
                  <span>Chưa có dữ liệu XAI.</span>
                </div>
              )}
            </section>
          )}

          {tab === 'pdf' && (
            <section className="web-profile-file-viewer">
              {loading ? (
                <div className="web-profile-file-loading">Loading CV file...</div>
              ) : fileUrl ? (
                <iframe src={fileUrl} title={`${profile.title} CV`} />
              ) : (
                <div className="web-profile-analysis-empty">
                  <span>Không có file CV để hiển thị.</span>
                </div>
              )}
            </section>
          )}

          {tab === 'overview' && (
            <section className="web-profile-main">
              <div className="web-profile-title-row">
                <div>
                  <span>Candidate</span>
                  <h2>{profile.candidate_name}</h2>
                </div>
                {profile.resume_id && <strong className="web-profile-id">#{profile.resume_id}</strong>}
              </div>

              <div className="web-profile-facts">
                {facts.map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>

              {profile.tags.length > 0 && (
                <div className="web-profile-tags">
                  {profile.tags.map(tag => <span key={tag}>{tag}</span>)}
                </div>
              )}

              <div className="web-profile-text">
                <span>Profile text</span>
                {rawText ? <pre>{rawText}</pre> : <p>No additional profile text returned.</p>}
              </div>

              <aside className="web-profile-side">
                <div className={`index-status ${error ? 'warning' : 'success'}`}>
                  <strong>{error ? 'Showing search result data' : 'Loaded in your workspace'}</strong>
                  {error && <p>{error}</p>}
                </div>
                {profile.profile_url && (
                  <a className="web-profile-action" href={profile.profile_url} target="_blank" rel="noreferrer">
                    Open {sourceLabel} source
                  </a>
                )}
              </aside>
            </section>
          )}
        </div>
      </div>
      <style>{`
        .web-profile-analysis {
          padding: 16px;
          height: 100%;
        }
        .web-profile-analysis-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          padding: 60px 24px;
          color: #64748b;
          font-size: 14px;
        }
        .detail-spinner {
          width: 36px;
          height: 36px;
          border: 3px solid #e2e8f0;
          border-top-color: #0891b2;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .web-profile-analysis-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 24px;
          color: #94a3b8;
          font-size: 14px;
        }
        .web-profile-analysis-error {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 40px 24px;
          color: #dc2626;
          font-size: 14px;
          font-weight: 600;
          text-align: center;
        }
        .web-profile-score-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-right: auto;
        }
        .ranking-detail-tabs {
          display: flex;
          gap: 4px;
          padding: 8px 16px;
          border-bottom: 1px solid #e2e8f0;
          background: #f8fafc;
          flex-wrap: wrap;
        }
        .ranking-detail-tabs button {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 14px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          background: white;
          color: #475569;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
        }
        .ranking-detail-tabs button:hover {
          background: #f1f5f9;
        }
        .ranking-detail-tabs button.active {
          background: #0891b2;
          color: white;
          border-color: #0891b2;
        }
        .tab-badge {
          font-size: 9px;
          padding: 1px 5px;
          border-radius: 4px;
          background: rgba(0,0,0,0.08);
          color: inherit;
        }
        .tab-badge.loading {
          animation: pulse 1s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
