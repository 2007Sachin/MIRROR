from __future__ import annotations

from copy import deepcopy

from .role_models import RoleAgentOutput


def _competency(
    role: str,
    name: str,
    category: str,
    weight: float,
    level: str = "INTERMEDIATE",
) -> dict:
    return {
        "name": name,
        "category": category,
        "importance_weight": weight,
        "expected_level": level,
        "source_type": "SYNTHETIC_CANONICAL",
        "source_reference": f"Synthetic canonical profile v1: {role}",
        "confidence": 0.75,
    }


CANONICAL_ROLE_PROFILES = {
    "data analyst": {
        "canonical_role": "Data Analyst",
        "seniority": "ENTRY_LEVEL",
        "source_type": "SYNTHETIC_CANONICAL",
        "competencies": [
            _competency("Data Analyst", "SQL", "TECHNICAL", 0.95),
            _competency("Data Analyst", "Data visualization", "TOOL", 0.8),
            _competency("Data Analyst", "Analytical reasoning", "ANALYTICAL", 0.95),
            _competency("Data Analyst", "Business communication", "COMMUNICATION", 0.8),
            _competency("Data Analyst", "Project ownership", "BEHAVIOURAL", 0.7),
        ],
        "must_have_skills": ["SQL", "Analytical reasoning", "Data visualization"],
        "nice_to_have_skills": ["Python", "Experimentation"],
        "behavioural_expectations": ["Own analysis from question to recommendation"],
        "domain_expectations": [
            "Translate business questions into measurable analysis"
        ],
        "interview_themes": [
            "SQL",
            "Data visualization",
            "Analytical reasoning",
            "Business communication",
            "Project ownership",
        ],
    },
    "business analyst": {
        "canonical_role": "Business Analyst",
        "seniority": "ENTRY_LEVEL",
        "source_type": "SYNTHETIC_CANONICAL",
        "competencies": [
            _competency(
                "Business Analyst", "Requirements analysis", "ANALYTICAL", 0.95
            ),
            _competency(
                "Business Analyst", "Stakeholder communication", "COMMUNICATION", 0.9
            ),
            _competency("Business Analyst", "Process modelling", "DOMAIN", 0.8),
            _competency("Business Analyst", "Data interpretation", "ANALYTICAL", 0.75),
            _competency("Business Analyst", "Delivery ownership", "BEHAVIOURAL", 0.75),
        ],
        "must_have_skills": [
            "Requirements analysis",
            "Stakeholder communication",
            "Process modelling",
        ],
        "nice_to_have_skills": ["SQL", "Dashboarding"],
        "behavioural_expectations": ["Clarify ambiguity and align stakeholders"],
        "domain_expectations": [
            "Understand workflows, constraints, and business outcomes"
        ],
        "interview_themes": [
            "Requirements discovery",
            "Prioritization",
            "Stakeholder alignment",
            "Process improvement",
        ],
    },
    "software engineer": {
        "canonical_role": "Software Engineer",
        "seniority": "ENTRY_LEVEL",
        "source_type": "SYNTHETIC_CANONICAL",
        "competencies": [
            _competency(
                "Software Engineer", "Programming fundamentals", "TECHNICAL", 0.95
            ),
            _competency(
                "Software Engineer", "Problem decomposition", "ANALYTICAL", 0.9
            ),
            _competency(
                "Software Engineer", "Testing and debugging", "TECHNICAL", 0.85
            ),
            _competency(
                "Software Engineer",
                "System design fundamentals",
                "TECHNICAL",
                0.7,
                "BASIC",
            ),
            _competency(
                "Software Engineer", "Technical communication", "COMMUNICATION", 0.75
            ),
        ],
        "must_have_skills": [
            "Programming fundamentals",
            "Problem decomposition",
            "Testing and debugging",
        ],
        "nice_to_have_skills": ["Cloud platforms", "CI/CD"],
        "behavioural_expectations": [
            "Explain tradeoffs and respond constructively to review"
        ],
        "domain_expectations": [
            "Build maintainable software within product constraints"
        ],
        "interview_themes": [
            "Coding",
            "Debugging",
            "Design tradeoffs",
            "Collaboration",
            "Project ownership",
        ],
    },
    "product analyst": {
        "canonical_role": "Product Analyst",
        "seniority": "ENTRY_LEVEL",
        "source_type": "SYNTHETIC_CANONICAL",
        "competencies": [
            _competency("Product Analyst", "Product metrics", "ANALYTICAL", 0.95),
            _competency("Product Analyst", "SQL", "TECHNICAL", 0.85),
            _competency("Product Analyst", "Experiment analysis", "ANALYTICAL", 0.85),
            _competency("Product Analyst", "Product judgement", "DOMAIN", 0.8),
            _competency(
                "Product Analyst", "Insight communication", "COMMUNICATION", 0.8
            ),
        ],
        "must_have_skills": ["Product metrics", "SQL", "Insight communication"],
        "nice_to_have_skills": ["A/B testing", "Analytics instrumentation"],
        "behavioural_expectations": [
            "Frame ambiguous product questions with measurable outcomes"
        ],
        "domain_expectations": [
            "Connect user behaviour, product changes, and business outcomes"
        ],
        "interview_themes": [
            "Product metrics",
            "Experimentation",
            "SQL",
            "Analytical reasoning",
            "Business communication",
        ],
    },
}

ROLE_ALIASES = {"software developer": "software engineer"}


def load_canonical_role(target_role: str) -> RoleAgentOutput | None:
    key = " ".join(target_role.lower().split())
    key = ROLE_ALIASES.get(key, key)
    value = CANONICAL_ROLE_PROFILES.get(key)
    return RoleAgentOutput.model_validate(deepcopy(value)) if value else None

