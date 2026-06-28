import re


def clean_text(text):
    """Normalize extracted resume/JD text for lightweight NLP matching."""
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", " ", text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"[\u2022\-|\u2013\u2014,;:()\[\]{}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_skills_gap(jd_text, resume_text):
    """Backwards-compatible skill gap helper used by older screens/tests."""
    common_skills = [
        "python", "sql", "java", "tableau", "power bi", "excel", "aws", "azure",
        "machine learning", "deep learning", "nlp", "statistics", "regression",
        "xgboost", "random forest", "pandas", "numpy", "scikit-learn", "git",
        "docker", "mongodb", "react", "node", "fastapi", "llm", "rag",
    ]

    cleaned_jd = clean_text(jd_text)
    cleaned_resume = clean_text(resume_text)
    required_skills = [skill for skill in common_skills if skill in cleaned_jd]

    matched_skills = []
    missing_skills = []
    for skill in required_skills:
        if skill in cleaned_resume:
            matched_skills.append(skill.upper())
        else:
            missing_skills.append(skill.upper())

    return matched_skills, missing_skills
