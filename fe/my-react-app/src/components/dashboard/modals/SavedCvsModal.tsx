import type { SavedDocument } from '../../../types/document';
import SavedCvList from '../storage/SavedCvList';

interface SavedCvsModalProps {
  open: boolean;
  onClose: () => void;
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

export default function SavedCvsModal({
  open,
  onClose,
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
}: SavedCvsModalProps) {
  if (!open) return null;
  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content saved-cv-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div><h3>Kho CV đã lưu</h3><span className="modal-subtitle">{savedCvs.length} CV trong kho</span></div>
          <button className="close-modal" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body saved-cv-modal-body">
          <SavedCvList
            savedCvs={savedCvs}
            savedCvsLoading={savedCvsLoading}
            editingCvId={editingCvId}
            editingCvName={editingCvName}
            onEditingNameChange={onEditingNameChange}
            onStartRename={onStartRename}
            onCancelRename={onCancelRename}
            onSaveRename={onSaveRename}
            onView={onView}
            onRequestDelete={onRequestDelete}
          />
        </div>
      </div>
    </div>
  );
}
