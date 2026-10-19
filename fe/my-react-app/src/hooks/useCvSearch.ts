import { useState } from 'react';
import type { SearchCvResult, SearchApiResponse, ReindexApiResponse } from '../types/search';
import { searchCvs, reindexAllCvs } from '../services/api';

interface RunSearchDeps {
  modelId: string;
  showNotify: (msg: string) => void;
}

interface ReindexDeps {
  modelId: string;
  showNotify: (msg: string) => void;
  onComplete?: () => Promise<void> | void;
}

export function useCvSearch() {
  const [searchMode, setSearchMode] = useState<'text' | 'file'>('text');
  const [searchJdText, setSearchJdText] = useState('');
  const [searchJdFile, setSearchJdFile] = useState<File | null>(null);
  const [searchTopK, setSearchTopK] = useState(10);
  const [searchMinScore, setSearchMinScore] = useState(0);
  const [searchAutoIndex, setSearchAutoIndex] = useState(true);
  const [searchRerank, setSearchRerank] = useState(false);
  const [searchRerankTopN, setSearchRerankTopN] = useState(5);
  const [searchLoading, setSearchLoading] = useState(false);
  const [reindexLoading, setReindexLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchCvResult[]>([]);
  const [searchMeta, setSearchMeta] = useState<SearchApiResponse['data'] | null>(null);
  const [reindexSummary, setReindexSummary] = useState<ReindexApiResponse['data'] | null>(null);

  const resetSearchState = () => {
    setSearchMeta(null);
    setReindexSummary(null);
    setSearchResults([]);
  };

  const handleSearchJdFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSearchJdFile(file);
    setSearchResults([]);
    setSearchMeta(null);
    event.target.value = '';
  };

  const handleReindexAllCvs = async (deps: ReindexDeps) => {
    const { modelId, showNotify, onComplete } = deps;
    setReindexLoading(true);
    setReindexSummary(null);
    try {
      showNotify('Đang tạo embedding cho kho CV...');
      const { ok, result } = await reindexAllCvs({ modelId: modelId || undefined });
      if (!ok || result.status !== 'success') {
        throw new Error(result.detail || 'Không thể reindex kho CV');
      }
      setReindexSummary(result.data ?? null);
      showNotify(`Đã index ${result.data?.successful ?? 0}/${result.data?.total_cvs ?? 0} CV.`);
      await onComplete?.();
    } catch (error) {
      showNotify(error instanceof Error ? error.message : 'Lỗi khi reindex kho CV');
    } finally {
      setReindexLoading(false);
    }
  };

  const handleRunCvSearch = async (deps: RunSearchDeps) => {
    const { modelId, showNotify } = deps;
    const cleanText = searchJdText.trim();
    if (searchMode === 'text' && !cleanText) {
      showNotify('Vui lòng nhập nội dung JD.');
      return;
    }
    if (searchMode === 'file' && !searchJdFile) {
      showNotify('Vui lòng chọn file JD PDF.');
      return;
    }

    const safeTopK = Math.max(1, Math.min(500, searchTopK));
    const safeRerankTopN = Math.max(1, Math.min(safeTopK, searchRerankTopN));
    const safeMinScore = Math.max(0, Math.min(1, searchMinScore));

    setSearchLoading(true);
    setSearchResults([]);
    setSearchMeta(null);
    try {
      showNotify(searchRerank ? 'Đang search CV và rerank bằng AI...' : 'Đang search CV bằng embedding...');
      const { ok, result } = await searchCvs({
        mode: searchMode,
        jdText: searchMode === 'text' ? cleanText : undefined,
        jdFile: searchMode === 'file' ? searchJdFile : null,
        topK: safeTopK,
        minScore: safeMinScore,
        autoIndexMissing: searchAutoIndex,
        rerank: searchRerank,
        rerankTopN: safeRerankTopN,
        modelId: modelId || undefined,
      });
      if (!ok || result.status !== 'success') {
        throw new Error(result.detail || 'Không thể search CV');
      }
      setSearchMeta(result.data ?? null);
      setSearchResults(result.data?.results ?? []);
      showNotify(`Tìm thấy ${result.data?.returned ?? 0} CV phù hợp.`);
    } catch (error) {
      showNotify(error instanceof Error ? error.message : 'Lỗi khi search CV');
    } finally {
      setSearchLoading(false);
    }
  };

  return {
    searchMode, setSearchMode,
    searchJdText, setSearchJdText,
    searchJdFile, setSearchJdFile,
    searchTopK, setSearchTopK,
    searchMinScore, setSearchMinScore,
    searchAutoIndex, setSearchAutoIndex,
    searchRerank, setSearchRerank,
    searchRerankTopN, setSearchRerankTopN,
    searchLoading,
    reindexLoading,
    searchResults, setSearchResults,
    searchMeta, setSearchMeta,
    reindexSummary, setReindexSummary,
    resetSearchState,
    handleSearchJdFileChange,
    handleReindexAllCvs,
    handleRunCvSearch,
  };
}
