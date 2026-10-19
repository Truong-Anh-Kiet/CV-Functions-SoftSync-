export type MenuType = 'CV Storage' | 'CV-JD Matching' | 'CV Ranking' | 'CV Comparison' | 'CV Searching';

export type EvidenceValue = string | string[] | null | undefined;

export interface UploadedFile {
  id: string;
  filename: string;
  preview_url: string;
  isSaved: boolean;
  category: 'CV' | 'JD';
  section: MenuType;
  sourceFile?: File;
}
