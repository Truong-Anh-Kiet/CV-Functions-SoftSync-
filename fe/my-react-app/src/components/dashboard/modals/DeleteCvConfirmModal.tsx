import type { SavedDocument } from '../../../types/document';
import { IconTrash } from '../icons';

interface DeleteCvConfirmModalProps {
  target: SavedDocument | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function DeleteCvConfirmModal({ target, onCancel, onConfirm }: DeleteCvConfirmModalProps) {
  if (!target) return null;
  return (
    <div className="confirm-modal-overlay" onClick={onCancel}>
      <section className="confirm-modal" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-icon danger"><IconTrash /></div>
        <div className="confirm-copy"><h3>Xóa CV khỏi kho lưu trữ?</h3><p>CV <strong>{target.filename}</strong> sẽ bị xóa khỏi danh sách đã lưu.</p></div>
        <div className="confirm-actions">
          <button className="confirm-cancel-btn" onClick={onCancel}>Hủy</button>
          <button className="confirm-danger-btn" onClick={onConfirm}>Xóa CV</button>
        </div>
      </section>
    </div>
  );
}
