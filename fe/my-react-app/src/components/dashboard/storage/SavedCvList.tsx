import type { SavedDocument } from '../../../types/document';
import { formatSavedDate } from '../../../utils/format';
import { IconEye, IconEdit, IconTrash, IconCheck, IconClose } from '../icons';

interface SavedCvListProps {
  savedCvs: SavedDocument[];
  savedCvsLoading: boolean;
  editingCvId: number | null;
  editingCvName: string;
  onEditingNameChange: (name: string) => void;
  onStartRename: (document: SavedDocument) => void;
  onCancelRename: () => void;
  onSaveRename: (document: SavedDocument) => void;
  onView: (document: SavedDocument) => void;
  onRequestDelete: (document: SavedDocument) => void;
}

export default function SavedCvList({
  savedCvs,
  savedCvsLoading,
  editingCvId,
  editingCvName,
  onEditingNameChange,
  onStartRename,
  onCancelRename,
  onSaveRename,
  onView,
  onRequestDelete,
}: SavedCvListProps) {
  return (
    <div className="saved-cv-list modal-saved-cv-list">
      {savedCvsLoading ? (
        <div className="saved-cv-empty">Đang tải CV...</div>
      ) : savedCvs.length === 0 ? (
        <div className="saved-cv-empty">Chưa có CV nào được lưu.</div>
      ) : (
        savedCvs.map(document => (
          <article className="saved-cv-item" key={document.id}>
            <div className="saved-cv-file">
              {editingCvId === document.id ? (
                <input
                  className="saved-cv-rename-input"
                  value={editingCvName}
                  onChange={(event) => onEditingNameChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') onSaveRename(document);
                    if (event.key === 'Escape') onCancelRename();
                  }}
                  autoFocus
                />
              ) : (
                <>
                  <strong title={document.filename}>{document.filename}</strong>
                  <span>{formatSavedDate(document.created_at)}</span>
                </>
              )}
            </div>
            <div className="saved-cv-actions">
              {editingCvId === document.id ? (
                <>
                  <button className="icon-action success" title="Lưu tên mới" aria-label="Lưu tên mới" onClick={() => onSaveRename(document)}><IconCheck /></button>
                  <button className="icon-action" title="Hủy đổi tên" aria-label="Hủy đổi tên" onClick={onCancelRename}><IconClose /></button>
                </>
              ) : (
                <>
                  <button className="icon-action" title="Xem CV" aria-label={`Xem ${document.filename}`} onClick={() => { onCancelRename(); onView(document); }}><IconEye /></button>
                  <button className="icon-action" title="Đổi tên CV" aria-label={`Đổi tên ${document.filename}`} onClick={() => onStartRename(document)}><IconEdit /></button>
                  <button className="icon-action danger" title="Xóa CV" aria-label={`Xóa ${document.filename}`} onClick={() => onRequestDelete(document)}><IconTrash /></button>
                </>
              )}
            </div>
          </article>
        ))
      )}
    </div>
  );
}
