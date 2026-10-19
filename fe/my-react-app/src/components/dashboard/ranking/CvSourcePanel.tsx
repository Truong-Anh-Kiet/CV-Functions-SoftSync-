import { IconClose } from '../icons';
import type { SavedCvOption } from '../../../types/ranking';

interface CvSourcePanelProps {
  cvSource: 'upload' | 'saved';
  setCvSource: (source: 'upload' | 'saved') => void;
  uploadedCvs: File[];
  onCvFilesChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  removeUploadedCv: (index: number) => void;
  savedCvs: SavedCvOption[];
  savedCvsLoading: boolean;
  selectedSavedIds: Set<number>;
  toggleSavedCv: (id: number) => void;
  onRefreshSaved: () => void;
  onClearAll: () => void;
  disabled?: boolean;
}

export default function CvSourcePanel({
  cvSource, setCvSource,
  uploadedCvs, onCvFilesChange, removeUploadedCv,
  savedCvs, savedCvsLoading, selectedSavedIds, toggleSavedCv,
  onRefreshSaved, onClearAll,
  disabled,
}: CvSourcePanelProps) {
  const totalSelected = uploadedCvs.length + selectedSavedIds.size;

  return (
    <section className="search-panel ranking-cv-panel">
      <div className="search-panel-header ranking-header">
        <h2>CV <span className="ranking-header-count">· {totalSelected}</span></h2>
        <div className="search-mode-tabs ranking-tabs" role="tablist" aria-label="CV source">
          <button
            type="button"
            className={cvSource === 'upload' ? 'active' : ''}
            onClick={() => setCvSource('upload')}
            disabled={disabled}
          >
            Upload
          </button>
          <button
            type="button"
            className={cvSource === 'saved' ? 'active' : ''}
            onClick={() => setCvSource('saved')}
            disabled={disabled}
          >
            Đã lưu ({savedCvs.length})
          </button>
        </div>
      </div>

      {cvSource === 'upload' ? (
        <>
          <label className="search-file-drop ranking-multi-drop" htmlFor="ranking-cv-files">
            <input
              id="ranking-cv-files"
              type="file"
              accept=".pdf"
              hidden
              multiple
              onChange={onCvFilesChange}
              disabled={disabled}
            />
            <div className="upload-icon-circle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <strong>{uploadedCvs.length === 0 ? 'Chọn nhiều CV PDF' : 'Thêm CV PDF'}</strong>
          </label>

          {uploadedCvs.length > 0 && (
            <ul className="ranking-selected-list">
              {uploadedCvs.map((file, index) => (
                <li key={`${file.name}-${index}`}>
                  <div className="ranking-selected-info">
                    <strong title={file.name}>{file.name}</strong>
                    <span>{(file.size / 1024).toFixed(0)} KB</span>
                  </div>
                  <button
                    type="button"
                    className="ranking-selected-remove"
                    onClick={() => removeUploadedCv(index)}
                    aria-label={`Xoá ${file.name}`}
                    disabled={disabled}
                  >
                    <IconClose />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <div className="ranking-saved-wrap">
          <div className="ranking-saved-toolbar">
            <span>{selectedSavedIds.size} / {savedCvs.length} đã chọn</span>
            <button
              type="button"
              className="ranking-link-btn"
              onClick={onRefreshSaved}
              disabled={disabled || savedCvsLoading}
            >
              {savedCvsLoading ? 'Đang tải...' : 'Tải lại'}
            </button>
          </div>

          {savedCvs.length === 0 ? (
            <div className="empty-search-state">
              <strong>{savedCvsLoading ? 'Đang tải saved CVs...' : 'Chưa có CV nào trong kho'}</strong>
              <span>Mở mục "CV Storage" để tải CV lên trước.</span>
            </div>
          ) : (
            <ul className="ranking-saved-list">
              {savedCvs.map((cv) => {
                const checked = selectedSavedIds.has(cv.id);
                return (
                  <li
                    key={cv.id}
                    className={checked ? 'ranking-saved-item active' : 'ranking-saved-item'}
                  >
                    <label>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleSavedCv(cv.id)}
                        disabled={disabled}
                      />
                      <div className="ranking-selected-info">
                        <strong title={cv.filename}>{cv.filename}</strong>
                        <span>CV #{cv.id}</span>
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {totalSelected > 0 && (
        <div className="ranking-cv-footer">
          <button
            type="button"
            className="ranking-link-btn danger"
            onClick={onClearAll}
            disabled={disabled}
          >
            Xoá toàn bộ lựa chọn
          </button>
        </div>
      )}
    </section>
  );
}
