import type { MatchingResult } from '../../../types/matching';
import StructuredDataViewer from '../matching/StructuredDataViewer';

interface StructuredDataModalProps {
  open: boolean;
  onClose: () => void;
  result: MatchingResult | null;
}

export default function StructuredDataModal({ open, onClose, result }: StructuredDataModalProps) {
  if (!open || !result) return null;
  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content structured-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div><h3>Structured Data (JSON)</h3><span className="modal-subtitle">CV và JD đã được trích xuất sang dạng có cấu trúc</span></div>
          <button className="close-modal" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body structured-modal-body">
          <div className="structured-pane">
            <div className="structured-pane-head">CV</div>
            <div className="structured-content-box">
              <StructuredDataViewer data={result.cv_structured} />
            </div>
          </div>
          <div className="structured-pane">
            <div className="structured-pane-head">JD</div>
            <div className="structured-content-box">
              <StructuredDataViewer data={result.jd_structured} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
