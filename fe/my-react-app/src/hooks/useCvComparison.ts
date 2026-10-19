import { useCallback, useEffect, useMemo, useState } from 'react';
import { listSavedCvs } from '../services/api/upload';
import { runRanking } from '../services/api/ranking';
import { buildVerdict } from '../utils/cvComparison';
import type { RankingResultItem, SavedCvOption } from '../types/ranking';
import type { ComparisonVerdict } from '../types/comparison';

interface RunComparisonDeps {
  modelId: string;
  showNotify: (msg: string) => void;
}

export type CvSlot =
  | { kind: 'upload'; file: File }
  | { kind: 'saved'; id: number; filename: string; url: string | null }
  | null;

export interface CvPreviewItem {
  name: string;
  url: string | null; // PDF preview URL (object URL hoặc cloudinary/preview)
}

export function useCvComparison() {
  const [jdMode, setJdMode] = useState<'text' | 'file'>('text');
  const [jdText, setJdText] = useState('');
  const [jdFile, setJdFile] = useState<File | null>(null);

  // Hai slot CV cố định theo vị trí: [A, B].
  const [slots, setSlots] = useState<[CvSlot, CvSlot]>([null, null]);

  const [savedCvs, setSavedCvs] = useState<SavedCvOption[]>([]);
  const [savedCvsLoading, setSavedCvsLoading] = useState(false);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RankingResultItem[]>([]);
  const [verdict, setVerdict] = useState<ComparisonVerdict | null>(null);
  const [meta, setMeta] = useState<{ elapsed_seconds?: number; model_used?: string | null } | null>(null);

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

  // Object URLs cho slot upload — tạo trong memo, thu hồi ở cleanup (không setState).
  const slotUploadUrls = useMemo(
    () => slots.map((slot) => (slot && slot.kind === 'upload' ? URL.createObjectURL(slot.file) : null)),
    [slots],
  );
  useEffect(
    () => () => slotUploadUrls.forEach((url) => url && URL.revokeObjectURL(url)),
    [slotUploadUrls],
  );

  const jdFileUrl = useMemo(() => (jdFile ? URL.createObjectURL(jdFile) : null), [jdFile]);
  useEffect(() => {
    if (!jdFileUrl) return;
    return () => URL.revokeObjectURL(jdFileUrl);
  }, [jdFileUrl]);

  const handleJdFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setJdFile(file);
    event.target.value = '';
  };

  const clearJdFile = () => setJdFile(null);

  const setSlot = (index: 0 | 1, slot: CvSlot) => {
    setSlots((prev) => {
      const next: [CvSlot, CvSlot] = [prev[0], prev[1]];
      next[index] = slot;
      return next;
    });
  };

  const setSlotUpload = (index: 0 | 1, event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    if (file) setSlot(index, { kind: 'upload', file });
  };

  const setSlotSaved = (index: 0 | 1, cv: SavedCvOption) => {
    setSlot(index, {
      kind: 'saved',
      id: cv.id,
      filename: cv.filename,
      url: cv.preview_url || cv.cloudinary_url || null,
    });
  };

  const clearSlot = (index: 0 | 1) => setSlot(index, null);

  const clearSelections = () => setSlots([null, null]);

  const clearResults = () => {
    setResults([]);
    setVerdict(null);
    setMeta(null);
  };

  const totalCvCount = slots.filter(Boolean).length;

  // Preview theo đúng vị trí slot (A trước, B sau).
  const cvPreviews = useMemo<(CvPreviewItem | null)[]>(
    () =>
      slots.map((slot, index) => {
        if (!slot) return null;
        if (slot.kind === 'upload') return { name: slot.file.name, url: slotUploadUrls[index] ?? null };
        return { name: slot.filename, url: slot.url };
      }),
    [slots, slotUploadUrls],
  );

  const savedIdInOtherSlot = (index: 0 | 1): number | null => {
    const other = slots[index === 0 ? 1 : 0];
    return other && other.kind === 'saved' ? other.id : null;
  };

  const handleRunComparison = async (deps: RunComparisonDeps) => {
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
    if (totalCvCount !== 2) {
      showNotify(`Cần chọn đủ 2 CV để so sánh (hiện ${totalCvCount}).`);
      return;
    }

    const uploadedCvs = slots
      .filter((s): s is { kind: 'upload'; file: File } => s?.kind === 'upload')
      .map((s) => s.file);
    const savedCvIds = slots
      .filter((s): s is { kind: 'saved'; id: number; filename: string; url: string | null } => s?.kind === 'saved')
      .map((s) => s.id);
    const orderNames = slots
      .map((s) => (s ? (s.kind === 'upload' ? s.file.name : s.filename) : null))
      .filter((n): n is string => Boolean(n));

    setLoading(true);
    setResults([]);
    setVerdict(null);
    setMeta(null);
    try {
      showNotify('Đang so sánh 2 CV...');
      const { ok, result } = await runRanking({
        jdMode,
        jdText: jdMode === 'text' ? cleanText : undefined,
        jdFile: jdMode === 'file' ? jdFile : null,
        uploadedCvs,
        savedCvIds,
        modelId: modelId || undefined,
      });

      if (!ok || result.status !== 'success' || !result.data) {
        throw new Error(result.detail || 'Không thể chạy so sánh');
      }

      const items = result.data.results ?? [];
      setResults(items);
      // Giữ thứ tự CV theo đúng vị trí slot (A/B) để nhất quán với preview.
      setVerdict(buildVerdict(items, orderNames));
      setMeta({
        elapsed_seconds: result.data.elapsed_seconds,
        model_used: result.data.model_used,
      });
      showNotify('Hoàn tất so sánh 2 CV.');
    } catch (error) {
      showNotify(error instanceof Error ? error.message : 'Lỗi khi so sánh CV');
    } finally {
      setLoading(false);
    }
  };

  return {
    jdMode, setJdMode,
    jdText, setJdText,
    jdFile, jdFileUrl,
    handleJdFileChange,
    clearJdFile,
    slots,
    setSlotUpload,
    setSlotSaved,
    clearSlot,
    savedIdInOtherSlot,
    savedCvs, savedCvsLoading,
    clearSelections,
    totalCvCount,
    cvPreviews,
    loading,
    results,
    verdict,
    meta,
    clearResults,
    handleRunComparison,
    refreshSavedCvs: fetchSavedCvs,
  };
}
