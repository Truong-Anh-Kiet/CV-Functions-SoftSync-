import type { ModelOption } from '../../../types/model';

interface JdQueryPanelProps {
  mode: 'text' | 'file';
  setMode: (mode: 'text' | 'file') => void;
  jdText: string;
  setJdText: (text: string) => void;
  jdFile: File | null;
  topK: number;
  setTopK: (value: number) => void;
  minScore: number;
  setMinScore: (value: number) => void;
  autoIndex: boolean;
  setAutoIndex: (value: boolean) => void;
  rerank: boolean;
  setRerank: (value: boolean) => void;
  rerankTopN: number;
  setRerankTopN: (value: number) => void;
  loading: boolean;
  reindexLoading: boolean;
  currentSearchMeta: string | null;
  currentReindexSummary: string | null;
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  onJdFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSearch: () => void;
  onReindex: () => void;
  showDatabase?: boolean;
  showWeb?: boolean;
  selectedSources?: Set<string>;
  hideStatusBar?: boolean;
}

export function JdQueryPanel(props: JdQueryPanelProps) {
  const {
    mode, setMode,
    jdText, setJdText,
    jdFile,
    topK, setTopK,
    minScore, setMinScore,
    autoIndex, setAutoIndex,
    rerank, setRerank,
    loading,
    reindexLoading,
    currentSearchMeta,
    currentReindexSummary,
    modelOptions,
    selectedModel, setSelectedModel,
    onJdFileChange,
    onSearch,
    onReindex,
    showDatabase = true,
    showWeb = false,
    hideStatusBar = false,
  } = props;

  const searchMode = mode;
  const setSearchMode = setMode;
  const searchJdText = jdText;
  const setSearchJdText = setJdText;
  const searchJdFile = jdFile;
  const searchTopK = topK;
  const setSearchTopK = setTopK;
  const searchMinScore = minScore;
  const setSearchMinScore = setMinScore;
  const searchAutoIndex = autoIndex;
  const setSearchAutoIndex = setAutoIndex;
  const searchRerank = rerank;
  const setSearchRerank = setRerank;
  const onSearchJdFileChange = onJdFileChange;
  const onRunCvSearch = onSearch;
  const onReindexAllCvs = onReindex;

  const hasBoth = showDatabase && showWeb;

  return (
    <section className="search-panel jd-query-panel">
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
              placeholder="Java Spring Boot PostgreSQL backend developer..."
              spellCheck={false}
            />
          ) : (
            <label className="search-file-drop" htmlFor="search-jd-file">
              <input id="search-jd-file" type="file" accept=".pdf" hidden onChange={onSearchJdFileChange} />
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

          <div className="search-controls-row">
            <label className="search-field">
              <span>Model</span>
              <select
                className="search-select"
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value)}
                disabled={loading || reindexLoading || modelOptions.length === 0}
              >
                {modelOptions.length === 0 ? (
                  <option value="">Default model</option>
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
                min={1}
                max={500}
                value={searchTopK}
                onChange={(event) => setSearchTopK(Number(event.target.value))}
              />
            </label>
            <label className="search-field">
              <span>Min score</span>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={searchMinScore}
                onChange={(event) => setSearchMinScore(Number(event.target.value))}
              />
            </label>
            <label className="search-toggle">
              <input type="checkbox" checked={searchAutoIndex} onChange={(event) => setSearchAutoIndex(event.target.checked)} />
              Auto index
            </label>
            <label className="search-toggle">
              <input type="checkbox" checked={searchRerank} onChange={(event) => setSearchRerank(event.target.checked)} />
              AI rerank
            </label>
          </div>

          {!hideStatusBar && (currentSearchMeta || currentReindexSummary) && (
            <div className="search-status-bar">
              {currentSearchMeta && <span>{currentSearchMeta}</span>}
              {currentReindexSummary && <span>{currentReindexSummary}</span>}
            </div>
          )}
        </div>

        <div className="search-actions">
          <button className="search-primary-btn" onClick={onRunCvSearch} disabled={loading || reindexLoading}>
            {loading ? 'Đang tìm...' : (hasBoth ? 'Tìm tất cả' : 'Tìm kiếm')}
          </button>
          <button className="search-secondary-btn" onClick={onReindexAllCvs} disabled={loading || reindexLoading}>
            {reindexLoading ? 'Đang index...' : 'Reindex'}
          </button>
        </div>
      </div>
    </section>
  );
}
