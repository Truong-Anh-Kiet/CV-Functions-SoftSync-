import type { MatchingResult } from './matching';

export interface JdAnalysisSummary {
  job_title: string;
  job_category: string;
  required_skills: string[];
  preferred_skills: string[];
  required_experience_years?: number | null;
  salary_text?: string | null;
  work_location?: string | null;
  work_mode?: 'onsite' | 'hybrid' | 'remote' | 'unknown' | null;
  seniority_level?: string | null;
  alternative_job_titles?: string[];
  confidence?: number;
}

export interface CandidateScoreBreakdown {
  job_title_match_score: number;
  skill_match_score: number;
  experience_match_score: number;
  location_match_score: number;
  cv_recency_score: number;
}

export interface SearchCvResult {
  id: number | string;
  filename: string;
  category: 'CV';
  cloudinary_url?: string | null;
  preview_url?: string | null;
  created_at?: string | null;
  search_score: number;
  embedding_model_id?: string;
  sbert_id?: string;
  embedding_dimension?: number;
  indexed_at?: string | null;
  text_length?: number;
  // AI matching fields (present when reranking is enabled)
  score?: number;
  confidence?: number;
  match?: boolean;
  label?: string;
  similarity_score?: number;
  candidate_id?: string;
  candidate_name?: string;
  current_job_title?: string | null;
  desired_job_title?: string | null;
  experience_years?: number | null;
  location?: string | null;
  salary?: string | null;
  skills?: string[];
  matched_required_skills?: string[];
  missing_required_skills?: string[];
  last_updated_date?: string | null;
  total_score?: number;
  score_breakdown?: CandidateScoreBreakdown;
  recommendation_reason?: string;
  result_bucket?: 'primary' | 'near';
  result_bucket_label?: string;
}

export interface SearchFailure {
  id: number | string;
  filename: string;
  reason: string;
}

export interface SearchApiResponse {
  status?: string;
  detail?: string;
  data?: {
    success?: boolean;
    jd_analysis?: JdAnalysisSummary;
    total_candidates?: number;
    total_cvs: number;
    search_mode?: string;
    embedding_model_id?: string;
    sbert_id?: string;
    embedding_dimension?: number;
    indexed_cvs?: number;
    indexed_missing?: number;
    skipped_cvs?: SearchFailure[];
    returned: number;
    top_k: number;
    min_score: number;
    auto_index_missing?: boolean;
    ranking_weights?: Record<string, number>;
    score_breakdown_labels?: Record<string, string>;
    usd_vnd_rate?: number;
    filtered_out?: number;
    near_match_count?: number;
    used_near_matches?: boolean;
    results?: SearchCvResult[];
    candidates?: SearchCvResult[];
    rerank?: {
      results?: MatchingResult[];
      elapsed_seconds?: number;
      model_used?: string;
    } | null;
  };
}

export interface ReindexApiResponse {
  status?: string;
  detail?: string;
  data?: {
    total_cvs: number;
    successful: number;
    failed: number;
    failures?: SearchFailure[];
  };
}
