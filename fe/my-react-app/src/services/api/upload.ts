import { API_BASE_URL } from './client';
import type { SavedDocument } from '../../types/document';

export interface PreviewUploadResult {
  status: string;
  detail?: string;
  data?: {
    filename: string;
    preview_url: string;
  };
}

export const uploadPreview = async (file: File): Promise<PreviewUploadResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE_URL}/api/v1/upload/preview`, {
    method: 'POST',
    body: formData,
  });
  return response.json();
};

export interface ConfirmSaveResult {
  status: string;
  detail?: string;
  data?: SavedDocument;
}

export const confirmSave = async (filename: string, category: string): Promise<ConfirmSaveResult> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/upload/confirm-save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ filename, category }),
  });
  return response.json();
};

export interface ListSavedCvsResponse {
  status: string;
  detail?: string;
  data?: SavedDocument[];
  ok: boolean;
}

export const listSavedCvs = async (): Promise<ListSavedCvsResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/upload/cvs`);
  const result = await response.json();
  return { ...result, ok: response.ok };
};

export interface RenameSavedCvResponse {
  status: string;
  detail?: string;
  data?: SavedDocument;
  ok: boolean;
}

export const renameSavedCv = async (id: number, filename: string): Promise<RenameSavedCvResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/upload/cvs/${id}/rename`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({ filename }),
  });
  const result = await response.json();
  return { ...result, ok: response.ok };
};

export interface DeleteSavedCvResponse {
  status: string;
  detail?: string;
  ok: boolean;
}

export const deleteSavedCv = async (id: number): Promise<DeleteSavedCvResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/upload/cvs/${id}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  return { ...result, ok: response.ok };
};
