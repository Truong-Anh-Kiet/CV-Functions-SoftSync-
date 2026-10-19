import { API_BASE_URL } from './client';

export interface CareerVietProfile {
  id: string;
  title: string;
  candidate_name: string;
  resume_id?: string | null;
  education?: string | null;
  level?: string | null;
  experience?: string | null;
  salary?: string | null;
  location?: string | null;
  last_access?: string | null;
  source: string;
  source_url?: string | null;
  profile_url?: string | null;
  attachment_url?: string | null;
  summary?: string | null;
  tags: string[];
  raw_text?: string | null;
}

export interface CareerVietSearchResponse {
  status?: string;
  detail?: string;
  data?: {
    source: string;
    query?: string | null;
    page: number;
    page_size: number;
    total: number;
    items: CareerVietProfile[];
    min_score?: number;
    skipped_cvs?: {
      id: string | number;
      filename: string;
      reason: string;
    }[];
    rerank?: {
      results?: import('../../types/matching').MatchingResult[];
      elapsed_seconds?: number;
      model_used?: string;
    } | null;
  };
}

export interface CareerVietProfileResponse {
  status?: string;
  detail?: string;
  data?: CareerVietProfile;
}

export type VietnamWorksProfile = CareerVietProfile;
export type VietnamWorksSearchResponse = CareerVietSearchResponse;
export type VietnamWorksProfileResponse = CareerVietProfileResponse;
export type AcademicProfile = CareerVietProfile;
export type AcademicSearchResponse = CareerVietSearchResponse;
export type AcademicProfileResponse = CareerVietProfileResponse;

export interface SearchCareerVietProfilesInput {
  query?: string;
  page?: number;
  pageSize: number;
}

export const searchCareerVietProfiles = async (
  input: SearchCareerVietProfilesInput,
): Promise<{ ok: boolean; result: CareerVietSearchResponse }> => {
  const params = new URLSearchParams({
    page: String(input.page ?? 1),
    page_size: String(input.pageSize),
  });
  const query = input.query?.trim();
  if (query) params.set('query', query);

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/careerviet/profiles?${params.toString()}`);
  const result: CareerVietSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export interface SearchCareerVietProfilesByJdInput {
  jdText?: string;
  jdFile?: File | null;
  page?: number;
  pageSize: number;
}

export const searchCareerVietProfilesByJd = async (
  input: SearchCareerVietProfilesByJdInput,
): Promise<{ ok: boolean; result: CareerVietSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  if (input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/careerviet/profiles/search-jd`, {
    method: 'POST',
    body: formData,
  });
  const result: CareerVietSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export interface SearchCareerVietProfilesWithMatchingInput {
  mode: 'text' | 'file';
  query?: string;
  jdText?: string;
  jdFile?: File | null;
  page?: number;
  pageSize: number;
  minScore: number;
  rerank: boolean;
  rerankTopN: number;
  modelId?: string;
}

export const searchCareerVietProfilesWithMatching = async (
  input: SearchCareerVietProfilesWithMatchingInput,
): Promise<{ ok: boolean; result: CareerVietSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  formData.append('min_score', String(input.minScore));
  formData.append('rerank', input.rerank ? 'true' : 'false');
  formData.append('rerank_top_n', String(input.rerankTopN));
  if (input.modelId) formData.append('model_id', input.modelId);

  const query = input.query?.trim();
  if (query) formData.append('query', query);
  if (input.mode === 'file' && input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/careerviet/profiles/search-match`, {
    method: 'POST',
    body: formData,
  });
  const result: CareerVietSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export const getCareerVietProfile = async (
  profileId: string,
  profileUrl?: string | null,
  salary?: string | null,
): Promise<{ ok: boolean; result: CareerVietProfileResponse }> => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);
  if (salary) params.set('salary', salary);

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(
    `${API_BASE_URL}/api/v1/web-search/careerviet/profiles/${encodeURIComponent(profileId)}${suffix}`,
  );
  const result: CareerVietProfileResponse = await response.json();
  return { ok: response.ok, result };
};

export const careerVietProfileFileUrl = (profileId: string, profileUrl?: string | null, salary?: string | null) => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);
  if (salary) params.set('salary', salary);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return `${API_BASE_URL}/api/v1/web-search/careerviet/profiles/${encodeURIComponent(profileId)}/file${suffix}`;
};

export type SearchVietnamWorksProfilesInput = SearchCareerVietProfilesInput;

export const searchVietnamWorksProfiles = async (
  input: SearchVietnamWorksProfilesInput,
): Promise<{ ok: boolean; result: VietnamWorksSearchResponse }> => {
  const params = new URLSearchParams({
    page: String(input.page ?? 1),
    page_size: String(input.pageSize),
  });
  const query = input.query?.trim();
  if (query) params.set('query', query);

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/vietnamworks/profiles?${params.toString()}`);
  const result: VietnamWorksSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export type SearchVietnamWorksProfilesByJdInput = SearchCareerVietProfilesByJdInput;

export const searchVietnamWorksProfilesByJd = async (
  input: SearchVietnamWorksProfilesByJdInput,
): Promise<{ ok: boolean; result: VietnamWorksSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  if (input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/vietnamworks/profiles/search-jd`, {
    method: 'POST',
    body: formData,
  });
  const result: VietnamWorksSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export type SearchVietnamWorksProfilesWithMatchingInput = SearchCareerVietProfilesWithMatchingInput;

export const searchVietnamWorksProfilesWithMatching = async (
  input: SearchVietnamWorksProfilesWithMatchingInput,
): Promise<{ ok: boolean; result: VietnamWorksSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  formData.append('min_score', String(input.minScore));
  formData.append('rerank', input.rerank ? 'true' : 'false');
  formData.append('rerank_top_n', String(input.rerankTopN));
  if (input.modelId) formData.append('model_id', input.modelId);

  const query = input.query?.trim();
  if (query) formData.append('query', query);
  if (input.mode === 'file' && input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/vietnamworks/profiles/search-match`, {
    method: 'POST',
    body: formData,
  });
  const result: VietnamWorksSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export const getVietnamWorksProfile = async (
  profileId: string,
  profileUrl?: string | null,
): Promise<{ ok: boolean; result: VietnamWorksProfileResponse }> => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(
    `${API_BASE_URL}/api/v1/web-search/vietnamworks/profiles/${encodeURIComponent(profileId)}${suffix}`,
  );
  const result: VietnamWorksProfileResponse = await response.json();
  return { ok: response.ok, result };
};

export const vietnamWorksProfileFileUrl = (profileId: string, profileUrl?: string | null) => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return `${API_BASE_URL}/api/v1/web-search/vietnamworks/profiles/${encodeURIComponent(profileId)}/file${suffix}`;
};

export type SearchAcademicProfilesInput = SearchCareerVietProfilesInput;

export const searchAcademicProfiles = async (
  input: SearchAcademicProfilesInput,
): Promise<{ ok: boolean; result: AcademicSearchResponse }> => {
  const params = new URLSearchParams({
    page: String(input.page ?? 1),
    page_size: String(input.pageSize),
  });
  const query = input.query?.trim();
  if (query) params.set('query', query);

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/academic/profiles?${params.toString()}`);
  const result: AcademicSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export type SearchAcademicProfilesByJdInput = SearchCareerVietProfilesByJdInput;

export const searchAcademicProfilesByJd = async (
  input: SearchAcademicProfilesByJdInput,
): Promise<{ ok: boolean; result: AcademicSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  if (input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/academic/profiles/search-jd`, {
    method: 'POST',
    body: formData,
  });
  const result: AcademicSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export type SearchAcademicProfilesWithMatchingInput = SearchCareerVietProfilesWithMatchingInput;

export const searchAcademicProfilesWithMatching = async (
  input: SearchAcademicProfilesWithMatchingInput,
): Promise<{ ok: boolean; result: AcademicSearchResponse }> => {
  const formData = new FormData();
  formData.append('page', String(input.page ?? 1));
  formData.append('page_size', String(input.pageSize));
  formData.append('min_score', String(input.minScore));
  formData.append('rerank', input.rerank ? 'true' : 'false');
  formData.append('rerank_top_n', String(input.rerankTopN));
  if (input.modelId) formData.append('model_id', input.modelId);

  const query = input.query?.trim();
  if (query) formData.append('query', query);
  if (input.mode === 'file' && input.jdFile) {
    formData.append('jd_file', input.jdFile, input.jdFile.name);
  } else if (input.jdText?.trim()) {
    formData.append('jd_text', input.jdText.trim());
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/web-search/academic/profiles/search-match`, {
    method: 'POST',
    body: formData,
  });
  const result: AcademicSearchResponse = await response.json();
  return { ok: response.ok, result };
};

export const getAcademicProfile = async (
  profileId: string,
  profileUrl?: string | null,
): Promise<{ ok: boolean; result: AcademicProfileResponse }> => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(
    `${API_BASE_URL}/api/v1/web-search/academic/profiles/${encodeURIComponent(profileId)}${suffix}`,
  );
  const result: AcademicProfileResponse = await response.json();
  return { ok: response.ok, result };
};

export const academicProfileFileUrl = (profileId: string, profileUrl?: string | null) => {
  const params = new URLSearchParams();
  if (profileUrl) params.set('profile_url', profileUrl);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return `${API_BASE_URL}/api/v1/web-search/academic/profiles/${encodeURIComponent(profileId)}/file${suffix}`;
};
