import { API_BASE_URL } from './client';
import type { MatchingApiResponse } from '../../types/matching';
import type { ModelsApiResponse } from '../../types/model';
import type { SearchApiResponse, ReindexApiResponse, JdAnalysisSummary } from '../../types/search';

export const fetchModels = async (): Promise<{ ok: boolean; result: ModelsApiResponse }> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/models`);
  if (!response.ok) return { ok: false, result: {} };
  const result: ModelsApiResponse = await response.json();
  return { ok: true, result };
};

export interface RunMatchingInput {
  cvFiles: { file: File; filename: string }[];
  jdFile?: { file: File; filename: string } | null;
  jdText?: string;
  saveCv: boolean;
  modelId?: string;
}

export const runMatching = async (
  input: RunMatchingInput,
): Promise<{ ok: boolean; result: MatchingApiResponse }> => {
  const formData = new FormData();
  input.cvFiles.forEach(({ file, filename }) => {
    formData.append('cv_files', file, filename);
  });
  // JD as pasted text or as a PDF (exactly one — backend validates).
  const jdText = input.jdText?.trim();
  if (jdText) {
    formData.append('jd_text', jdText);
  } else if (input.jdFile) {
    formData.append('jd_file', input.jdFile.file, input.jdFile.filename);
  }
  formData.append('save_cv', input.saveCv ? 'true' : 'false');
  if (input.modelId) {
    formData.append('model_id', input.modelId);
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/cv-jd`, {
    method: 'POST',
    body: formData,
  });
  const result: MatchingApiResponse = await response.json();
  return { ok: response.ok, result };
};

export interface ReindexAllInput {
  modelId?: string;
}

export const reindexAllCvs = async (
  input: ReindexAllInput,
): Promise<{ ok: boolean; result: ReindexApiResponse }> => {
  const formData = new FormData();
  if (input.modelId) formData.append('model_id', input.modelId);
  formData.append('force', 'false');
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/search-cvs/reindex-all`, {
    method: 'POST',
    body: formData,
  });
  const result: ReindexApiResponse = await response.json();
  return { ok: response.ok, result };
};

export interface SearchCvsInput {
  mode: 'text' | 'file';
  jdText?: string;
  jdFile?: File | null;
  topK: number;
  minScore: number;
  autoIndexMissing: boolean;
  rerank: boolean;
  rerankTopN: number;
  modelId?: string;
}

export const searchCvs = async (
  input: SearchCvsInput,
): Promise<{ ok: boolean; result: SearchApiResponse }> => {
  const formData = new FormData();
  if (input.mode === 'text' && input.jdText !== undefined) {
    formData.append('jd_text', input.jdText);
  } else if (input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  }
  formData.append('top_k', String(input.topK));
  formData.append('min_score', String(input.minScore));
  formData.append('auto_index_missing', input.autoIndexMissing ? 'true' : 'false');
  formData.append('rerank', input.rerank ? 'true' : 'false');
  formData.append('rerank_top_n', String(input.rerankTopN));
  if (input.modelId) formData.append('model_id', input.modelId);
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/search-cvs/from-jd`, {
    method: 'POST',
    body: formData,
  });
  const result: SearchApiResponse = await response.json();
  return { ok: response.ok, result };
};

export interface AnalyzeJdInput {
  mode: 'text' | 'file';
  jdText?: string;
  jdFile?: File | null;
}

export interface AnalyzeJdApiResponse {
  status?: string;
  detail?: string;
  data?: JdAnalysisSummary;
}

export const analyzeJd = async (
  input: AnalyzeJdInput,
): Promise<{ ok: boolean; result: AnalyzeJdApiResponse }> => {
  const formData = new FormData();
  if (input.mode === 'text' && input.jdText !== undefined) {
    formData.append('jd_text', input.jdText);
  } else if (input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  }
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/jd-analysis`, {
    method: 'POST',
    body: formData,
  });
  const result: AnalyzeJdApiResponse = await response.json();
  return { ok: response.ok, result };
};

export interface CvHeatmapInput {
  jdText?: string;
  jdFile?: File | null;
  cvDocumentId?: number;
  cvFile?: File | null;
  cvText?: string;
  cvFilename?: string;
  modelId?: string;
}

export const getCvHeatmap = async (
  input: CvHeatmapInput,
): Promise<{ ok: boolean; result: MatchingApiResponse }> => {
  const formData = new FormData();
  if (input.jdText) formData.append('jd_text', input.jdText);
  if (input.jdFile) formData.append('jd_file', input.jdFile, input.jdFile.name);
  if (input.cvDocumentId !== undefined) formData.append('cv_document_id', String(input.cvDocumentId));
  if (input.cvFile) formData.append('cv_file', input.cvFile, input.cvFile.name);
  if (input.cvText) formData.append('cv_text', input.cvText);
  if (input.cvFilename) formData.append('cv_filename', input.cvFilename);
  if (input.modelId) formData.append('model_id', input.modelId);
  const response = await fetch(`${API_BASE_URL}/api/v1/matching/cv-detail/heatmap`, {
    method: 'POST',
    body: formData,
  });
  const result: MatchingApiResponse = await response.json();
  return { ok: response.ok, result };
};
