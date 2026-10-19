import { useEffect, useMemo, useState } from 'react';
import type { SearchApiResponse, SearchCvResult, ReindexApiResponse } from '../../../types/search';
import type { ModelOption } from '../../../types/model';
import type { AcademicProfile, CareerVietProfile, VietnamWorksProfile } from '../../../services/api';
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
} from '../../../services/api';
import { buildWebSearchQuery, rankWebProfilesFromJd, resolveWebBreakdownLabels, resolveWebRankingWeights } from '../../../utils/webCvRanking';
import { JdQueryPanel } from './JdQueryPanel';
import SearchSummaryPanel from './SearchSummaryPanel';
import SearchResultsTable from './SearchResultsTable';
import WebSearchResultsTable from './WebSearchResultsTable';
import SearchDetailModal from '../modals/SearchDetailModal';
import CvDetailModal from '../modals/CvDetailModal';

export type HybridSource = 'database' | 'web';
type WebSource = 'careerviet' | 'vietnamworks' | 'scholar';
type WebProfile = AcademicProfile | CareerVietProfile | VietnamWorksProfile;

interface HybridSearchingSectionProps {
  searchMode: 'text' | 'file';
  setSearchMode: (mode: 'text' | 'file') => void;
  searchJdText: string;
  setSearchJdText: (text: string) => void;
  searchJdFile: File | null;
  searchTopK: number;
  setSearchTopK: (value: number) => void;
  searchMinScore: number;
  setSearchMinScore: (value: number) => void;
  searchAutoIndex: boolean;
  setSearchAutoIndex: (value: boolean) => void;
  searchRerank: boolean;
  setSearchRerank: (value: boolean) => void;
  searchRerankTopN: number;
  setSearchRerankTopN: (value: number) => void;
  searchLoading: boolean;
  reindexLoading: boolean;
  searchResults: SearchCvResult[];
  searchMeta: SearchApiResponse['data'] | null;
  currentSearchMeta: SearchApiResponse['data'] | null;
  currentReindexSummary: ReindexApiResponse['data'] | null;
  currentCvTotal: number;
  savedCvsLength: number;
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  onSearchJdFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onRunCvSearch: () => void;
  onReindexAllCvs: () => void;
  onViewSearchCv: (result: SearchCvResult) => void;
  onViewWebCv: (result: SearchCvResult) => void;
  onViewDbCv: (result: SearchCvResult) => void;
  showNotify: (msg: string) => void;
  selectedSources: Set<HybridSource>;
  setSelectedSources: React.Dispatch<React.SetStateAction<Set<HybridSource>>>;
}

const WEB_SOURCE_OPTIONS: { id: WebSource; label: string }[] = [
  { id: 'careerviet', label: 'CareerViet' },
  { id: 'vietnamworks', label: 'VietnamWorks' },
  { id: 'scholar', label: 'Google Scholar' },
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

export default function HybridSearchingSection(props: HybridSearchingSectionProps) {
  const {
    searchMode,
    setSearchMode,
    searchJdText,
    setSearchJdText,
    searchJdFile,
    searchTopK,
    setSearchTopK,
    searchMinScore,
    setSearchMinScore,
    searchAutoIndex,
    setSearchAutoIndex,
    searchRerank,
    setSearchRerank,
    searchRerankTopN,
    setSearchRerankTopN,
    searchLoading,
    reindexLoading,
    searchResults,
    searchMeta,
    currentSearchMeta,
    currentReindexSummary,
    currentCvTotal,
    savedCvsLength,
    modelOptions,
    selectedModel,
    setSelectedModel,
    onSearchJdFileChange,
    onRunCvSearch,
    onReindexAllCvs,
    onViewSearchCv: _onViewSearchCv,
    onViewWebCv,
    onViewDbCv: _onViewDbCv,
    showNotify,
    selectedSources,
    setSelectedSources,
  } = props;

  const [selectedWebSources, setSelectedWebSources] = useState<Set<WebSource>>(new Set(['careerviet']));
  const [webSearchResults, setWebSearchResults] = useState<SearchCvResult[]>([]);
  const [webSearchMeta, setWebSearchMeta] = useState<SearchApiResponse['data'] | null>(null);
  const [webSearchLoading, setWebSearchLoading] = useState(false);
  const [webSearchError, setWebSearchError] = useState('');
  const [webSourceTotal, setWebSourceTotal] = useState<number | null>(null);
  const [_webSourceTotalLoading, setWebSourceTotalLoading] = useState(false);
  const [webProfilesByResultId, setWebProfilesByResultId] = useState<Record<string, WebProfile>>({});
  const [detailCvResult, setDetailCvResult] = useState<SearchCvResult | null>(null);
  const [detailCvProfile, setDetailCvProfile] = useState<AcademicProfile | CareerVietProfile | VietnamWorksProfile | null>(null);
  const [detailSearchResult, setDetailSearchResult] = useState<SearchCvResult | null>(null);
  const [detailSearchMode, setDetailSearchMode] = useState<'database' | 'web'>('database');
  const [detailSearchJdText, setDetailSearchJdText] = useState<string>('');
  const [detailSearchJdFile, setDetailSearchJdFile] = useState<File | null>(null);
  const [detailCvText, setDetailCvText] = useState<string>('');
  const [detailCvFilename, setDetailCvFilename] = useState<string>('');

  const showDatabase = selectedSources.has('database');
  const showWeb = selectedSources.has('web');
  const isHybridMode = showDatabase && showWeb;

  const selectedModelOption = useMemo(
    () => modelOptions.find(model => model.id === selectedModel),
    [modelOptions, selectedModel],
  );
  const selectedWebSourceList = useMemo(
    () => WEB_SOURCE_OPTIONS.filter(option => selectedWebSources.has(option.id)).map(option => option.id),
    [selectedWebSources],
  );
  const selectedWebSourceTitle = useMemo(
    () => selectedWebSourceList.map(source => WEB_SOURCE_LABELS[source]).join(' + ') || 'Web',
    [selectedWebSourceList],
  );
  const statusTotalCount = (
    (showDatabase ? currentCvTotal : 0)
    + (showWeb ? (webSourceTotal ?? 0) : 0)
  );

  useEffect(() => {
    let ignore = false;

    const loadSourceTotal = async () => {
      if (!showWeb) return;
      setWebSourceTotalLoading(true);
      try {
        const totals = await Promise.all(
          selectedWebSourceList.map(async source => {
            const { ok, result } = await sourceApiFor(source).search({ page: 1, pageSize: 1 });
            return ok && result.data ? result.data.total : 0;
          }),
        );
        if (!ignore) {
          setWebSourceTotal(totals.reduce((sum, value) => sum + value, 0));
        }
      } catch {
        if (!ignore) setWebSourceTotal(null);
      } finally {
        if (!ignore) setWebSourceTotalLoading(false);
      }
    };

    loadSourceTotal();
    return () => {
      ignore = true;
    };
  }, [showWeb, selectedWebSourceList]);

  const toggleSource = (source: HybridSource) => {
    setSelectedSources(prev => {
      const next = new Set(prev);
      if (next.has(source)) {
        if (next.size > 1) next.delete(source);
      } else {
        next.add(source);
      }
      return next;
    });
  };

  const toggleWebSource = (source: WebSource) => {
    setSelectedWebSources(prev => {
      const next = new Set(prev);
      if (next.has(source)) {
        if (next.size > 1) next.delete(source);
      } else {
        next.add(source);
      }
      return next;
    });
  };

  const handleRunWebSearch = async () => {
    const query = searchJdText.trim();
    setWebSearchLoading(true);
    setWebSearchError('');

    try {
      if (selectedWebSourceList.length === 0) {
        throw new Error('Please select at least one web source.');
      }
      if (searchMode === 'file' && !searchJdFile) {
        throw new Error('Vui lòng chọn file JD PDF.');
      }
      if (searchMode === 'text' && !query) {
        throw new Error('Vui lòng nhập nội dung JD hoặc từ khóa.');
      }

      const safeTopK = Math.max(1, Math.min(100, searchTopK));
      const safeRerankTopN = Math.max(1, Math.min(safeTopK, searchRerankTopN));
      const fetchPoolSize = 100;
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
      const sourceResponses: Array<{ source: WebSource; ok: boolean; result: any }> = await Promise.all(
        selectedWebSourceList.map(async source => {
          const sourceApi = sourceApiFor(source);
          try {
            let response = searchRerank
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
            if (response.ok && response.result.data && (response.result.data.items?.length ?? 0) === 0) {
              response = await sourceApi.searchByJd({
                jdText: searchMode === 'text' ? query : undefined,
                jdFile: searchMode === 'file' ? searchJdFile : null,
                page: 1,
                pageSize: fetchPoolSize,
              });
            }
            return { source, ...response };
          } catch (error) {
            return {
              source,
              ok: false,
              result: {
                detail: error instanceof Error ? error.message : `${WEB_SOURCE_LABELS[source]} search failed.`,
              },
            };
          }
        }),
      );

      const successfulResponses = sourceResponses.filter(item => item.ok && item.result.data);
      if (successfulResponses.length === 0) {
        const firstError = sourceResponses.find(item => item.result.detail)?.result.detail;
        throw new Error(firstError || 'Khong the tim kiem Web.');
      }

      const allProfiles = successfulResponses.flatMap(item => item.result.data?.items ?? []);
      const ranking = rankWebProfilesFromJd(
        allProfiles,
        jdAnalysis,
        selectedModel,
        selectedModelOption?.sbert_id,
        safeTopK,
        usdVndRate,
      );
      const finalResults = ranking.toppedUp
        .filter(item => (item.total_score ?? 0) >= searchMinScore * 100)
        .slice(0, safeTopK);

      const nextProfilesByResultId = allProfiles.reduce<Record<string, WebProfile>>((acc, profile) => {
        acc[String(profile.id)] = profile;
        return acc;
      }, {});

      const failedResponses = sourceResponses.filter(item => !item.ok || !item.result.data);
      const skippedCvs = [
        ...successfulResponses.flatMap(item => item.result.data?.skipped_cvs ?? []),
        ...failedResponses.map(item => ({
          id: item.source,
          filename: WEB_SOURCE_LABELS[item.source],
          reason: item.result.detail || `${WEB_SOURCE_LABELS[item.source]} search failed.`,
        })),
      ];
      const rerankResults = successfulResponses.flatMap(item => item.result.data?.rerank?.results ?? []);
      const total = successfulResponses.reduce((sum, item) => sum + (item.result.data?.total ?? 0), 0);

      const meta: SearchApiResponse['data'] = {
        success: true,
        jd_analysis: jdAnalysis,
        total_candidates: finalResults.length,
        total_cvs: total,
        search_mode: searchMode,
        embedding_model_id: selectedModel || 'web-search',
        sbert_id: selectedModelOption?.sbert_id,
        indexed_cvs: total,
        indexed_missing: 0,
        skipped_cvs: skippedCvs,
        returned: finalResults.length,
        top_k: searchTopK,
        min_score: searchMinScore,
        auto_index_missing: false,
        ranking_weights: {
          ...resolveWebRankingWeights(jdAnalysis, usdVndRate).normalized,
        },
        score_breakdown_labels: resolveWebBreakdownLabels(jdAnalysis, usdVndRate),
        usd_vnd_rate: usdVndRate,
        filtered_out: ranking.filtered.length,
        results: finalResults,
        rerank: rerankResults.length > 0 ? { results: rerankResults } : null,
      };

      setWebSourceTotal(total);
      setWebSearchResults(finalResults);
      setWebSearchMeta(meta);
      setWebProfilesByResultId(nextProfilesByResultId);
      if (failedResponses.length > 0) {
        setWebSearchError(
          failedResponses
            .map(item => `${WEB_SOURCE_LABELS[item.source]}: ${item.result.detail || 'failed'}`)
            .join(' | '),
        );
      } else {
        setWebSearchError('');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Không thể tìm kiếm Web.';
      setWebSearchResults([]);
      setWebProfilesByResultId({});
      setWebSearchMeta({
        success: false,
        total_cvs: 0,
        search_mode: searchMode,
        embedding_model_id: selectedModel || 'web-search',
        sbert_id: selectedModelOption?.sbert_id,
        indexed_cvs: 0,
        indexed_missing: 0,
        skipped_cvs: [{ id: 'web', filename: selectedWebSourceTitle, reason: message }],
        returned: 0,
        top_k: searchTopK,
        min_score: searchMinScore,
        auto_index_missing: false,
        results: [],
        rerank: null,
      });
      setWebSearchError(message);
      showNotify(message);
    } finally {
      setWebSearchLoading(false);
    }
  };

  const handleRunHybridSearch = () => {
    if (showDatabase) onRunCvSearch();
    if (showWeb) {
      void handleRunWebSearch();
    }
  };

  const handleViewDbCv = (result: SearchCvResult) => {
    setDetailSearchMode('database');
    setDetailSearchResult(result);
    setDetailCvResult(null);
    setDetailSearchJdText(searchJdText);
    setDetailSearchJdFile(searchJdFile);
    setDetailCvText('');
    setDetailCvFilename('');
  };

  const handleViewHybridWebCv = async (result: SearchCvResult) => {
    const profile = webProfilesByResultId[String(result.id)];
    if (!profile) {
      onViewWebCv(result);
      return;
    }

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
      const detailProfile = ok && detailResult.data ? detailResult.data : profile;
      const previewUrl = isAcademicProfile(detailProfile)
        ? academicProfileFileUrl(detailProfile.id, detailProfile.profile_url)
        : isVietnamWorksProfile(detailProfile)
          ? vietnamWorksProfileFileUrl(detailProfile.id, detailProfile.profile_url)
          : careerVietProfileFileUrl(detailProfile.id, detailProfile.profile_url, detailProfile.salary);

      const cvResult: SearchCvResult = {
        ...result,
        id: String(detailProfile.id),
        filename: `${detailProfile.title} - ${detailProfile.candidate_name}`,
        preview_url: previewUrl || (isVietnamWorksProfile(detailProfile) ? undefined : result.preview_url),
        cloudinary_url: previewUrl || undefined,
        text_length: (detailProfile as any).raw_text?.length || (detailProfile as any).summary?.length,
      };
      const rawText = (detailProfile as any).raw_text || (detailProfile as any).summary || '';
      const filename = `${detailProfile.title} - ${detailProfile.candidate_name}.txt`;
      console.log('[Hybrid] handleViewHybridWebCv', {
        profileId: detailProfile.id,
        hasRawText: Boolean(rawText),
        rawTextLength: rawText.length,
        searchJdText,
        hasSearchJdFile: Boolean(searchJdFile),
      });
      setDetailSearchMode('web');
      setDetailSearchResult(cvResult);
      setDetailCvResult(null);
      setDetailSearchJdText(searchJdText);
      setDetailSearchJdFile(searchJdFile);
      setDetailCvText(rawText);
      setDetailCvFilename(filename);
    } catch {
      onViewWebCv(result);
    }
  };

  return (
    <div className="searching-workspace">
      <div className="searching-grid">
        <div>
          <section className="search-panel jd-query-panel">
            <div className="hybrid-source-row">
              <span className="hybrid-source-label">Nguồn tìm kiếm</span>
              <div className="hybrid-source-checkboxes">
                <label className="hybrid-source-checkbox">
                  <span className="db-source-badge">Database</span>
                  <input
                    type="checkbox"
                    checked={showDatabase}
                    onChange={() => toggleSource('database')}
                  />
                </label>
                <label className="hybrid-source-checkbox">
                  <span className="web-source-badge">Web</span>
                  <input
                    type="checkbox"
                    checked={showWeb}
                    onChange={() => toggleSource('web')}
                  />
                </label>
                {showWeb && (
                  <div className="hybrid-web-source-options" role="group" aria-label="Web sources">
                    {WEB_SOURCE_OPTIONS.map(option => (
                      <label
                        key={option.id}
                        className={`hybrid-web-source-checkbox ${selectedWebSources.has(option.id) ? 'active' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedWebSources.has(option.id)}
                          onChange={() => toggleWebSource(option.id)}
                          disabled={webSearchLoading}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <JdQueryPanel
              mode={searchMode}
              setMode={setSearchMode}
              jdText={searchJdText}
              setJdText={setSearchJdText}
              jdFile={searchJdFile}
              topK={searchTopK}
              setTopK={setSearchTopK}
              minScore={searchMinScore}
              setMinScore={setSearchMinScore}
              autoIndex={searchAutoIndex}
              setAutoIndex={setSearchAutoIndex}
              rerank={searchRerank}
              setRerank={setSearchRerank}
              rerankTopN={searchRerankTopN}
              setRerankTopN={setSearchRerankTopN}
              loading={searchLoading || webSearchLoading}
              reindexLoading={reindexLoading}
              currentSearchMeta={currentSearchMeta ? `${currentSearchMeta.returned}/${currentSearchMeta.total_cvs} CV phù hợp` : null}
              currentReindexSummary={currentReindexSummary ? `${currentReindexSummary.successful}/${currentReindexSummary.total_cvs} CV đã index` : null}
              modelOptions={modelOptions}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              onJdFileChange={onSearchJdFileChange}
              onSearch={handleRunHybridSearch}
              onReindex={onReindexAllCvs}
              showDatabase={showDatabase}
              showWeb={showWeb}
              hideStatusBar
            />
          </section>
        </div>

        <SearchSummaryPanel
          currentCvTotal={showDatabase ? currentCvTotal : (webSourceTotal ?? 0)}
          currentSearchMeta={showDatabase ? currentSearchMeta : webSearchMeta}
          currentReindexSummary={showDatabase ? currentReindexSummary : null}
          searchMeta={showDatabase ? searchMeta : webSearchMeta}
          selectedModel={selectedModel}
          modelOptions={modelOptions}
          showIndexDetails={showDatabase}
          headingLabel={showDatabase && showWeb ? 'Hybrid status' : showWeb ? 'Web source' : 'Index status'}
          title={showDatabase && showWeb ? `Database + ${selectedWebSourceTitle}` : showWeb ? selectedWebSourceTitle : 'CV database'}
          summaryCount={statusTotalCount}
          compact={showDatabase || showWeb}
          statusActive={searchLoading || webSearchLoading || reindexLoading}
          statusMessage={
            reindexLoading
              ? 'Dang reindex CV'
              : searchLoading || webSearchLoading
                ? 'Dang tim kiem va matching'
                : 'San sang chay tim kiem'
          }
        />
      </div>

      <div className={`search-results-area ${isHybridMode ? 'dual-pane' : ''}`}>
        {showDatabase && (
          <div className="search-results-panel">
            <div className="results-panel-head">
              <div>
                <span>Database</span>
                <h2>{searchResults.length} CV</h2>
              </div>
            </div>
            <SearchResultsTable
              searchResults={searchResults}
              searchMeta={searchMeta}
              searchLoading={searchLoading}
              savedCvsLength={savedCvsLength}
              onViewDbCv={handleViewDbCv}
            />
          </div>
        )}

        {showWeb && (
          <div className="search-results-panel">
            <div className="results-panel-head">
              <div>
                <span>Web</span>
                <h2>{webSearchResults.length} CV</h2>
              </div>
            </div>
            <WebSearchResultsTable
              searchResults={webSearchResults}
              searchMeta={webSearchMeta}
              searchLoading={webSearchLoading}
              loadingLabel={`Dang tim tren ${selectedWebSourceTitle}...`}
              onViewCv={handleViewHybridWebCv}
            />
            {webSearchError && <div className="web-error">{webSearchError}</div>}
          </div>
        )}
      </div>

      <CvDetailModal
        result={detailCvResult}
        profile={detailCvProfile as any}
        searchMeta={searchMeta}
        onClose={() => { setDetailCvResult(null); setDetailCvProfile(null); }}
      />

      <SearchDetailModal
        result={detailSearchResult}
        jdText={detailSearchJdText}
        jdFile={detailSearchJdFile}
        cvText={detailSearchMode === 'web' ? detailCvText : undefined}
        cvFilename={detailSearchMode === 'web' ? detailCvFilename : undefined}
        modelId={selectedModel}
        searchMeta={detailSearchMode === 'web' ? webSearchMeta : searchMeta}
        enableAiMatching={searchRerank}
        onClose={() => setDetailSearchResult(null)}
      />
    </div>
  );
}
