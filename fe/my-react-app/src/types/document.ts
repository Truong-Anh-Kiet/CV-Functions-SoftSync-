export interface SavedDocument {
  id: number;
  filename: string;
  category: 'CV' | 'JD';
  url?: string | null;
  cloudinary_url?: string | null;
  preview_url?: string | null;
  created_at?: string | null;
}
