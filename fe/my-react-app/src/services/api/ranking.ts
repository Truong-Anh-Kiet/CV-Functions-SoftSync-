import { API_BASE_URL } from './client';
import type { RankingApiResponse } from '../../types/ranking';

export interface RunRankingInput {
  jdMode: 'text' | 'file';
  jdText?: string;
  jdFile?: File | null;
  uploadedCvs: File[];
  savedCvIds: number[];
  modelId?: string;
}

export const runRanking = async (
  input: RunRankingInput,
): Promise<{ ok: boolean; result: RankingApiResponse }> => {
  const fd = new FormData();
  if (input.jdMode === 'text' && input.jdText !== undefined) {
    fd.append('jd_text', input.jdText);
  } else if (input.jdMode === 'file' && input.jdFile) {
    fd.append('jd_file', input.jdFile, input.jdFile.name);
  }
  input.uploadedCvs.forEach((file) => {
    fd.append('cv_files', file, file.name);
  });
  if (input.savedCvIds.length) {
    fd.append('saved_cv_ids', input.savedCvIds.join(','));
  }
  if (input.modelId) {
    fd.append('model_id', input.modelId);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/ranking/rank`, {
    method: 'POST',
    body: fd,
  });
  const result: RankingApiResponse = await response.json();
  return { ok: response.ok, result };
};
