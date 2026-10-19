import { useState } from 'react';
import type { SearchCvResult } from '../types/search';

export type WebSource = 'careerviet' | 'vietnamworks' | 'scholar';

interface RunWebSearchDeps {
  source: WebSource;
  showNotify: (msg: string) => void;
}

export function useWebSearch() {
  const [webSearchMode, setWebSearchMode] = useState<'text' | 'file'>('text');
  const [webSearchJdText, setWebSearchJdText] = useState('');
  const [webSearchJdFile, setWebSearchJdFile] = useState<File | null>(null);
  const [webSearchTopK, setWebSearchTopK] = useState(10);
  const [webSearchMinScore, setWebSearchMinScore] = useState(0);
  const [webSearchRerank, setWebSearchRerank] = useState(false);
  const [webSearchRerankTopN, setWebSearchRerankTopN] = useState(5);
  const [webSearchSource, setWebSearchSource] = useState<WebSource>('careerviet');
  const [webSearchResults, setWebSearchResults] = useState<SearchCvResult[]>([]);
  const [webSearchLoading] = useState(false);
  const [webSearchMeta, setWebSearchMeta] = useState<{ total: number; query: string } | null>(null);
  const [webSearchRerankTopK] = useState(5);
  const [webSearchLoadingLabel] = useState('');
  const [webSelectedModel, setWebSelectedModel] = useState('');
  const [webModelOptions] = useState<{ id: string; display_name: string }[]>([]);

  const resetWebSearchState = () => {
    setWebSearchResults([]);
    setWebSearchMeta(null);
  };

  const handleWebSearchJdFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setWebSearchJdFile(file);
    setWebSearchResults([]);
    setWebSearchMeta(null);
    event.target.value = '';
  };

  const handleRunWebSearch = async (_deps: RunWebSearchDeps) => {
    // This is a stub - actual implementation would call the web search APIs
    // The actual search logic is handled in HybridSearchingSection
  };

  const handleReindexWeb = async (_deps: { showNotify: (msg: string) => void }) => {
    // Stub for reindex web
  };

  return {
    webSearchMode, setWebSearchMode,
    webSearchJdText, setWebSearchJdText,
    webSearchJdFile, setWebSearchJdFile,
    webSearchTopK, setWebSearchTopK,
    webSearchMinScore, setWebSearchMinScore,
    webSearchRerank, setWebSearchRerank,
    webSearchRerankTopN, setWebSearchRerankTopN,
    webSearchSource, setWebSearchSource,
    webSearchResults, setWebSearchResults,
    webSearchLoading,
    webSearchMeta, setWebSearchMeta,
    webSearchRerankTopK,
    webSearchLoadingLabel,
    webSelectedModel, setWebSelectedModel,
    webModelOptions,
    resetWebSearchState,
    handleWebSearchJdFileChange,
    handleRunWebSearch,
    handleReindexWeb,
  };
}
