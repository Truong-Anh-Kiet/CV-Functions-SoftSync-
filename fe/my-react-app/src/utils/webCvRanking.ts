import type { AcademicProfile, CareerVietProfile, VietnamWorksProfile } from '../services/api/webSearch';
import type { JdAnalysisSummary, SearchCvResult } from '../types/search';

type WebProfile = AcademicProfile | CareerVietProfile | VietnamWorksProfile;
const DEFAULT_USD_VND_RATE = 26236.346503;

const WEB_RANKING_BASE_WEIGHTS = {
  job_title_match_score: 40,
  skill_match_score: 20,
  experience_match_score: 20,
  location_match_score: 10,
  cv_recency_score: 10,
} as const;

const TITLE_SYNONYMS: Record<string, string[]> = {
  'backend developer': ['backend developer', 'java developer', 'backend engineer', 'software engineer backend', 'java backend developer'],
  'frontend developer': ['frontend developer', 'react developer', 'reactjs developer', 'web frontend developer', 'frontend engineer'],
  'qa engineer': ['qa engineer', 'test engineer', 'quality assurance engineer', 'automation tester', 'software tester'],
  'data analyst': ['data analyst', 'business analyst', 'bi analyst'],
  'big data engineer': ['big data engineer', 'data engineer', 'big data developer', 'data platform engineer', 'data pipeline engineer'],
  'data security specialist': [
    'senior data security specialist',
    'data security specialist',
    'information security specialist',
    'cyber security specialist',
    'security engineer',
    'cloud security engineer',
    'security analyst',
  ],
  'ai engineer': ['ai engineer', 'ml engineer', 'machine learning engineer', 'nlp engineer'],
  'full-stack developer': ['full-stack developer', 'full stack developer', 'software engineer full stack'],
};

const SKILL_SYNONYMS: Record<string, string[]> = {
  'node.js': ['node.js', 'nodejs', 'node'],
  react: ['react', 'reactjs', 'react.js'],
  'spring boot': ['spring boot', 'springboot'],
  postgresql: ['postgresql', 'postgres', 'postgre'],
  'rest api': ['rest api', 'restful api', 'api'],
  '.net': ['.net', 'dotnet', 'asp.net', 'asp net'],
  'c#': ['c#', 'c sharp'],
  'c++': ['c++', 'cpp'],
  unity: ['unity', 'unity engine'],
  oop: ['oop', 'oop principles', 'object oriented programming', 'object-oriented programming'],
  mysql: ['mysql', 'my sql'],
  'sql server': ['sql server', 'mssql', 'ms sql', 'microsoft sql server'],
  javascript: ['javascript', 'js'],
  typescript: ['typescript', 'ts'],
  python: ['python', 'py'],
  java: ['java'],
  docker: ['docker'],
  kubernetes: ['kubernetes', 'k8s'],
};

const LOCATION_SYNONYMS: Record<string, string[]> = {
  'ho chi minh city': ['ho chi minh city', 'ho chi minh', 'hcm', 'tp hcm', 'tphcm', 'sai gon', 'saigon'],
  'ha noi': ['ha noi', 'hanoi', 'hn'],
  'da nang': ['da nang', 'danang'],
};

const EXPERIENCE_PATTERNS = [
  /(\d+(?:\.\d+)?)\+?\s*(?:years|year|yrs|yr)/i,
  /(\d+(?:\.\d+)?)\+?\s*(?:nam)/i,
];

function stripAccents(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function normalizeText(value: string | null | undefined) {
  if (!value) return '';
  return stripAccents(value)
    .toLowerCase()
    .replace(/[^a-z0-9+#.\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeBySynonyms(value: string | null | undefined, dictionary: Record<string, string[]>) {
  const cleaned = normalizeText(value);
  for (const [canonical, aliases] of Object.entries(dictionary)) {
    if (aliases.includes(cleaned) || aliases.some(alias => cleaned.includes(alias))) return canonical;
  }
  return cleaned;
}

function normalizeSkill(skill: string) {
  return normalizeBySynonyms(skill, SKILL_SYNONYMS);
}

function skillAliases(skill: string) {
  const canonical = normalizeSkill(skill);
  const aliases = SKILL_SYNONYMS[canonical] ?? [canonical];
  return uniqueStrings([canonical, ...aliases.map(normalizeText)]);
}

function normalizeTitle(title: string | null | undefined) {
  return normalizeBySynonyms(title, TITLE_SYNONYMS);
}

function normalizeLocation(location: string | null | undefined) {
  return normalizeBySynonyms(location, LOCATION_SYNONYMS);
}

function parseExperienceYears(experience: string | null | undefined) {
  const normalized = normalizeText(experience);
  if (!normalized) return null;
  if (normalized.includes('chua co kinh nghiem') || normalized.includes('no experience')) return 0;
  if (normalized.includes('tren 10 nam')) return 10;
  for (const pattern of EXPERIENCE_PATTERNS) {
    const match = normalized.match(pattern);
    if (match) return Number(match[1]);
  }
  const numeric = normalized.match(/(\d+(?:\.\d+)?)/);
  return numeric ? Number(numeric[1]) : null;
}

function parseSalaryRangeMillions(value: string | null | undefined, usdToVndRate: number = DEFAULT_USD_VND_RATE) {
  const normalized = stripAccents(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9+$.,\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!normalized) return null;
  if (normalized.includes('thoa thuan') || normalized.includes('negotiable') || normalized.includes('competitive')) {
    return null;
  }

  const parseLocalizedNumber = (raw: string) => {
    if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(raw)) {
      return Number(raw.replace(/,/g, ''));
    }
    if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(raw)) {
      return Number(raw.replace(/\./g, '').replace(',', '.'));
    }
    if (raw.includes(',') && !raw.includes('.')) {
      return Number(raw.replace(',', '.'));
    }
    return Number(raw);
  };

  const matches = Array.from(normalized.matchAll(/(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)/g));
  if (matches.length === 0) return null;

  const hasUsd = normalized.includes('usd') || normalized.includes('$');
  const hasK = normalized.includes('k');
  const hasMillionUnit = normalized.includes('trieu') || /(?:^|\s)tr(?:\s|$)/.test(normalized) || normalized.includes('million');
  const hasVndUnit = normalized.includes('vnd');
  const values = matches.map(match => {
    let amount = parseLocalizedNumber(match[1]);
    if (hasUsd && hasK && amount < 100) amount *= 1000;
    if (hasUsd) {
      amount = (amount * usdToVndRate) / 1_000_000;
    } else if (hasMillionUnit) {
      return amount;
    } else if (hasVndUnit || amount >= 1000) {
      amount /= 1_000_000;
    }
    return amount;
  }).filter(valueNumber => Number.isFinite(valueNumber) && valueNumber > 0);

  if (values.length === 0) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  return { min, max };
}

function parseUpdatedDate(value: string | null | undefined) {
  if (!value) return null;
  const raw = value.trim();
  const normalized = normalizeText(raw);
  if (!normalized) return null;
  if (normalized.includes('ngay hom nay') || normalized === 'today') {
    return new Date().toISOString().slice(0, 10);
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const slashMatch = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    const [, dd, mm, yyyy] = slashMatch;
    return `${yyyy}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`;
  }
  const yearMatch = raw.match(/^(19|20)\d{2}$/);
  if (yearMatch) return `${yearMatch[0]}-01-01`;
  const parsed = new Date(raw);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return null;
}

function uniqueStrings(values: Array<string | null | undefined>) {
  return Array.from(new Set(values.map(value => (value ?? '').trim()).filter(Boolean)));
}

function extractProfileSkills(profile: WebProfile) {
  const fromTags = profile.tags ?? [];
  const haystack = normalizeText(`${profile.title} ${profile.summary ?? ''} ${profile.raw_text ?? ''}`);
  const detected = Object.keys(SKILL_SYNONYMS).filter(skill => {
    const aliases = SKILL_SYNONYMS[skill] ?? [skill];
    return aliases.some(alias => haystack.includes(normalizeText(alias)));
  });
  return uniqueStrings([...fromTags, ...detected]);
}

function containsWholeTerm(haystack: string, term: string) {
  const cleanTerm = normalizeText(term);
  if (!haystack || !cleanTerm) return false;
  const paddedHaystack = ` ${haystack} `;
  return paddedHaystack.includes(` ${cleanTerm} `);
}

function isShortExactSkill(skill: string) {
  return ['c#', 'c++', 'qa', 'ai', 'ui', 'ux', 'oop'].includes(normalizeSkill(skill));
}

function hasSkillMatch(requiredSkill: string, candidateSkills: string[], candidateText: string) {
  const requiredAliases = skillAliases(requiredSkill);
  const normalizedCandidates = candidateSkills.map(normalizeSkill);

  for (const alias of requiredAliases) {
    if (normalizedCandidates.some(candidate => candidate === alias)) return true;
    if (containsWholeTerm(candidateText, alias)) return true;

    if (!isShortExactSkill(alias)) {
      if (normalizedCandidates.some(candidate => candidate.includes(alias) || alias.includes(candidate))) return true;
    }
  }

  return false;
}

function jobTitleScore(jdAnalysis: JdAnalysisSummary, title: string | null | undefined) {
  const jdTitle = normalizeTitle(jdAnalysis.job_title);
  const alternatives = new Set((jdAnalysis.alternative_job_titles ?? []).map(normalizeTitle).filter(Boolean));
  const candidateTitle = normalizeTitle(title);
  if (!candidateTitle) return 20;
  if (candidateTitle === jdTitle) return 100;
  if (alternatives.has(candidateTitle)) return 90;
  if (jdTitle && (candidateTitle.includes(jdTitle) || jdTitle.includes(candidateTitle))) return 85;
  if (jdTitle === 'backend developer' && candidateTitle === 'full-stack developer') return 60;
  return 10;
}

function skillScore(jdAnalysis: JdAnalysisSummary, skills: string[], candidateText: string) {
  const required = (jdAnalysis.required_skills ?? []).map(normalizeSkill);
  const preferred = (jdAnalysis.preferred_skills ?? []).map(normalizeSkill);
  const matchedRequired = (jdAnalysis.required_skills ?? []).filter(skill => hasSkillMatch(skill, skills, candidateText));
  const missingRequired = (jdAnalysis.required_skills ?? []).filter(skill => !hasSkillMatch(skill, skills, candidateText));
  const matchedPreferred = (jdAnalysis.preferred_skills ?? []).filter(skill => hasSkillMatch(skill, skills, candidateText));

  if (required.length === 0 && preferred.length === 0) {
    return { score: 50, matchedRequired, missingRequired };
  }

  const requiredRatio = matchedRequired.length / Math.max(1, required.length);
  const preferredRatio = preferred.length > 0 ? matchedPreferred.length / preferred.length : 0;
  return {
    score: Math.round((requiredRatio * 80 + preferredRatio * 20) * 100) / 100,
    matchedRequired,
    missingRequired,
  };
}

function salaryScore(
  jdSalaryText: string | null | undefined,
  candidateSalaryText: string | null | undefined,
  usdToVndRate: number,
) {
  const jdRange = parseSalaryRangeMillions(jdSalaryText, usdToVndRate);
  const candidateRange = parseSalaryRangeMillions(candidateSalaryText, usdToVndRate);

  if (!jdRange && !candidateRange) return 60;
  if (!jdRange) return 60;
  if (!candidateRange) return 60;

  if (candidateRange.min > jdRange.max) {
    const overRatio = candidateRange.min / Math.max(jdRange.max, 1);
    if (overRatio <= 1.05) return 55;
    if (overRatio <= 1.15) return 35;
    if (overRatio <= 1.3) return 15;
    return 0;
  }

  if (candidateRange.max < jdRange.min) {
    const underRatio = candidateRange.max / Math.max(jdRange.min, 1);
    if (underRatio >= 0.9) return 92;
    if (underRatio >= 0.75) return 82;
    return 72;
  }

  const fullyInsideBudget = candidateRange.min >= jdRange.min && candidateRange.max <= jdRange.max;
  if (fullyInsideBudget) return 100;

  const candidateMid = (candidateRange.min + candidateRange.max) / 2;
  const jdMid = (jdRange.min + jdRange.max) / 2;
  const distanceRatio = Math.abs(candidateMid - jdMid) / Math.max(jdRange.max - jdRange.min, 1);
  if (distanceRatio <= 0.15) return 96;
  if (distanceRatio <= 0.3) return 90;
  return 84;
}

function experienceScore(requiredYears: number | null | undefined, candidateYears: number | null) {
  if (requiredYears === null || requiredYears === undefined) return 55;
  if (candidateYears === null) return 60;
  if (candidateYears >= requiredYears) return 100;
  if (candidateYears >= Math.max(0, requiredYears - 1)) return 70;
  if (candidateYears >= Math.max(0, requiredYears - 2)) return 35;
  return 5;
}

function locationScore(jdAnalysis: JdAnalysisSummary, candidateLocation: string | null | undefined) {
  const jdLocation = normalizeLocation(jdAnalysis.work_location);
  const profileLocation = normalizeLocation(candidateLocation);
  if (jdLocation && profileLocation && profileLocation === jdLocation) return 100;
  return 0;
}

function shouldFilterOutWebCandidate(titleScore: number, skillScoreValue: number, experienceScoreValue: number) {
  if (titleScore <= 10 && skillScoreValue < 20) return true;
  if (titleScore <= 20 && skillScoreValue < 30) return true;
  if (experienceScoreValue <= 5 && skillScoreValue < 40) return true;
  return false;
}

function recencyScore(lastUpdatedDate: string | null | undefined) {
  const isoDate = parseUpdatedDate(lastUpdatedDate);
  if (!isoDate) return 40;
  const updated = new Date(isoDate);
  if (Number.isNaN(updated.getTime())) return 40;
  const ageDays = Math.max(0, Math.floor((Date.now() - updated.getTime()) / (1000 * 60 * 60 * 24)));
  if (ageDays <= 7) return 100;
  if (ageDays <= 30) return 80;
  if (ageDays <= 90) return 55;
  return 20;
}


function buildMinMaxRecencyScores(profiles: WebProfile[]) {
  const timestamps = new Map<string, number | null>();

  for (const profile of profiles) {
    const isoDate = parseUpdatedDate(profile.last_access);
    if (!isoDate) {
      timestamps.set(String(profile.id), null);
      continue;
    }
    const value = new Date(isoDate).getTime();
    timestamps.set(String(profile.id), Number.isNaN(value) ? null : value);
  }

  const validValues = Array.from(timestamps.values()).filter((value): value is number => value !== null);
  if (validValues.length === 0) {
    return new Map<string, number>(profiles.map(profile => [String(profile.id), 40]));
  }

  const minTime = Math.min(...validValues);
  const maxTime = Math.max(...validValues);
  if (minTime === maxTime) {
    return new Map<string, number>(
      profiles.map(profile => [String(profile.id), timestamps.get(String(profile.id)) === null ? 0 : 100]),
    );
  }

  const scores = new Map<string, number>();
  for (const profile of profiles) {
    const key = String(profile.id);
    const timestamp = timestamps.get(key) ?? null;
    if (timestamp === null) {
      scores.set(key, 0);
      continue;
    }
    scores.set(key, Math.round((((timestamp - minTime) / (maxTime - minTime)) * 100) * 100) / 100);
  }
  return scores;
}

function hasExplicitSalaryRequirement(jdSalaryText: string | null | undefined, usdToVndRate: number) {
  return parseSalaryRangeMillions(jdSalaryText, usdToVndRate) !== null;
}

export function resolveWebRankingWeights(jdAnalysis: JdAnalysisSummary, usdToVndRate: number = DEFAULT_USD_VND_RATE) {
  const includeSalary = hasExplicitSalaryRequirement(jdAnalysis.salary_text, usdToVndRate);
  const activeWeights = {
    ...WEB_RANKING_BASE_WEIGHTS,
    skill_match_score: includeSalary ? WEB_RANKING_BASE_WEIGHTS.skill_match_score : 0,
  };
  const totalWeight = Object.values(activeWeights).reduce((sum, value) => sum + value, 0);

  return {
    includeSalary,
    normalized: {
      job_title_match_score: activeWeights.job_title_match_score / totalWeight,
      skill_match_score: activeWeights.skill_match_score / totalWeight,
      experience_match_score: activeWeights.experience_match_score / totalWeight,
      location_match_score: activeWeights.location_match_score / totalWeight,
      cv_recency_score: activeWeights.cv_recency_score / totalWeight,
    },
  };
}

export function resolveWebBreakdownLabels(jdAnalysis: JdAnalysisSummary, usdToVndRate: number = DEFAULT_USD_VND_RATE) {
  const { includeSalary } = resolveWebRankingWeights(jdAnalysis, usdToVndRate);
  return {
    job_title_match_score: 'Vi tri',
    skill_match_score: includeSalary ? 'Muc luong' : 'Muc luong bo qua',
    experience_match_score: 'Kinh nghiem',
    location_match_score: 'Dia diem',
    cv_recency_score: 'Do moi',
  };
}

function buildReason(
  profile: WebProfile,
  years: number | null,
  matchedSkills: string[],
  missingSkills: string[],
  jdAnalysis: JdAnalysisSummary,
  updatedDate: string | null,
) {
  const parts: string[] = [];
  if (years !== null) parts.push(`ung vien co ${years} nam kinh nghiem`);
  if (profile.title) parts.push(`dang huong toi vi tri ${profile.title}`);
  if (matchedSkills.length > 0) parts.push(`co ${matchedSkills.slice(0, 4).join(', ')}`);
  if (profile.salary) parts.push(`muc luong ${profile.salary}`);
  if (jdAnalysis.work_mode !== 'remote' && profile.location) parts.push(`o ${profile.location}`);
  if (missingSkills.length > 0) parts.push(`con thieu ${missingSkills.slice(0, 2).join(', ')}`);
  if (updatedDate) parts.push(`cap nhat CV ngay ${updatedDate}`);
  return parts.length > 0 ? `CV phu hop vi ${parts.join(', ')}.` : 'CV phu hop voi JD da trich xuat.';
}

export function buildWebSearchQuery(jdAnalysis: JdAnalysisSummary) {
  return uniqueStrings([
    jdAnalysis.job_title,
    ...(jdAnalysis.required_skills ?? []).slice(0, 5),
    jdAnalysis.work_location ?? '',
  ]).join(' ');
}

export interface RankedWebCandidate extends SearchCvResult {
  filtered_out_by_rules?: boolean;
  web_pass_tier?: 'strong' | 'medium' | 'top_up';
}

export function scoreWebProfilesFromJd(
  profiles: WebProfile[],
  jdAnalysis: JdAnalysisSummary,
  modelId: string,
  sbertId?: string,
  usdToVndRate: number = DEFAULT_USD_VND_RATE,
) {
  const rankingWeights = resolveWebRankingWeights(jdAnalysis, usdToVndRate);
  const recencyScores = buildMinMaxRecencyScores(profiles);

  return profiles
    .map((profile): RankedWebCandidate => {
      const skills = extractProfileSkills(profile);
      const candidateText = normalizeText(`${profile.title} ${(profile.tags ?? []).join(' ')} ${profile.summary ?? ''} ${profile.raw_text ?? ''}`);
      const years = parseExperienceYears(profile.experience);
      const updatedDate = parseUpdatedDate(profile.last_access);
      const title = jobTitleScore(jdAnalysis, profile.title);
      const skillResult = skillScore(jdAnalysis, skills, candidateText);
      const experience = experienceScore(jdAnalysis.required_experience_years, years);
      const salary = salaryScore(jdAnalysis.salary_text, profile.salary, usdToVndRate);
      const location = locationScore(jdAnalysis, profile.location);
      const recency = recencyScores.get(String(profile.id)) ?? recencyScore(updatedDate);
      const filteredOut = shouldFilterOutWebCandidate(title, skillResult.score, experience);

      const totalScore = Math.round((
        title * rankingWeights.normalized.job_title_match_score
        + salary * rankingWeights.normalized.skill_match_score
        + experience * rankingWeights.normalized.experience_match_score
        + location * rankingWeights.normalized.location_match_score
        + recency * rankingWeights.normalized.cv_recency_score
      ) * 100) / 100;
      const tier: RankedWebCandidate['web_pass_tier'] = totalScore >= 55
        ? 'strong'
        : totalScore >= 40
          ? 'medium'
          : 'top_up';

      return {
        id: profile.id,
        candidate_id: String(profile.id),
        filename: `${profile.title} - ${profile.candidate_name}`,
        category: 'CV',
        preview_url: profile.attachment_url || profile.profile_url || profile.source_url,
        cloudinary_url: profile.profile_url || profile.source_url,
        created_at: updatedDate,
        indexed_at: updatedDate,
        search_score: Math.round((totalScore / 100) * 1000000) / 1000000,
        embedding_model_id: modelId || 'web-search',
        sbert_id: sbertId,
        text_length: profile.raw_text?.length || profile.summary?.length || `${profile.title} ${profile.candidate_name}`.length,
        candidate_name: profile.candidate_name,
        current_job_title: profile.title,
        desired_job_title: profile.title,
        experience_years: years,
        location: profile.location,
        salary: profile.salary,
        skills,
        matched_required_skills: skillResult.matchedRequired,
        missing_required_skills: skillResult.missingRequired,
        last_updated_date: updatedDate,
        total_score: totalScore,
        score_breakdown: {
          job_title_match_score: Math.round(title * 100) / 100,
          skill_match_score: Math.round(salary * 100) / 100,
          experience_match_score: Math.round(experience * 100) / 100,
          location_match_score: Math.round(location * 100) / 100,
          cv_recency_score: Math.round(recency * 100) / 100,
        },
        recommendation_reason: buildReason(profile, years, skillResult.matchedRequired, skillResult.missingRequired, jdAnalysis, updatedDate),
        filtered_out_by_rules: filteredOut,
        web_pass_tier: tier,
      };
    })
    .sort((left, right) => {
      const totalDiff = (right.total_score ?? 0) - (left.total_score ?? 0);
      if (totalDiff !== 0) return totalDiff;
      const dateDiff = new Date(right.last_updated_date ?? 0).getTime() - new Date(left.last_updated_date ?? 0).getTime();
      if (dateDiff !== 0) return dateDiff;
      return (right.matched_required_skills?.length ?? 0) - (left.matched_required_skills?.length ?? 0);
    });
}

export function rankWebProfilesFromJd(
  profiles: WebProfile[],
  jdAnalysis: JdAnalysisSummary,
  modelId: string,
  sbertId?: string,
  limit?: number,
  usdToVndRate: number = DEFAULT_USD_VND_RATE,
) {
  const scored = scoreWebProfilesFromJd(profiles, jdAnalysis, modelId, sbertId, usdToVndRate);
  const eligible = scored.filter(item => !item.filtered_out_by_rules);
  const strong = eligible.filter(item => item.web_pass_tier === 'strong');
  const medium = eligible.filter(item => item.web_pass_tier === 'medium');
  const filtered = scored.filter(item => item.filtered_out_by_rules);
  const topUp = eligible.filter(item => item.web_pass_tier === 'top_up');
  const kept = [...strong, ...medium];
  const desired = limit ?? profiles.length;
  const fallback = [...topUp, ...filtered];
  const toppedUp = kept.length >= desired
    ? kept.slice(0, desired)
    : [...kept, ...fallback.slice(0, Math.max(0, desired - kept.length))];
  return {
    scored,
    strong,
    medium,
    topUp,
    kept,
    filtered,
    toppedUp,
  };
}

export function mapWebProfilesToEstimatedResults(
  profiles: WebProfile[],
  modelId: string,
  sbertId?: string,
) {
  const resultScore = (index: number, count: number) => {
    if (count <= 1) return 0.99;
    return Math.max(0.7, 0.99 - index * (0.24 / Math.max(1, count - 1)));
  };

  const profileTextLength = (profile: WebProfile) => (
    profile.raw_text?.length
    || profile.summary?.length
    || `${profile.title} ${profile.candidate_name}`.length
  );

  return profiles.map((profile, index): SearchCvResult => {
    const score = resultScore(index, profiles.length);
    const totalScore = Math.round(Math.max(0, Math.min(1, score)) * 100);
    const jobTitleScore = Math.round(totalScore * 0.3);
    const skillScore = Math.round(totalScore * 0.3);
    const experienceScore = Math.round(totalScore * 0.2);
    const locationScore = Math.round(totalScore * 0.1);
    const recencyScoreValue = totalScore - jobTitleScore - skillScore - experienceScore - locationScore;

    return {
      id: profile.id,
      filename: `${profile.title} - ${profile.candidate_name}`,
      category: 'CV',
      preview_url: profile.attachment_url || profile.profile_url || profile.source_url,
      cloudinary_url: profile.profile_url || profile.source_url,
      created_at: profile.last_access,
      indexed_at: profile.last_access,
      search_score: score,
      embedding_model_id: modelId || 'web-search',
      sbert_id: sbertId,
      text_length: profileTextLength(profile),
      candidate_name: profile.candidate_name,
      current_job_title: profile.title,
      location: profile.location,
      skills: profile.tags,
      last_updated_date: profile.last_access,
      total_score: totalScore,
      score_breakdown: {
        job_title_match_score: jobTitleScore,
        skill_match_score: skillScore,
        experience_match_score: experienceScore,
        location_match_score: locationScore,
        cv_recency_score: recencyScoreValue,
      },
      recommendation_reason: `Hien thi theo ket qua web goc do chua co CV vuot qua bo loc xep hang rule-based tren ${profile.source || 'web source'}.`,
    };
  });
}
