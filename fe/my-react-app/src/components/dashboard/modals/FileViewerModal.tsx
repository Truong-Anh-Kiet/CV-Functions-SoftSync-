import type { UploadedFile } from '../../../types/dashboard';

interface FileViewerModalProps {
  file: UploadedFile | null;
  onClose: () => void;
}

export default function FileViewerModal({ file, onClose }: FileViewerModalProps) {
  if (!file) return null;
  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header"><h3>Đang xem: {file.filename}</h3><button className="close-modal" onClick={onClose}>&times;</button></div>
        <div className="modal-body">{file.filename.toLowerCase().endsWith('.pdf') ? (<iframe src={file.preview_url} title="PDF Viewer" width="100%" height="100%" />) : (<div className="no-preview">Trình duyệt không hỗ trợ xem trực tiếp định dạng này.</div>)}</div>
      </div>
    </div>
  );
}
