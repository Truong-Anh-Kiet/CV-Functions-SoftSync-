import type { UploadedFile, MenuType } from '../../../types/dashboard';

interface FileCardProps {
  file: UploadedFile;
  activeMenu: MenuType;
  onPreview: (file: UploadedFile) => void;
  onConfirmSave: (filename: string, category: string) => void;
  onRemove: (id: string) => void;
}

export default function FileCard({ file, activeMenu, onPreview, onConfirmSave, onRemove }: FileCardProps) {
  return (
    <div className="file-card">
      <div className="file-preview-box" onClick={() => onPreview(file)}>
        {file.filename.toLowerCase().endsWith('.pdf') ? (<iframe src={file.preview_url} title={file.filename} className="mini-preview" />) : (<div className="doc-placeholder">DOC / DOCX FILE</div>)}
        <div className="preview-overlay">Phóng to xem nội dung</div>
      </div>
      <div className="file-info">
        <p title={file.filename}>{file.filename}</p>
        {activeMenu === 'CV Storage' ? (
          !file.isSaved ? (<button className="save-btn" onClick={() => onConfirmSave(file.filename, file.category)}>Lưu vào hệ thống</button>) : (<span className="saved-badge">✓ Đã lưu Database</span>)
        ) : (
          <div className="file-actions-row">{file.isSaved && <span className="saved-badge">✓ Đã lưu DB</span>}<button className="delete-btn" onClick={() => onRemove(file.id)}>Gỡ bỏ file</button></div>
        )}
      </div>
    </div>
  );
}
