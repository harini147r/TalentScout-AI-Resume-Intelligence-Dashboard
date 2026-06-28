import math
import re
from collections import Counter
from difflib import SequenceMatcher

from src.core.preprocessor import clean_text


SKILL_LIBRARY = [
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "nosql",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
    "html", "css", "tailwind", "bootstrap", "aws", "azure", "gcp", "docker",
    "kubernetes", "terraform", "jenkins", "git", "github", "ci/cd", "linux",
    "machine learning", "deep learning", "nlp", "computer vision", "gen ai",
    "generative ai", "llm", "rag", "prompt engineering", "data science",
    "data analysis", "data engineering", "pandas", "numpy", "scikit-learn",
    "tensorflow", "pytorch", "keras", "xgboost", "random forest", "statistics",
    "power bi", "tableau", "excel", "mongodb", "postgresql", "mysql", "snowflake",
    "spark", "hadoop", "airflow", "api", "rest", "graphql", "microservices",
    "agile", "scrum", "jira", "product management", "stakeholder management",
    "communication", "leadership", "problem solving", "project management",
]

SECTION_ALIASES = {
    "summary": ["summary", "profile", "objective", "about"],
    "skills": ["skills", "technical skills", "core skills", "tools"],
    "experience": ["experience", "work experience", "employment", "professional experience"],
    "projects": ["projects", "personal projects", "academic projects"],
    "education": ["education", "academic background", "qualification"],
    "certifications": ["certifications", "certificates", "licenses"],
}

BIAS_TERMS = [
    "age", "dob", "date of birth", "married", "unmarried", "single", "gender",
    "male", "female", "religion", "caste", "nationality", "race", "photo",
    "father", "mother", "family", "pregnant", "disability",
]

ACTION_VERBS = [
    "built", "created", "designed", "developed", "implemented", "improved",
    "reduced", "increased", "optimized", "automated", "deployed", "led",
    "managed", "delivered", "analyzed", "launched", "migrated", "trained",
]

STOPWORDS = {
    "and", "the", "for", "with", "that", "this", "from", "are", "was", "were",
    "will", "you", "your", "our", "have", "has", "can", "using", "use", "into",
    "job", "role", "work", "team", "skills", "experience", "years", "candidate",
}


def calculate_ats_score(skill_score, semantic_score):
    return round((0.6 * skill_score) + (0.4 * semantic_score), 2)


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def tokenize(text):
    return re.findall(r"[a-zA-Z][a-zA-Z+#./-]{1,}", clean_text(text))


def extract_contact(text):
    email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    phone = re.search(r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4})", text)
    links = re.findall(r"(?:https?://|www\.)\S+|(?:linkedin\.com|github\.com)/\S+", text, flags=re.I)
    return {
        "email": email.group(0) if email else "Not found",
        "phone": phone.group(0) if phone else "Not found",
        "links": list(dict.fromkeys(links))[:5],
    }


def detect_sections(text):
    lowered = clean_text(text)
    detected = {}
    for section, aliases in SECTION_ALIASES.items():
        detected[section] = any(re.search(rf"\b{re.escape(alias)}\b", lowered) for alias in aliases)
    return detected


def extract_skills(text):
    lowered = clean_text(text)
    found = []
    for skill in SKILL_LIBRARY:
        pattern = rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.append(skill.title() if skill not in {"sql", "aws", "gcp", "nlp", "llm"} else skill.upper())
    return sorted(set(found))


def extract_keywords(text, limit=18):
    words = [word for word in tokenize(text) if len(word) > 2 and word not in STOPWORDS]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]


def keyword_match(job_text, resume_text):
    job_skills = extract_skills(job_text)
    resume_skills = extract_skills(resume_text)
    job_keywords = extract_keywords(job_text)
    resume_clean = clean_text(resume_text)

    required = list(dict.fromkeys(job_skills + [kw.title() for kw in job_keywords[:10]]))
    matched = []
    missing = []

    for keyword in required:
        if re.search(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])", resume_clean):
            matched.append(keyword)
        else:
            missing.append(keyword)

    score = round((len(matched) / len(required)) * 100, 1) if required else 0
    return {
        "score": score,
        "required": required,
        "matched": matched,
        "missing": missing,
        "resume_skills": resume_skills,
    }


def estimate_experience(text):
    lowered = clean_text(text)
    explicit_years = [int(value) for value in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)\b", lowered)]
    year_ranges = []
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", text)]
    for index in range(0, len(years) - 1):
        start, end = years[index], years[index + 1]
        if 1980 <= start <= 2035 and 1980 <= end <= 2035 and end >= start:
            year_ranges.append(end - start)

    estimated_years = max(explicit_years + year_ranges + [0])
    action_hits = sum(1 for verb in ACTION_VERBS if re.search(rf"\b{verb}\b", lowered))
    quantified_hits = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:%|percent|x|times|k|m|hours|days|users|customers|revenue)\b", lowered))
    project_hits = len(re.findall(r"\b(project|built|developed|deployed|model|dashboard|application)\b", lowered))

    score = clamp((estimated_years * 7) + (action_hits * 4) + (quantified_hits * 7) + min(project_hits, 8) * 3)
    level = "Entry"
    if estimated_years >= 7:
        level = "Senior"
    elif estimated_years >= 3:
        level = "Mid-level"
    elif estimated_years >= 1:
        level = "Junior"

    return {
        "score": round(score, 1),
        "years": estimated_years,
        "level": level,
        "action_verbs": action_hits,
        "metrics": quantified_hits,
        "project_signals": project_hits,
    }


def formatting_check(text):
    sections = detect_sections(text)
    word_count = len(tokenize(text))
    bullet_count = len(re.findall(r"(?:^|\n)\s*(?:[-*\u2022]|\d+\.)\s+", text))
    long_lines = sum(1 for line in text.splitlines() if len(line) > 120)
    uppercase_ratio = sum(1 for c in text if c.isupper()) / max(1, sum(1 for c in text if c.isalpha()))

    issues = []
    if not sections["summary"]:
        issues.append("Add a short summary/profile section.")
    if not sections["skills"]:
        issues.append("Add a clearly labelled skills section.")
    if not sections["experience"] and not sections["projects"]:
        issues.append("Add experience or project evidence.")
    if word_count < 180:
        issues.append("Resume looks too short for a complete evaluation.")
    if word_count > 1100:
        issues.append("Resume may be too long; tighten repeated content.")
    if bullet_count < 4:
        issues.append("Use achievement bullets for scanability.")
    if long_lines > 5:
        issues.append("Some lines are too long and may parse poorly.")
    if uppercase_ratio > 0.22:
        issues.append("Too much uppercase text can hurt readability.")

    score = 100
    score -= sum(1 for present in sections.values() if not present) * 6
    score -= min(30, len(issues) * 8)
    score += min(10, bullet_count)

    return {
        "score": round(clamp(score), 1),
        "sections": sections,
        "word_count": word_count,
        "bullet_count": bullet_count,
        "issues": issues,
    }


def bias_reducer(text):
    lowered = clean_text(text)
    found = sorted({term for term in BIAS_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)})
    score = clamp(100 - len(found) * 12)
    guidance = [
        "Review candidates using skills, outcomes, and job-relevant experience only.",
        "Ignore personal identifiers while comparing scorecards.",
    ]
    if found:
        guidance.insert(0, "Remove or mask personal details before sharing the resume with reviewers.")
    return {"score": round(score, 1), "flags": found, "guidance": guidance}


def plagiarism_detector(current_text, corpus):
    current = clean_text(current_text)
    current_tokens = set(tokenize(current_text))
    best = {"candidate": "No comparison available", "similarity": 0.0, "overlap": 0.0}

    for name, other_text in corpus:
        other = clean_text(other_text)
        if not other or other == current:
            continue
        ratio = SequenceMatcher(None, current[:6000], other[:6000]).ratio()
        other_tokens = set(tokenize(other_text))
        overlap = len(current_tokens & other_tokens) / max(1, len(current_tokens | other_tokens))
        combined = round(((ratio * 0.55) + (overlap * 0.45)) * 100, 1)
        if combined > best["similarity"]:
            best = {"candidate": name, "similarity": combined, "overlap": round(overlap * 100, 1)}

    risk = "Low"
    if best["similarity"] >= 72:
        risk = "High"
    elif best["similarity"] >= 48:
        risk = "Medium"
    best["risk"] = risk
    return best


def semantic_similarity(job_text, resume_text):
    job_tokens = set(tokenize(job_text))
    resume_tokens = set(tokenize(resume_text))
    if not job_tokens or not resume_tokens:
        return 0.0
    overlap = len(job_tokens & resume_tokens) / math.sqrt(len(job_tokens) * len(resume_tokens))
    return round(clamp(overlap * 100), 1)


def ai_summary(name, keyword, experience, formatting, bias, plagiarism):
    strengths = []
    if keyword["matched"]:
        strengths.append(f"matches {len(keyword['matched'])} job requirements")
    if experience["metrics"] > 0:
        strengths.append("shows measurable results")
    if formatting["score"] >= 75:
        strengths.append("is easy to read")

    risks = []
    if keyword["missing"]:
        risks.append(f"missing {len(keyword['missing'])} important keywords")
    if experience["score"] < 45:
        risks.append("needs clearer work experience or results")
    if formatting["issues"]:
        risks.append("needs a clearer resume structure")
    if bias["flags"]:
        risks.append("contains personal details to mask")
    if plagiarism["risk"] != "Low":
        risks.append(f"{plagiarism['risk'].lower()} similarity risk")

    strengths_text = ", ".join(strengths) if strengths else "shows a readable baseline profile"
    risks_text = ", ".join(risks) if risks else "no major review blockers detected"
    return f"{name} {strengths_text}. Things to improve: {risks_text}."


def analyze_resume(name, resume_text, job_text, corpus=None, semantic_score=None):
    keyword = keyword_match(job_text, resume_text)
    experience = estimate_experience(resume_text)
    formatting = formatting_check(resume_text)
    bias = bias_reducer(resume_text)
    plagiarism = plagiarism_detector(resume_text, corpus or [])
    semantic = semantic_score if semantic_score is not None else semantic_similarity(job_text, resume_text)

    overall = round(
        (keyword["score"] * 0.30)
        + (semantic * 0.22)
        + (experience["score"] * 0.18)
        + (formatting["score"] * 0.14)
        + (bias["score"] * 0.08)
        + ((100 - plagiarism["similarity"]) * 0.08),
        1,
    )

    recommendation = "Good match"
    if overall < 45:
        recommendation = "Needs improvement"
    elif overall < 68:
        recommendation = "Can be considered"

    contact = extract_contact(resume_text)
    report = {
        "candidate": name,
        "overall_score": overall,
        "recommendation": recommendation,
        "semantic_score": round(semantic, 1),
        "keyword": keyword,
        "experience": experience,
        "formatting": formatting,
        "bias": bias,
        "plagiarism": plagiarism,
        "contact": contact,
        "sections": formatting["sections"],
    }
    report["summary"] = ai_summary(name, keyword, experience, formatting, bias, plagiarism)
    return report
