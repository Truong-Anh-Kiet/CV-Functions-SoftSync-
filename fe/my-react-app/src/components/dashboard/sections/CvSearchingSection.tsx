import type { SearchCvResult, SearchApiResponse, ReindexApiResponse } from '../../../types/search';
import type { ModelOption } from '../../../types/model';
import { JdQueryPanel } from '../searching/JdQueryPanel';
import SearchSummaryPanel from '../searching/SearchSummaryPanel';
import SearchResultsTable from '../searching/SearchResultsTable';

interface CvSearchingSectionProps {
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
}

export default function CvSearchingSection(props: CvSearchingSectionProps) {
  return (
    <div className="searching-workspace">
      <div className="searching-grid">
        <JdQueryPanel
          mode={props.searchMode}
          setMode={props.setSearchMode}
          jdText={props.searchJdText}
          setJdText={props.setSearchJdText}
          jdFile={props.searchJdFile}
          topK={props.searchTopK}
          setTopK={props.setSearchTopK}
          minScore={props.searchMinScore}
          setMinScore={props.setSearchMinScore}
          autoIndex={props.searchAutoIndex}
          setAutoIndex={props.setSearchAutoIndex}
          rerank={props.searchRerank}
          setRerank={props.setSearchRerank}
          rerankTopN={props.searchRerankTopN}
          setRerankTopN={props.setSearchRerankTopN}
          loading={props.searchLoading}
          reindexLoading={props.reindexLoading}
          currentSearchMeta={props.currentSearchMeta ? `${props.currentSearchMeta.returned}/${props.currentSearchMeta.total_cvs} CV phù hợp` : null}
          currentReindexSummary={props.currentReindexSummary ? `${props.currentReindexSummary.successful}/${props.currentReindexSummary.total_cvs} CV đã index` : null}
          modelOptions={props.modelOptions}
          selectedModel={props.selectedModel}
          setSelectedModel={props.setSelectedModel}
          onJdFileChange={props.onSearchJdFileChange}
          onSearch={props.onRunCvSearch}
          onReindex={props.onReindexAllCvs}
        />

        <SearchSummaryPanel
          currentCvTotal={props.currentCvTotal}
          currentSearchMeta={props.currentSearchMeta}
          currentReindexSummary={props.currentReindexSummary}
          searchMeta={props.searchMeta}
          selectedModel={props.selectedModel}
          modelOptions={props.modelOptions}
        />
      </div>

      <SearchResultsTable
        searchResults={props.searchResults}
        searchMeta={props.searchMeta}
        searchLoading={props.searchLoading}
        savedCvsLength={props.savedCvsLength}
        onViewDbCv={props.onViewSearchCv}
      />
    </div>
  );
}
