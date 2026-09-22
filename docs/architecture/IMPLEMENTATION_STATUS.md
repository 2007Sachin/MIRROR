# Mirror implementation status

| Area | Status | Current implementation | Important files | Notes |
|---|---|---|---|---|
| Authentication | COMPLETE | Supabase token verification and owner-scoped profile API | `apps/api/app/auth.py`, `apps/web/src/lib/supabase.ts` | Browser uses public keys only |
| Onboarding | COMPLETE | Persisted five-stage diagnostic construction flow with role/resume intelligence, evidence-map review, inquiry depth, and prepared interview thesis | `apps/api/app/onboarding_repository.py`, `apps/web/src/components/onboarding-flow.tsx` | Legacy completed profiles remain compatible |
| Resume ingestion | COMPLETE | PDF/DOCX validation, Storage upload, document records | `apps/api/app/document_ingestion.py` | Size/type limits configurable |
| JD ingestion | COMPLETE | Pasted or validated PDF/DOCX role-brief documents | `apps/api/app/document_repository.py`, `apps/api/app/main.py` | Private source files and extracted text are persisted |
| Evidence library (My Experience) | COMPLETE | Owner-scoped taxonomy, context, versioned replacement, recoverable archive/restore, download, and diagnostic-usage visibility, grouped into Resume / Work / Projects / Achievements | `apps/api/app/document_library_service.py`, `apps/web/src/components/experience/experience-page.tsx` | Referenced versions are retained so later edits cannot rewrite completed diagnostics |
| Interview planning | COMPLETE | Role/resume-aware plan service and contracts | `apps/api/app/planner_service.py` | Provider-backed behavior depends on configuration |
| Interview orchestration | COMPLETE | Deterministic lifecycle, phases, probes, recovery, events | `apps/api/app/interview_engine.py` | State machine owns transitions |
| Voice/audio | COMPLETE | Validated audio, STT/TTS adapters, storage, retries, metrics | `apps/api/app/voice_service.py` | External provider credentials required |
| Interviewer | COMPLETE | Typed adaptive text/voice turn service | `apps/api/app/interviewer_service.py`, `apps/api/app/agents/interviewer.py` | Candidate-facing turns only |
| Skeptic | COMPLETE | Shadow/live flag processing with delayed activation | `apps/api/app/skeptic_processor.py`, `apps/api/app/flag_activation.py` | Hidden from candidate |
| Evidence extraction | COMPLETE | Validated evidence agent/service | `apps/api/app/evidence_service.py` | No hidden reasoning exposed |
| Claims model | COMPLETE | Claims graph, entities, relations, evidence, versions, resolution | `apps/api/app/claims_service.py`, `apps/api/app/claim_resolution_service.py` | PostgreSQL, not Neo4j |
| Specialist assessors | COMPLETE | Technical, behaviour, and claims contracts/orchestration | `apps/api/app/assessment_orchestrator.py`, `apps/api/app/agents/specialist_assessors.py` | Legacy V1 retained for compatibility |
| Adjudication | COMPLETE | Deterministic disagreement detection plus adjudicator service | `apps/api/app/assessment_adjudication_service.py` | No candidate-facing adjudication language |
| Verdict | COMPLETE | Deterministic aggregation and candidate-safe verdict generation | `apps/api/app/final_assessment_aggregator.py`, `apps/api/app/verdict_service.py` | Ranges, codes, root cause, limitations |
| Post-session assessment | COMPLETE (UNIT TESTED) | Durable Supabase job queue and worker drive specialist assessment through report persistence | `apps/api/app/assessment_worker.py`, `workers/assessor/worker.py` | HTTP completion only queues; worker credentials remain backend-only. Database, provider, and production validation are not yet available in this workspace. |
| Diagnostic report | COMPLETE | Normalized candidate-safe report API/UI | `apps/api/app/report_service.py`, `apps/web/src/app/app/report/[session_id]/page.tsx` | Waits neutrally for the asynchronous result; polished report design may evolve |
| Interview Map | COMPLETE (UNIT TESTED) | Deterministic, derived on read from role analysis, resume analysis, stories and the latest review; no LLM, no stored copy | `apps/api/app/interview_map.py`, `apps/api/app/readiness_service.py`, `apps/web/src/components/roles/interview-map-view.tsx` | `GET /api/v1/roles/{id}/interview-map`. Coverage is word overlap, explained per theme; no scores |
| Resume Pressure Test | COMPLETE (UNIT TESTED) | Follow-up questions derived from what each resume claim leaves open; self-readiness persisted; presence-only answer checks; answers can be saved as a story | `apps/api/app/pressure_test.py`, `supabase/migrations/202609220002_pressure_test_responses.sql`, `apps/web/src/components/roles/pressure-test-page.tsx` | Live Skeptic-driven pressure inside a conversation is Phase 4 |
| My Stories | COMPLETE (UNIT TESTED) | Owner-scoped CRUD, deterministic completeness, guided "Help me find a story", creation from the pressure test; stories count toward map coverage | `apps/api/app/story_models.py`, `apps/api/app/story_repository.py`, `supabase/migrations/202609220001_candidate_stories.sql`, `apps/web/src/components/stories/` | Mirror never writes story content |
| Practice modes, Try again, Interview tomorrow, Debrief | PLANNED | See the readiness plan | `docs/architecture/READINESS_SYSTEM_PLAN.md` | Phase 4 needs a product decision before the engine is extended |
| Analytics | NOT STARTED | No dedicated product analytics pipeline found | — | Voice metrics are operational, not product analytics |
| Observability | PARTIAL | Structured agent logs, session events, voice latency metrics | `apps/api/app/agents/logging.py` | Central dashboards/alerts not found |
| Testing | COMPLETE | Backend pytest suites, synthetic fixtures, frontend TypeScript checks | `apps/api/tests/`, `package.json` | External integrations require configured services |
| Deployment | UNKNOWN | Local dev scripts and Supabase migrations present | `package.json`, `supabase/` | No complete deployment manifest found |

Status is based on repository inspection, not the milestone brief alone. “Complete” means an implementation and tests/contracts exist; it does not imply production provider credentials, calibration, or operational readiness.

