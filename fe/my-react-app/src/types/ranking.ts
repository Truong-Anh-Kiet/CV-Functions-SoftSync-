import type { MatchingResult } from './matching';

export interface RankingResultItem extends MatchingResult {
  cv_id?: number | null;
  cv_source?: 'uploaded' | 'saved' | null;
  cv_preview_url?: string | null;
  cv_cloudinary_url?: string | null;
}

export interface RankingApiResponse {
  status?: string;
  detail?: string;
  data?: {
    jd_file?: string;
    results?: RankingResultItem[];
    elapsed_seconds?: number;
    model_used?: string | null;
  };
}

export interface SavedCvOption {
  id: number;
  filename: string;
  preview_url?: string | null;
  cloudinary_url?: string | null;
  created_at?: string | null;
}
