import type { EvidenceValue } from './dashboard';
import type { SavedDocument } from './document';

export interface ViewMatch {
  cv_view: string;
  jd_view: string;
  cv_label: string;
  jd_label: string;
  similarity: number;
  status: 'strong_match' | 'partial_match' | 'mismatch' | 'missing';
  color: 'green' | 'orange' | 'red';
  cv_evidence: EvidenceValue;
  jd_evidence: EvidenceValue;
  reason: string;
}

export interface MatchingResult {
  rank: number;
  cv_file: string;
  source_cv_file?: string | null;
  document_id?: number | string | null;
  profile_id?: number | string | null;
  score: number;
  confidence: number;
  match: boolean;
  label: string;
  cv_view_coverage: string;
  jd_view_coverage: string;
  view_matches?: ViewMatch[];
  alignment_matrix_raw?: number[][];
  alignment_matrix_masked?: number[][];
  heatmap_labels?: {
    cv: string[];
    jd: string[];
  };
  cv_structured?: any;
  jd_structured?: any;
  highlighted_cv_url?: string | null;
  highlighted_jd_url?: string | null;
}

export interface MatchingApiResponse {
  status?: string;
  detail?: string;
  data?: {
    documents?: {
      cvs?: SavedDocument[];
      jd?: SavedDocument | null;
    };
    matching?: {
      results?: MatchingResult[];
      elapsed_seconds?: number;
      extraction_seconds?: number;
      inference_seconds?: number;
      jd_file?: string;
      model_used?: string;
    };
  };
}
