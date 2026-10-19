import type { UploadedFile, MenuType } from '../../../types/dashboard';
import FileCard from '../storage/FileCard';
import SavedCvPanel from '../storage/SavedCvPanel';

interface CvStorageSectionProps {
  files: UploadedFile[];
  loading: boolean;
  activeMenu: MenuType;
  savedCvsCount: number;
  onPreviewUpload: (e: React.ChangeEvent<HTMLInputElement>, category: 'CV' | 'JD') => void;
  onPreview: (file: UploadedFile) => void;
  onConfirmSave: (filename: string, category: string) => void;
  onRemove: (id: string) => void;
  onToggleSavedCvs: () => void;
}

export default function CvStorageSection({
  files,
  loading,
  activeMenu,
  savedCvsCount,
  onPreviewUpload,
  onPreview,
  onConfirmSave,
  onRemove,
  onToggleSavedCvs,
}: CvStorageSectionProps) {
  return (
    <div className="storage-layout">
      <div className="storage-section">
        <div className="upload-zone">
          <input type="file" multiple onChange={(e) => onPreviewUpload(e, 'CV')} id="cv-up" hidden />
          <label htmlFor="cv-up" className="premium-upload-label">
            <div className="upload-icon-circle"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg></div>
            <h3>{loading ? 'Đang tải CV...' : 'Tải lên CV (Storage)'}</h3>
          </label>
        </div>
        <div className="file-grid">
          {files.filter(f => f.category === 'CV' && f.section === 'CV Storage').map(file => (
            <FileCard
              key={file.id}
              file={file}
              activeMenu={activeMenu}
              onPreview={onPreview}
              onConfirmSave={onConfirmSave}
              onRemove={onRemove}
            />
          ))}
        </div>
      </div>
      <SavedCvPanel count={savedCvsCount} onToggle={onToggleSavedCvs} />
    </div>
  );
}
