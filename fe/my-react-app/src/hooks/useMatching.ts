import { useState } from 'react';
import type { UploadedFile, MenuType } from '../types/dashboard';
import type { MatchingResult } from '../types/matching';
import { runMatching } from '../services/api';

interface RunMatchingDeps {
  files: UploadedFile[];
  activeMenu: MenuType;
  modelId: string;
  showNotify: (msg: string) => void;
  onComplete?: () => Promise<void> | void;
}

export interface MatchingMeta {
  elapsed_seconds?: number;
  extraction_seconds?: number;
  inference_seconds?: number;
  model_used?: string;
}

export function useMatching() {
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [matchingResults, setMatchingResults] = useState<MatchingResult[]>([]);
  const [matchingMeta, setMatchingMeta] = useState<MatchingMeta | null>(null);
  const [saveCv, setSaveCv] = useState(false);
  const [jdMode, setJdMode] = useState<'file' | 'text'>('file');
  const [jdText, setJdText] = useState('');

  const handleRunMatching = async (deps: RunMatchingDeps) => {
    const { files, activeMenu, modelId, showNotify, onComplete } = deps;
    const hasSourceFile = (file: UploadedFile): file is UploadedFile & { sourceFile: File } => Boolean(file.sourceFile);
    const cvEntries = files.filter(f => f.category === 'CV' && f.section === activeMenu);
    const jdEntries = files.filter(f => f.category === 'JD' && f.section === activeMenu);
    const cvFiles = cvEntries.filter(hasSourceFile);
    const jdEntry = jdEntries.find(hasSourceFile);
    const cleanJdText = jdText.trim();

    if (cvFiles.length === 0) {
      showNotify("Vui lòng tải lên ít nhất 1 CV PDF trước khi chạy matching.");
      return;
    }
    if (jdMode === 'text' && !cleanJdText) {
      showNotify("Vui lòng nhập nội dung JD.");
      return;
    }
    if (jdMode === 'file' && !jdEntry) {
      showNotify("Vui lòng tải lên JD PDF, hoặc chuyển sang nhập JD dạng Text.");
      return;
    }

    setMatchingLoading(true);
    setMatchingResults([]);
    setMatchingMeta(null);

    try {
      showNotify(saveCv ? "Đang lưu CV và chạy AI matching..." : "Đang chạy AI matching...");
      const { ok, result } = await runMatching({
        cvFiles: cvFiles.map(file => ({ file: file.sourceFile, filename: file.filename })),
        jdFile: jdMode === 'file' && jdEntry ? { file: jdEntry.sourceFile, filename: jdEntry.filename } : null,
        jdText: jdMode === 'text' ? cleanJdText : undefined,
        saveCv,
        modelId: modelId || undefined,
      });
      if (!ok || result.status !== 'success') {
        throw new Error(result.detail || "Không thể chạy CV-JD Matching");
      }
      const matching = result.data?.matching;
      setMatchingResults(matching?.results ?? []);
      setMatchingMeta({
        elapsed_seconds: matching?.elapsed_seconds,
        extraction_seconds: matching?.extraction_seconds,
        inference_seconds: matching?.inference_seconds,
        model_used: matching?.model_used,
      });
      showNotify("Chạy Matching hoàn tất!");
      await onComplete?.();
    } catch (error) {
      showNotify(error instanceof Error ? error.message : "Lỗi khi chạy CV-JD Matching");
    } finally {
      setMatchingLoading(false);
    }
  };

  return {
    matchingLoading,
    matchingResults,
    setMatchingResults,
    matchingMeta,
    saveCv,
    setSaveCv,
    jdMode,
    setJdMode,
    jdText,
    setJdText,
    handleRunMatching,
  };
}
