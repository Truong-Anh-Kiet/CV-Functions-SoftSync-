export const CV_VIEW_KEYS = [
  'skills', 'education', 'year_experience', 'experience', 'responsibilities',
  'projects', 'publications', 'achievement', 'certification', 'employment_history',
] as const;

export const JD_VIEW_KEYS = [
  'skills', 'education', 'year_experience_requirement', 'experience_requirement', 'responsibilities',
] as const;

export const VIEW_LABEL_MAP: Record<string, string> = {
  skills: 'Skills',
  education: 'Education',
  year_experience: 'Year Experience',
  experience: 'Experience',
  responsibilities: 'Responsibilities',
  projects: 'Projects',
  publications: 'Publications',
  achievement: 'Achievement',
  certification: 'Certification',
  employment_history: 'Employment History',
  year_experience_requirement: 'Year Experience Req.',
  experience_requirement: 'Experience Req.',
};
