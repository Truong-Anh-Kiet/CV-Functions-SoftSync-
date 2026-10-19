import type { UploadedFile } from '../../../types/dashboard';

interface FullDocumentPanelProps {
  title: string;
  file: UploadedFile | undefined;
  previewUrl: string | null | undefined;
  inputId: 'sm-cv' | 'sm-jd';
  onRemove: (id: string) => void;
}

export default function FullDocumentPanel({ title, file, previewUrl, inputId, onRemove }: FullDocumentPanelProps) {
  return (
    <section className="full-doc-panel">
      <div className="full-doc-header">
        <h3>{title}</h3>
        {file && (
          <div className="full-doc-meta">
            <span title={file.filename}>{file.filename}</span>
            <button className="delete-btn compact-btn" onClick={() => onRemove(file.id)}>Gỡ bỏ</button>
          </div>
        )}
      </div>
      {file ? (
        <iframe src={previewUrl || file.preview_url} title={file.filename} className="full-doc-frame" />
      ) : (
        <label htmlFor={inputId} className="empty-doc-panel upload-dropzone" aria-label={`Tải lên ${title} PDF`}>
          <div className="upload-icon-circle large">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <span className="upload-dropzone-text">Bấm để tải lên {title} (PDF)</span>
        </label>
      )}
    </section>
  );
}
