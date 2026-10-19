import { useState } from 'react';
import type { UploadedFile, MenuType } from '../types/dashboard';
import { uploadPreview } from '../services/api';

interface PreviewUploadOptions {
  activeMenu: MenuType;
  onSuccess?: () => void;
  onError: (msg: string) => void;
}

export function useUploadedFiles() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(false);

  const handlePreviewUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
    category: 'CV' | 'JD',
    options: PreviewUploadOptions,
  ) => {
    const { activeMenu, onSuccess, onError } = options;
    const selectedFiles = e.target.files;
    if (!selectedFiles) return;

    setLoading(true);
    const isSingleSlot = category === 'JD' || (activeMenu === 'CV-JD Matching' && category === 'CV');
    const filesToUpload = isSingleSlot
      ? Array.from(selectedFiles).slice(0, 1)
      : Array.from(selectedFiles);

    for (const currentFile of filesToUpload) {
      try {
        const result = await uploadPreview(currentFile);
        if (result.status === 'success' && result.data) {
          const newFile: UploadedFile = {
            id: Math.random().toString(36).substr(2, 9),
            filename: result.data.filename,
            preview_url: result.data.preview_url,
            isSaved: false,
            category: category,
            section: activeMenu,
            sourceFile: currentFile,
          };
          setFiles(prev => {
            if (activeMenu === 'CV-JD Matching' && (category === 'CV' || category === 'JD')) {
              return [...prev.filter(f => !(f.category === category && f.section === activeMenu)), newFile];
            }
            if (category === 'JD' && activeMenu === 'CV Ranking') {
              return [...prev.filter(f => !(f.category === 'JD' && f.section === activeMenu)), newFile];
            }
            return [...prev, newFile];
          });
          onSuccess?.();
        }
      } catch {
        onError("Lỗi kết nối server khi tải preview!");
      }
    }
    setLoading(false);
    e.target.value = '';
  };

  return { files, setFiles, loading, handlePreviewUpload };
}
