
# TalentScout: Contextual AI Resume Intelligence & Anti-Bias Screening Pipeline

TalentScout is an enterprise-ready, full-stack resume screening and intelligence application designed to replace archaic keyword-matching Applicant Tracking Systems (ATS). By leveraging semantic analysis and structured LLM evaluation pipelines, TalentScout analyzes the structural context of resumes against a job description. 

A core differentiator of the system is its **Anti-Bias Engine**, which actively bypasses rigid keyword checklists to identify "Hidden Gems"—high-potential career pivoters, bootcamp graduates, or non-traditional candidates possessing exceptional transferable skill matrices.

---

## Architectural Overview

The application enforces a strict separation of concerns, decoupling the client-side user experience from the data extraction and inference layers:

```text
resume-screener-app/
├── src/                    # Core Backend Domain Logic
│   ├── core/
│   │   ├── ats.py          # Applicant tracking matrix algorithms
│   │   ├── extractor.py    # Multi-format document text extraction engine (PDF/DOCX)
│   │   └── preprocessor.py # Text normalization, token hygiene, and sanitization
│   └── ml/                 # Inference Layer & Prompt Engineering Modules
├── static/                 # Production Client Assets
│   └── app.js              # State orchestration and reactive UI rendering logic
├── storage/                # Secure, ephemeral local document caching layer
├── app.py                  # Monolithic Python Application Entry Point & API Gateway
├── requirements.txt        # Managed Python environment dependencies
├── setup.py                # Package distribution configuration
└── talent-scout.html       # Single-Page Recruiter Workspace & Interactive Dashboard
