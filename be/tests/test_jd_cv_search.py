from app.schemas.cv_search import JdAnalysisPayload
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.jd_cv_search import (
    CandidateProfile,
    compute_minmax_recency_scores,
    detect_work_mode,
    detect_salary_text,
    experience_match,
    job_title_match_score,
    location_match,
    recency_score,
    should_filter_out,
    skill_match,
)


def _analysis() -> JdAnalysisPayload:
    return JdAnalysisPayload(
        job_title="Backend Developer",
        job_category="Software Development",
        required_skills=["Java", "Spring Boot", "MySQL", "REST API"],
        preferred_skills=["Docker"],
        required_experience_years=2,
        work_location="Ho Chi Minh City",
        work_mode="onsite",
        seniority_level="middle",
        alternative_job_titles=["Java Developer", "Full-stack Developer"],
        confidence=0.9,
    )


def test_job_title_match_score_prefers_equivalent_titles() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van A",
        current_job_title="Java Developer",
        desired_job_title="Backend Developer",
        experience_years=3,
        location="Ho Chi Minh City",
        work_mode="onsite",
        skills=["Java", "Spring Boot", "MySQL"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert job_title_match_score(_analysis(), profile) >= 90


def test_skill_match_distinguishes_matched_and_missing_required_skills() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van A",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=3,
        location="Ho Chi Minh City",
        work_mode="onsite",
        skills=["Java", "Spring Boot", "Docker"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    score, matched, missing = skill_match(_analysis(), profile)

    assert score > 40
    assert matched == ["Java", "Spring Boot"]
    assert missing == ["MySQL", "REST API"]


def test_experience_location_and_recency_scores_follow_priority_rules() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van A",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=2.5,
        location="Ho Chi Minh City",
        work_mode="onsite",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert experience_match(_analysis(), profile) >= 88
    assert location_match(_analysis(), profile) == 100
    assert recency_score(profile.last_updated_date) >= 80


def test_experience_match_keeps_full_score_when_candidate_exceeds_requirement() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van Senior",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=7,
        location="Ho Chi Minh City",
        work_mode="onsite",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert experience_match(_analysis(), profile) == 100


def test_location_match_requires_same_province() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van B",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=2.5,
        location="Ha Noi",
        work_mode="remote",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=True,
        open_to_remote=True,
    )

    assert location_match(_analysis(), profile) == 10


def test_location_match_accepts_full_address_in_same_city() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van B",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=2.5,
        location="Ho Chi Minh City, District 1",
        work_mode="onsite",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert location_match(_analysis(), profile) == 70


def test_location_match_prefers_same_city_and_same_area() -> None:
    analysis = _analysis().model_copy(update={"work_location": "Ho Chi Minh City, District 1"})
    profile = CandidateProfile(
        candidate_name="Nguyen Van C",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=3,
        location="Ho Chi Minh City, District 1",
        work_mode="onsite",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert location_match(analysis, profile) == 100


def test_should_filter_out_hard_rejects_wrong_title() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van Z",
        current_job_title="Tester",
        desired_job_title=None,
        experience_years=5,
        location="Ho Chi Minh City",
        work_mode="onsite",
        skills=["Java"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )
    assert should_filter_out(_analysis(), profile, 10, 100, 100) is True


def test_job_title_match_score_supports_security_title_family() -> None:
    analysis = JdAnalysisPayload(
        job_title="Senior Data Security Specialist",
        job_category="Information Security",
        required_skills=["Data Governance"],
        preferred_skills=[],
        required_experience_years=5,
        work_location="Ha Noi",
        work_mode="onsite",
        seniority_level="senior",
        alternative_job_titles=["Information Security Specialist", "Security Engineer"],
        confidence=0.9,
    )
    profile = CandidateProfile(
        candidate_name="Nguyen Van C",
        current_job_title="Security Engineer",
        desired_job_title=None,
        experience_years=6,
        location="Ha Noi",
        work_mode="onsite",
        skills=["Data Governance"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=False,
    )

    assert job_title_match_score(analysis, profile) >= 90


def test_detect_salary_text_extracts_common_salary_ranges() -> None:
    assert detect_salary_text("Salary: 15-20M VND, bonus") == "15-20M VND"
    assert detect_salary_text("Muc luong: 20-30 trieu/thang") == "20-30 trieu/thang"


def test_detect_work_mode_defaults_to_onsite_when_cv_is_silent() -> None:
    assert detect_work_mode("Backend Developer with Java and Spring Boot experience") == "onsite"


def test_detect_work_mode_marks_online_cv_as_remote() -> None:
    assert detect_work_mode("Looking for online remote work, can work from home") == "remote"


def test_should_filter_out_remote_cv_for_onsite_jd() -> None:
    profile = CandidateProfile(
        candidate_name="Nguyen Van Remote",
        current_job_title="Backend Developer",
        desired_job_title=None,
        experience_years=4,
        location="Ho Chi Minh City",
        work_mode="remote",
        skills=["Java", "Spring Boot", "MySQL", "REST API"],
        last_updated_date="2026-06-18",
        willing_to_relocate=False,
        open_to_remote=True,
    )

    assert should_filter_out(_analysis(), profile, 100, 100, 100) is True


def test_compute_minmax_recency_scores_prefers_newer_documents() -> None:
    older = SimpleNamespace(id=1, created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    newer = SimpleNamespace(id=2, created_at=datetime(2026, 6, 20, tzinfo=timezone.utc))

    scores = compute_minmax_recency_scores([older, newer])

    assert scores[older.id] == 0.0
    assert scores[newer.id] == 100.0


def test_compute_minmax_recency_scores_returns_full_score_when_all_dates_equal() -> None:
    same_time = datetime(2026, 6, 20, tzinfo=timezone.utc)
    first = SimpleNamespace(id=1, created_at=same_time)
    second = SimpleNamespace(id=2, created_at=same_time)

    scores = compute_minmax_recency_scores([first, second])

    assert scores[first.id] == 100.0
    assert scores[second.id] == 100.0
