export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
export const DEFAULT_USD_VND_RATE = 26236.346503;

export interface CvContentResponse {
  status: string;
  data?: { text: string };
  detail?: string;
}

export interface CvStructuredResponse {
  status: string;
  data?: {
    text: string;
    structured: Record<string, unknown>;
    model_used?: string;
  };
  detail?: string;
}

export interface ExchangeRateResponse {
  status: string;
  data?: {
    rate: number;
  };
  detail?: string;
}

export const fetchCvContent = async (documentId: number): Promise<{ ok: boolean; text: string }> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/matching/search-cvs/${documentId}/content`);
    const result: CvContentResponse = await response.json();
    if (!response.ok || result.status !== 'success' || !result.data) {
      return { ok: false, text: '' };
    }
    return { ok: true, text: result.data.text };
  } catch {
    return { ok: false, text: '' };
  }
};

export const fetchCvStructured = async (documentId: number): Promise<{ ok: boolean; text: string; structured: Record<string, unknown> }> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/matching/search-cvs/${documentId}/structured`);
    const result: CvStructuredResponse = await response.json();
    if (!response.ok || result.status !== 'success' || !result.data) {
      return { ok: false, text: '', structured: {} };
    }
    return {
      ok: true,
      text: result.data.text || '',
      structured: result.data.structured || {},
    };
  } catch {
    return { ok: false, text: '', structured: {} };
  }
};

export const fetchUsdVndRate = async (): Promise<number> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/exchange-rate/usd-vnd`);
    const result: ExchangeRateResponse = await response.json();
    const rate = result.data?.rate;
    if (!response.ok || result.status !== 'success' || typeof rate !== 'number' || !Number.isFinite(rate) || rate <= 0) {
      return DEFAULT_USD_VND_RATE;
    }
    return rate;
  } catch {
    return DEFAULT_USD_VND_RATE;
  }
};
