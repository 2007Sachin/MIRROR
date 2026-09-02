# Interview Planner Agent

## Purpose

The Interview Planner answers: **What evidence does Mirror need to collect during this interview?** It combines non-sensitive candidate profile metadata, Resume Intelligence claims, Claims Graph entities and evidence, Role Intelligence competencies, and interview constraints into structured objectives.

It plans evidence targets. It does not conduct or score the interview.

## Input

The typed input contains the trusted session ID, target role, career stage, configured duration, neutral claim summaries, high-verification-priority IDs, role competencies, canonical projects and skills, and counts of existing evidence. It excludes names, email addresses, raw identity data, and complete resume text.

Candidate-derived text remains untrusted. Instructions embedded in claims, resumes, or job descriptions are data and are never followed.

## Output

Each versioned plan contains objectives and a deterministic coverage summary. Objectives identify their phase, neutral evidence goal, priority, target claim/competency/project IDs, starting question, question intent, expected signals, time budget, suggested probe allowance, starting difficulty, and completion conditions.

Coverage diagnostics remain in backend persistence and logs. The candidate-facing GET response omits that internal quality summary and exposes only the structured plan and objectives.

The initial question is a starting point for a future Interviewer, not a fixed script.

Example sanitized objective:

```json
{
  "objective_id": "sql-ownership",
  "phase": "ROLE_CORE",
  "objective": "Collect evidence of SQL reasoning and personal ownership",
  "priority": "HIGH",
  "target_claim_ids": ["00000000-0000-4000-8000-000000000011"],
  "target_competency_ids": ["00000000-0000-4000-8000-000000000021"],
  "target_project_ids": ["00000000-0000-4000-8000-000000000031"],
  "initial_question": "Walk me through how data moved from source systems into the dashboard.",
  "question_intent": "Establish architecture understanding and personal ownership.",
  "expected_signal": ["implementation detail", "ownership specificity", "SQL reasoning"],
  "time_budget_seconds": 240,
  "max_probes": 2,
  "difficulty_start": "INTERMEDIATE",
  "completion_conditions": ["Candidate explains one concrete design decision"]
}
```

## Deterministic validation

Agent output is advisory until `InterviewPlanningService` validates it. Application code rejects unknown IDs, requires introduction and closing objectives, checks coverage of useful claims and role-critical competencies, caps probes at two, lowers inappropriate beginner difficulty, limits single-project dominance, reserves configured time, normalizes excess objective budgets, and recomputes coverage.

Scores, readiness judgments, marks, and hiring recommendations are forbidden by the schema and prompt.

## Persistence

`interview_plans` stores immutable versions. A partial unique index prevents concurrent duplicate planning, and only one completed version is active. Replanning preserves previous output. RLS permits owner-only reads; service-role operations perform writes.

## Domain relationships

The Claims Graph supplies neutral claims, projects, skills, and evidence references. The Role Competency Map independently supplies role requirements. The Planner chooses evidence targets across both sources.

The deterministic Interview State Machine remains authoritative. Preparation enters `PREPARING`; a session becomes `READY` only after a completed plan exists. The State Machine—not the Planner—controls runtime phases, duration, the two-probe cap, one-turn-late flags, recovery, and termination.

A future Interviewer may adapt wording within an objective. It cannot override these deterministic boundaries.

## Explicit non-responsibilities

The Planner does not authenticate users, query SQL, control permissions, mutate session lifecycle, enforce probes, run Skeptic logic, conduct live conversation, use voice, decide truthfulness, score performance, or terminate a session.

Planning logs contain execution and session IDs, model and prompt versions, claim/competency/objective counts, duration, latency, retries, and success. They exclude complete resumes and transcripts.

