import { useCallback, useState } from 'react';
import type { SavedDocument } from '../types/document';
import { listSavedCvs } from '../services/api';

export function useSavedCvs(onError: (msg: string) => void) {
  const [savedCvs, setSavedCvs] = useState<SavedDocument[]>([]);
  const [savedCvsLoading, setSavedCvsLoading] = useState(false);
  const [editingCvId, setEditingCvId] = useState<number | null>(null);
  const [editingCvName, setEditingCvName] = useState('');
  const [deleteTargetCv, setDeleteTargetCv] = useState<SavedDocument | null>(null);

  const fetchSavedCvs = useCallback(async () => {
    setSavedCvsLoading(true);
    try {
      const result = await listSavedCvs();
      if (!result.ok || result.status !== 'success') {
        throw new Error(result.detail || 'Không thể tải danh sách CV đã lưu');
      }
      setSavedCvs(result.data ?? []);
    } catch (error) {
      console.error('Lỗi tải danh sách CV:', error);
      onError('Không thể tải danh sách CV đã lưu');
    } finally {
      setSavedCvsLoading(false);
    }
  }, [onError]);

  const cancelRename = useCallback(() => {
    setEditingCvId(null);
    setEditingCvName('');
  }, []);

  return {
    savedCvs,
    setSavedCvs,
    savedCvsLoading,
    fetchSavedCvs,
    editingCvId,
    setEditingCvId,
    editingCvName,
    setEditingCvName,
    cancelRename,
    deleteTargetCv,
    setDeleteTargetCv,
  };
}
