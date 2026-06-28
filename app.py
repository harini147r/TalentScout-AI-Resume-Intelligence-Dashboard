from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Literal

import docx2txt
import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="TalentScout API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

UPLOAD_CACHE: dict[str, list[dict[str, str]]] = {}
LAST_RESULTS: list[dict[str, Any]] = []


class SkillGroups(BaseModel):
    matched: list[str] = Field(default_factory=list)
    partial: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    technicalSkills: int = Field(ge=0, le=100)
    experienceLevel: int = Field(ge=0, le=100)
    domainKnowledge: int = Field(ge=0, le=100)
    cultureFit: int = Field(ge=0, le=100)
    growthPotential: int = Field(ge=0, le=100)


class CandidateInsights(BaseModel):
    yearsExp: str
    education: str
    prevCompanies: str


class CandidateResult(BaseModel):
    id: int
    name: str
    filename: str
    currentRole: str
    experience: str
    location: str
    score: int = Field(ge=0, le=100)
    tier: Literal["S", "A", "B", "C", "D"]
    skills: SkillGroups
    scoreBreakdown: ScoreBreakdown
    insights: CandidateInsights
    summary: str
    flags: list[str] = Field(default_factory=list)
    isHiddenGem: bool
    hiddenGemReason: str

    @field_validator("name", "filename", "currentRole", "experience", "location", "summary")
    @classmethod
    def required_text(cls, value: str) -> str:
        return value.strip() or "Unknown"


class AnalyzeRequest(BaseModel):
    uploadId: str
    jobDescription: str = Field(min_length=20)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "talent-scout.html")


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one resume")
    upload_id = str(uuid.uuid4())
    cached: list[dict[str, str]] = []
    for file in files:
        suffix = Path(file.filename or "resume").suffix.lower()
        if suffix not in {".pdf", ".docx", ".txt"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")
        target = UPLOAD_DIR / f"{upload_id}-{uuid.uuid4().hex}{suffix}"
        target.write_bytes(await file.read())
        cached.append({"filename": file.filename or target.name, "path": str(target)})
    UPLOAD_CACHE[upload_id] = cached
    return {"uploadId": upload_id, "files": [{"filename": item["filename"]} for item in cached]}


@app.post("/api/analyze", response_model=list[CandidateResult])
async def analyze(payload: AnalyzeRequest) -> list[CandidateResult]:
    cached_files = UPLOAD_CACHE.get(payload.uploadId)
    if not cached_files:
        raise HTTPException(status_code=404, detail="Upload cache not found. Please upload resumes again.")
    results = []
    for index, cached in enumerate(cached_files, start=1):
        text = extract_resume_text(Path(cached["path"]))
        results.append(await evaluate_candidate(index, cached["filename"], text, payload.jobDescription))
    results.sort(key=lambda candidate: candidate.score, reverse=True)
    global LAST_RESULTS
    LAST_RESULTS = [candidate.model_dump() for candidate in results]
    return results


@app.get("/api/export-csv")
def export_csv() -> StreamingResponse:
    if not LAST_RESULTS:
        raise HTTPException(status_code=404, detail="No analysis results to export")
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Name", "Filename", "Role", "Experience", "Location", "Score", "Tier", "Matched Skills", "Missing Skills", "Hidden Gem"])
    for row in LAST_RESULTS:
        writer.writerow([
            row["name"], row["filename"], row["currentRole"], row["experience"], row["location"], row["score"], row["tier"],
            ", ".join(row["skills"]["matched"]), ", ".join(row["skills"]["missing"]), row["hiddenGemReason"] if row["isHiddenGem"] else "",
        ])
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=talentscout-results.csv"})


def extract_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        text = extract_pdf_with_pdfplumber(path) or extract_pdf_with_pypdf(path)
    elif path.suffix.lower() == ".docx":
        text = docx2txt.process(str(path)) or ""
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf_with_pdfplumber(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        return ""


def extract_pdf_with_pypdf(path: Path) -> str:
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except Exception:
        return ""


async def evaluate_candidate(candidate_id: int, filename: str, resume_text: str, job_description: str) -> CandidateResult:
    raw = await call_ai_provider(candidate_id, filename, resume_text, job_description)
    raw = raw or heuristic_candidate(candidate_id, filename, resume_text, job_description)
    try:
        return CandidateResult.model_validate(raw)
    except ValidationError:
        return CandidateResult.model_validate(heuristic_candidate(candidate_id, filename, resume_text, job_description))


async def call_ai_provider(candidate_id: int, filename: str, resume_text: str, job_description: str) -> dict[str, Any] | None:
    prompt = build_ai_prompt(candidate_id, filename, resume_text[:12000], job_description[:6000])
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "system", "content": "Return only valid JSON matching the requested schema."}, {"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return None
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            response = client.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"), max_tokens=1800, temperature=0.2, messages=[{"role": "user", "content": prompt}])
            return json.loads(response.content[0].text)
        except Exception:
            return None
    return None


def build_ai_prompt(candidate_id: int, filename: str, resume_text: str, job_description: str) -> str:
    return f"""Evaluate this resume against the job description. Return one JSON object with exactly these keys: id, name, filename, currentRole, experience, location, score, tier, skills, scoreBreakdown, insights, summary, flags, isHiddenGem, hiddenGemReason. Use id {candidate_id} and filename {filename}. Score integers must be 0-100. tier must be S, A, B, C, or D.\n\nJob Description:\n{job_description}\n\nResume Text:\n{resume_text}"""


def heuristic_candidate(candidate_id: int, filename: str, resume_text: str, job_description: str) -> dict[str, Any]:
    resume_lower = resume_text.lower()
    jd_skills = extract_skills(job_description)
    resume_skills = extract_skills(resume_text)
    matched = sorted(set(jd_skills) & set(resume_skills))
    missing = sorted(set(jd_skills) - set(resume_skills))[:8]
    partial = sorted(skill for skill in resume_skills if skill not in matched)[:8]
    years = detect_years(resume_text)
    technical = int((len(matched) / max(len(jd_skills), 1)) * 100)
    experience_score = min(100, 45 + years * 9)
    growth = min(96, 55 + len(resume_skills) * 4 + (10 if "project" in resume_lower else 0))
    domain = int((technical * 0.72) + (min(100, len(resume_text) // 35) * 0.28))
    culture = 82 if re.search(r"collaborat|mentor|stakeholder|cross-functional|lead", resume_lower) else 68
    score = round(technical * 0.36 + experience_score * 0.22 + domain * 0.18 + culture * 0.12 + growth * 0.12)
    hidden_gem = score >= 72 and years <= 3 and len(resume_skills) >= 6
    name = detect_name(resume_text, filename)
    return {
        "id": candidate_id,
        "name": name,
        "filename": filename,
        "currentRole": detect_role(resume_text),
        "experience": f"{years} years" if years else "Not specified",
        "location": detect_location(resume_text),
        "score": max(0, min(100, score)),
        "tier": score_to_tier(score),
        "skills": {"matched": matched[:10], "partial": partial, "missing": missing},
        "scoreBreakdown": {"technicalSkills": technical, "experienceLevel": experience_score, "domainKnowledge": domain, "cultureFit": culture, "growthPotential": growth},
        "insights": {"yearsExp": f"{years} years" if years else "Not specified", "education": detect_education(resume_text), "prevCompanies": detect_companies(resume_text)},
        "summary": f"{name} shows {len(matched)} direct requirement matches. Strongest signals: {', '.join(matched[:4]) or 'general experience'}. Gaps to review: {', '.join(missing[:4]) or 'no major gaps detected'}.",
        "flags": ["hidden-gem"] if hidden_gem else [],
        "isHiddenGem": hidden_gem,
        "hiddenGemReason": "Early-career profile with unusually broad hands-on skill coverage against the role." if hidden_gem else "No hidden-gem pattern detected.",
    }


def extract_skills(text: str) -> list[str]:
    catalog = ["Python", "FastAPI", "Flask", "React", "TypeScript", "JavaScript", "AWS", "Docker", "Kubernetes", "SQL", "PostgreSQL", "MongoDB", "Machine Learning", "NLP", "LLM", "OpenAI", "Anthropic", "Pandas", "Spark", "CI/CD", "Git", "Azure", "GCP", "Django", "Node.js"]
    lower = text.lower()
    return [skill for skill in catalog if skill.lower() in lower]


def detect_years(text: str) -> int:
    matches = [int(match) for match in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", text.lower())]
    return max(matches) if matches else 0


def detect_name(text: str, filename: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if 2 <= len(first.split()) <= 4 and not any(char.isdigit() for char in first):
        return first[:60]
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


def detect_role(text: str) -> str:
    roles = ["Software Engineer", "Data Scientist", "Product Manager", "Frontend Developer", "Backend Developer", "Full Stack Developer", "Machine Learning Engineer", "DevOps Engineer"]
    lower = text.lower()
    return next((role for role in roles if role.lower() in lower), "Candidate")


def detect_location(text: str) -> str:
    match = re.search(r"(?:location|based in)[:\s]+([A-Za-z ,.-]{3,50})", text, re.I)
    return match.group(1).strip(" .,") if match else "Not specified"


def detect_education(text: str) -> str:
    match = re.search(r"(B\.?S\.?|M\.?S\.?|Bachelor|Master|MBA|PhD)[^\n,.]{0,80}", text, re.I)
    return match.group(0).strip() if match else "Not specified"


def detect_companies(text: str) -> str:
    companies = re.findall(r"(?:at|@)\s+([A-Z][A-Za-z0-9& .-]{2,35})", text)
    return ", ".join(dict.fromkeys(company.strip() for company in companies[:4])) or "Not specified"


def score_to_tier(score: int) -> str:
    if score >= 88:
        return "S"
    if score >= 75:
        return "A"
    if score >= 62:
        return "B"
    if score >= 45:
        return "C"
    return "D"
