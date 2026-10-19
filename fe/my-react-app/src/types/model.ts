export interface ModelOption {
  id: string;
  display_name: string;
  sbert_id: string;
}

export interface ModelsApiResponse {
  status?: string;
  data?: {
    default?: string;
    models?: ModelOption[];
  };
}
