interface JdInputPanelProps {
  jdMode: 'text' | 'file';
  setJdMode: (mode: 'text' | 'file') => void;
  jdText: string;
  setJdText: (value: string) => void;
  jdFile: File | null;
  onJdFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
}

export default function JdInputPanel({
  jdMode, setJdMode,
  jdText, setJdText,
  jdFile, onJdFileChange,
  disabled,
}: JdInputPanelProps) {
  return (
    <section className="search-panel jd-query-panel ranking-jd-panel">
      <div className="search-panel-header ranking-header">
        <h2>Job Description</h2>
        <div className="search-mode-tabs ranking-tabs" role="tablist" aria-label="JD input mode">
          <button
            type="button"
            className={jdMode === 'text' ? 'active' : ''}
            onClick={() => setJdMode('text')}
            disabled={disabled}
          >
            Text
          </button>
          <button
            type="button"
            className={jdMode === 'file' ? 'active' : ''}
            onClick={() => setJdMode('file')}
            disabled={disabled}
          >
            PDF
          </button>
        </div>
      </div>

      {jdMode === 'text' ? (
        <textarea
          className="search-textarea"
          value={jdText}
          onChange={(event) => setJdText(event.target.value)}
          placeholder="Dán nội dung Job Description vào đây. Ví dụ: Senior Backend Engineer, 5+ năm kinh nghiệm Java Spring Boot, PostgreSQL..."
          spellCheck={false}
          disabled={disabled}
        />
      ) : (
        <label className="search-file-drop" htmlFor="ranking-jd-file">
          <input
            id="ranking-jd-file"
            type="file"
            accept=".pdf"
            hidden
            onChange={onJdFileChange}
            disabled={disabled}
          />
          <div className="upload-icon-circle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <strong>{jdFile ? jdFile.name : 'Chọn JD PDF'}</strong>
          {jdFile && <span>{(jdFile.size / 1024 / 1024).toFixed(2)} MB</span>}
        </label>
      )}
    </section>
  );
}
