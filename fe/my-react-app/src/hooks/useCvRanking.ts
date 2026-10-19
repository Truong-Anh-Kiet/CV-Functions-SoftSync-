import { useCallback, useEffect, useState } from 'react';
import { listSavedCvs } from '../services/api/upload';
import { runRanking } from '../services/api/ranking';
import type { RankingResultItem, SavedCvOption } from '../types/ranking';

interface RunRankingDeps {
  modelId: string;
  showNotify: (msg: string) => void;
}

export function useCvRanking() {
  const [jdMode, setJdMode] = useState<'text' | 'file'>('text');
  const [jdText, setJdText] = useState('');
  const [jdFile, setJdFile] = useState<File | null>(null);

  const [cvSource, setCvSource] = useState<'upload' | 'saved'>('upload');
  const [uploadedCvs, setUploadedCvs] = useState<File[]>([]);
  const [selectedSavedIds, setSelectedSavedIds] = useState<Set<number>>(new Set());

  const [savedCvs, setSavedCvs] = useState<SavedCvOption[]>([]);
  const [savedCvsLoading, setSavedCvsLoading] = useState(false);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RankingResultItem[]>([]);
  const [meta, setMeta] = useState<{ elapsed_seconds?: number; model_used?: string | null; jd_file?: string } | null>(
    null,
  );

  const fetchSavedCvs = useCallback(async () => {
    setSavedCvsLoading(true);
    try {
      const res = await listSavedCvs();
      if (res.ok && Array.isArray(res.data)) {
        setSavedCvs(
          res.data.map((doc) => ({
            id: doc.id,
            filename: doc.filename,
            preview_url: doc.preview_url ?? null,
            cloudinary_url: doc.cloudinary_url ?? null,
            created_at: doc.created_at ?? null,
          })),
        );
      }
    } finally {
      setSavedCvsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSavedCvs();
  }, [fetchSavedCvs]);

  const handleJdFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setJdFile(file);
    event.target.value = '';
  };

  const handleCvFilesChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) return;
    setUploadedCvs((prev) => {
      const existing = new Set(prev.map((f) => `${f.name}_${f.size}`));
      const additions = files.filter((f) => !existing.has(`${f.name}_${f.size}`));
      return [...prev, ...additions];
    });
    event.target.value = '';
  };

  const removeUploadedCv = (index: number) => {
    setUploadedCvs((prev) => prev.filter((_, i) => i !== index));
  };

  const toggleSavedCv = (id: number) => {
    setSelectedSavedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const clearSelections = () => {
    setUploadedCvs([]);
    setSelectedSavedIds(new Set());
  };

  const clearResults = () => {
    setResults([]);
    setMeta(null);
  };

  const totalCvCount = uploadedCvs.length + selectedSavedIds.size;

  const handleRunRanking = async (deps: RunRankingDeps) => {
    const { modelId, showNotify } = deps;
    const cleanText = jdText.trim();

    if (jdMode === 'text' && !cleanText) {
      showNotify('Vui lòng nhập nội dung JD.');
      return;
    }
    if (jdMode === 'file' && !jdFile) {
      showNotify('Vui lòng chọn file JD PDF.');
      return;
    }
    if (totalCvCount === 0) {
      showNotify('Vui lòng chọn ít nhất 1 CV (upload hoặc từ Saved CVs).');
      return;
    }

    setLoading(true);
    setResults([]);
    setMeta(null);
    try {
      showNotify(`Đang xếp hạng ${totalCvCount} CV...`);
      const { ok, result } = await runRanking({
        jdMode,
        jdText: jdMode === 'text' ? cleanText : undefined,
        jdFile: jdMode === 'file' ? jdFile : null,
        uploadedCvs,
        savedCvIds: Array.from(selectedSavedIds),
        modelId: modelId || undefined,
      });

      if (!ok || result.status !== 'success' || !result.data) {
        throw new Error(result.detail || 'Không thể chạy ranking');
      }

      setResults(result.data.results ?? []);
      setMeta({
        elapsed_seconds: result.data.elapsed_seconds,
        model_used: result.data.model_used,
        jd_file: result.data.jd_file,
      });
      showNotify(`Hoàn tất ranking ${result.data.results?.length ?? 0} CV.`);
    } catch (error) {
      showNotify(error instanceof Error ? error.message : 'Lỗi khi chạy ranking');
    } finally {
      setLoading(false);
    }
  };

  return {
    jdMode, setJdMode,
    jdText, setJdText,
    jdFile, setJdFile,
    handleJdFileChange,
    cvSource, setCvSource,
    uploadedCvs, setUploadedCvs,
    handleCvFilesChange,
    removeUploadedCv,
    savedCvs, savedCvsLoading,
    selectedSavedIds,
    toggleSavedCv,
    clearSelections,
    totalCvCount,
    loading,
    results,
    meta,
    clearResults,
    handleRunRanking,
    refreshSavedCvs: fetchSavedCvs,
  };
}
