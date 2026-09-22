# Mirror copy audit (Step 1, read-only)

Generated heuristically from source. It lists JSX text, string props, and string literals with a space in them. Some rows are not shown to users (log lines, internal exceptions). Those are marked in the Surface column as error/api and get triaged in Step 3.

## A. Banned-word totals in extracted user-facing strings

| word | count |
|---|---|
| evidence | 204 |
| diagnostic | 52 |
| diagnostics | 22 |
| analysis | 16 |
| assessment | 14 |
| candidate | 12 |
| evaluation | 9 |
| failed | 9 |
| skeptic | 9 |
| evaluating | 6 |
| flag | 5 |
| assessments | 4 |
| audit | 4 |
| gap | 4 |
| tested | 4 |
| evaluates | 3 |
| scored | 3 |
| score | 3 |
| gaps | 3 |
| test | 3 |
| assessor | 3 |
| scores | 2 |
| verify | 2 |
| verdict | 1 |
| verdicts | 1 |
| wrong | 1 |
| analyst | 1 |
| incorrect | 1 |
| proof | 1 |
| performance | 1 |
| proofline | 1 |
| verified | 1 |
| analysed | 1 |
| analysing | 1 |
| evaluated | 1 |
| assessor_type | 1 |

## B. Prompts, docs, README (whole files; banned-word counts)

| file | lines | banned hits | role |
|---|---|---|---|
| README.md | 25 | 14 | README |
| apps/api/app/prompts/adjudicator/v1.md | 3 | 7 | LLM prompt |
| apps/api/app/prompts/assessor/behaviour/v1.md | 3 | 5 | LLM prompt |
| apps/api/app/prompts/assessor/claims/v1.md | 3 | 9 | LLM prompt |
| apps/api/app/prompts/assessor/technical/v1.md | 3 | 3 | LLM prompt |
| apps/api/app/prompts/evidence/v1.md | 16 | 12 | LLM prompt |
| apps/api/app/prompts/framework_test/v1.md | 4 | 0 | LLM prompt |
| apps/api/app/prompts/interviewer/v1.md | 26 | 16 | LLM prompt |
| apps/api/app/prompts/planner/v1.md | 22 | 16 | LLM prompt |
| apps/api/app/prompts/planner/v2.md | 23 | 18 | LLM prompt |
| apps/api/app/prompts/planner/v3.md | 25 | 20 | LLM prompt |
| apps/api/app/prompts/resume/v1.md | 30 | 6 | LLM prompt |
| apps/api/app/prompts/role/v1.md | 32 | 13 | LLM prompt |
| apps/api/app/prompts/skeptic/v1.md | 25 | 11 | LLM prompt |
| apps/api/app/prompts/verdict/v1.md | 2 | 4 | LLM prompt |
| design-qa.md | 46 | 21 | internal doc |
| docs/ai/adjudication.md | 27 | 19 | internal doc |
| docs/ai/evidence-agent.md | 85 | 34 | internal doc |
| docs/ai/interview-planner.md | 67 | 21 | internal doc |
| docs/ai/interviewer-agent.md | 95 | 33 | internal doc |
| docs/ai/resume-agent.md | 69 | 23 | internal doc |
| docs/ai/role-agent.md | 66 | 23 | internal doc |
| docs/ai/skeptic-agent.md | 153 | 55 | internal doc |
| docs/ai/specialist-assessors.md | 29 | 17 | internal doc |
| docs/ai/verdict-agent.md | 6 | 8 | internal doc |
| docs/api/report.md | 61 | 14 | internal doc |
| docs/architecture.md | 101 | 33 | internal doc |
| docs/architecture/IMPLEMENTATION_STATUS.md | 28 | 36 | internal doc |
| docs/architecture/MIRROR_ARCHITECTURE.md | 58 | 38 | internal doc |
| docs/architecture/agents.md | 44 | 14 | internal doc |
| docs/architecture/authentication.md | 34 | 8 | internal doc |
| docs/architecture/claim-resolution.md | 79 | 26 | internal doc |
| docs/architecture/claims-graph.md | 61 | 20 | internal doc |
| docs/architecture/document-ingestion.md | 36 | 7 | internal doc |
| docs/architecture/flag-activation.md | 78 | 29 | internal doc |
| docs/architecture/interview-state-machine.md | 66 | 16 | internal doc |
| docs/architecture/onboarding.md | 71 | 38 | internal doc |
| docs/architecture/post-session-assessment-pipeline.md | 17 | 19 | internal doc |
| docs/architecture/voice-pipeline.md | 148 | 31 | internal doc |
| docs/privacy.md | 11 | 5 | internal doc |
| docs/product/report-ui.md | 17 | 11 | internal doc |
| docs/scoring.md | 11 | 10 | internal doc |
| docs/synthetic-data.md | 17 | 8 | internal doc |
| packages/prompts/assessor/v1.md | 9 | 9 | LLM prompt |
| packages/prompts/interviewer/v1.md | 11 | 8 | LLM prompt |
| packages/prompts/skeptic/v1.md | 9 | 5 | LLM prompt |
| workers/assessor/README.md | 11 | 4 | README |
| workers/skeptic/README.md | 16 | 6 | README |
| workers/tts/README.md | 5 | 1 | README |

## C. Every extracted user-facing string (file, line, text, surface, banned words)

| file | line | current text | surface | banned |
|---|---|---|---|---|
| apps/api/app/agents/base.py | 36 | agent model is required | error/api |  |
| apps/api/app/agents/base.py | 38 | temperature must be between 0 and 2 | error/api |  |
| apps/api/app/agents/base.py | 40 | timeout_seconds must be positive | error/api |  |
| apps/api/app/agents/base.py | 42 | max_retries must not be negative | error/api |  |
| apps/api/app/agents/base.py | 44 | allowed_tools must not contain duplicates | error/api |  |
| apps/api/app/agents/prompts.py | 23 | invalid prompt identifier | error/api |  |
| apps/api/app/agents/providers.py | 76 | Groq is not configured | error/api |  |
| apps/api/app/agents/providers.py | 151 | provider request timed out | error/api |  |
| apps/api/app/agents/providers.py | 157 |  status={exc.response.status_code} body={exc.response.text[:500]} | error/api |  |
| apps/api/app/agents/providers.py | 165 | provider request failed | error/api | failed |
| apps/api/app/agents/registry.py | 16 | agent already registered: {agent.name} | error/api |  |
| apps/api/app/agents/registry.py | 23 | unknown agent: {name} | error/api |  |
| apps/api/app/agents/runner.py | 169 | agent input validation failed | error/api | failed |
| apps/api/app/agents/runner.py | 180 | agent execution timed out | error/api |  |
| apps/api/app/agents/runner.py | 227 | multiple tool-call rounds are not supported | error/api |  |
| apps/api/app/agents/runner.py | 233 | provider returned no structured output | error/api |  |
| apps/api/app/agents/runner.py | 245 | provider output must be a JSON object | error/api |  |
| apps/api/app/agents/tools.py | 43 | tool already registered: {tool.name} | error/api |  |
| apps/api/app/agents/tools.py | 51 | allowed tool is not registered: {name} | error/api |  |
| apps/api/app/agents/tools.py | 68 | tool is not registered: {call.name} | error/api |  |
| apps/api/app/agents/tools.py | 86 | tool execution failed: {call.name} | error/api | failed |
| apps/api/app/assessment_adjudication_repository.py | 16 | adjudication persistence is not configured | error/api |  |
| apps/api/app/assessment_disagreement.py | 14 | material signal gap must be between one and three | error/api | gap |
| apps/api/app/assessment_disagreement.py | 30 | Technical and claims evidence have a material signal-strength gap. | error/api | evidence, gap |
| apps/api/app/assessment_disagreement.py | 37 | Specialist signal availability conflicts and needs interpretation. | error/api |  |
| apps/api/app/assessment_orchestrator.py | 81 | {assessor_type.value} assessor failed | error/api | assessor, assessor_type, failed |
| apps/api/app/assessment_orchestrator.py | 84 | assessor output type mismatch | error/api | assessor |
| apps/api/app/assessment_orchestrator.py | 100 | assessor proposed an untraceable quote | error/api | assessor |
| apps/api/app/assessment_pipeline_repository.py | 35 | assessment persistence is not configured | error/api | assessment |
| apps/api/app/assessment_pipeline_repository.py | 107 | assessment job payload is invalid | error/api | assessment |
| apps/api/app/assessment_pipeline_repository.py | 131 | session is not owned | error/api |  |
| apps/api/app/assessment_worker.py | 89 | poll_seconds must be positive | error/api |  |
| apps/api/app/auth.py | 101 | Authentication required | error/api |  |
| apps/api/app/auth.py | 110 | Invalid or expired access token | error/api |  |
| apps/api/app/auth.py | 116 | Authentication service is temporarily unavailable | error/api |  |
| apps/api/app/claim_resolution_models.py | 38 | extraction corrections must be user corrections | error/api |  |
| apps/api/app/claim_resolution_repository.py | 58 | claim resolution was rejected | error/api |  |
| apps/api/app/claim_resolution_service.py | 55 | claim not found | error/api |  |
| apps/api/app/claim_resolution_service.py | 63 | extraction correction cannot rewrite interview state | error/api |  |
| apps/api/app/claim_resolution_service.py | 65 | illegal claim status transition | error/api |  |
| apps/api/app/claim_resolution_service.py | 80 | corroboration requires unconflicted supporting evidence | error/api | evidence |
| apps/api/app/claim_resolution_service.py | 82 | partial status requires support and weakening evidence | error/api | evidence |
| apps/api/app/claim_resolution_service.py | 87 | walk-back requires explicit narrowing or retraction | error/api |  |
| apps/api/app/claim_resolution_service.py | 91 | contradiction requires strong direct-conflict evidence | error/api | evidence |
| apps/api/app/claim_resolution_service.py | 93 | substantive evidence cannot be marked insufficient | error/api | evidence |
| apps/api/app/claims_models.py | 176 | evidence must reference a turn, document, or quote | error/api | evidence |
| apps/api/app/claims_models.py | 178 | interview-turn evidence requires a turn | error/api | evidence |
| apps/api/app/claims_models.py | 183 | document evidence requires a document | error/api | evidence |
| apps/api/app/claims_repository.py | 98 | Supabase claims storage is not configured | error/api |  |
| apps/api/app/dashboard_repository.py | 27 | dashboard persistence is not configured | error/api |  |
| apps/api/app/dashboard_repository.py | 72 | dashboard data could not be loaded | error/api |  |
| apps/api/app/dependencies.py | 173 | Interview planning is not configured | error/api |  |
| apps/api/app/dependencies.py | 206 | Text interview storage is not configured | error/api |  |
| apps/api/app/dependencies.py | 247 | Skeptic flag activation is not configured | error/api | flag, skeptic |
| apps/api/app/dependencies.py | 269 | Voice persistence is not configured | error/api |  |
| apps/api/app/dependencies.py | 280 | Interview audio storage is not configured | error/api |  |
| apps/api/app/dependencies.py | 300 | Speech transcription is not configured | error/api |  |
| apps/api/app/dependencies.py | 317 | Speech synthesis is not configured | error/api |  |
| apps/api/app/dependencies.py | 357 | Profile service is not configured | error/api |  |
| apps/api/app/dependencies.py | 368 | Onboarding service is not configured | error/api |  |
| apps/api/app/dependencies.py | 379 | Document service is not configured | error/api |  |
| apps/api/app/dependencies.py | 390 | Resume storage is not configured | error/api |  |
| apps/api/app/dependencies.py | 401 | Resume analysis service is not configured | error/api | analysis |
| apps/api/app/dependencies.py | 437 | Role analysis service is not configured | error/api | analysis |
| apps/api/app/dependencies.py | 466 | Claims service is not configured | error/api |  |
| apps/api/app/dependencies.py | 482 | Skeptic persistence is not configured | error/api | skeptic |
| apps/api/app/dependencies.py | 533 | Evidence persistence is not configured | error/api | evidence |
| apps/api/app/dependencies.py | 574 | Specialist assessment persistence is not configured | error/api | assessment |
| apps/api/app/dependencies.py | 608 | Evidence workspace is not configured | error/api | evidence |
| apps/api/app/dependencies.py | 619 | Assessment processing is not configured | error/api | assessment |
| apps/api/app/document_parsing.py | 29 | unsupported resume type | error/api |  |
| apps/api/app/document_parsing.py | 32 | resume contains no extractable text | error/api |  |
| apps/api/app/document_parsing.py | 43 | resume has too many pages | error/api |  |
| apps/api/app/document_parsing.py | 53 | PDF text extraction failed | error/api | failed |
| apps/api/app/document_parsing.py | 60 | DOCX document content is too large | error/api |  |
| apps/api/app/document_parsing.py | 65 | DOCX text extraction failed | error/api | failed |
| apps/api/app/document_repository.py | 63 | Supabase document storage is not configured | error/api |  |
| apps/api/app/document_repository.py | 221 | document update returned no row | error/api |  |
| apps/api/app/document_repository.py | 271 | replacement returned no row | error/api |  |
| apps/api/app/document_repository.py | 299 | Supabase resume storage is not configured | error/api |  |
| apps/api/app/evidence_models.py | 64 | turn evidence must use its turn as source | error/api | evidence |
| apps/api/app/evidence_models.py | 67 | document evidence must use its document as source | error/api | evidence |
| apps/api/app/evidence_models.py | 105 | evidence direction does not match its collection | error/api | evidence |
| apps/api/app/evidence_service.py | 68 | Evidence inference failed | error/api | evidence, failed |
| apps/api/app/evidence_service.py | 71 | Evidence assessment claim does not match | error/api | assessment, evidence |
| apps/api/app/evidence_service.py | 95 | Evidence recommendation validated by deterministic resolution rules | error/api | evidence |
| apps/api/app/flag_activation.py | 70 | Skeptic live-probe confidence must be between zero and one | error/api | skeptic |
| apps/api/app/flag_repository.py | 77 | Eligible flag data is invalid | error/api | flag |
| apps/api/app/interview_engine.py | 62 | interview time budgets must be positive | error/api |  |
| apps/api/app/interview_engine.py | 138 | primary question id is required | error/api |  |
| apps/api/app/interview_engine.py | 154 | a probe requires an active primary question | error/api |  |
| apps/api/app/interview_engine.py | 157 | probe limit reached; recovery is required | error/api |  |
| apps/api/app/interview_engine.py | 197 | recovery is not currently required | error/api |  |
| apps/api/app/interview_engine.py | 213 | interview time budget is exhausted | error/api |  |
| apps/api/app/interview_engine.py | 216 | closing is the final active phase | error/api |  |
| apps/api/app/interview_engine.py | 359 | interview time budget is exhausted | error/api |  |
| apps/api/app/interview_engine.py | 361 | phase time budget is exhausted | error/api |  |
| apps/api/app/interviewer_models.py | 146 | action and turn type do not match | error/api |  |
| apps/api/app/interviewer_models.py | 148 | only transition actions may request a phase | error/api |  |
| apps/api/app/interviewer_models.py | 150 | the state machine controls completion | error/api |  |
| apps/api/app/interviewer_models.py | 163 | candidate response must not be blank | error/api | candidate |
| apps/api/app/interviewer_repository.py | 100 | Supabase turn storage is not configured | error/api |  |
| apps/api/app/interviewer_service.py | 209 | session is not accepting candidate turns | error/api | candidate |
| apps/api/app/main.py | 187 | Choose a supported evidence category | error/api | evidence |
| apps/api/app/main.py | 193 | Evidence title must be between 1 and 160 characters | error/api | evidence |
| apps/api/app/main.py | 202 | This evidence is part of an active diagnostic. Confirm that the change should apply only to future diagnostics. | error/api | diagnostic, diagnostics, evidence |
| apps/api/app/main.py | 227 | Session report not found | error/api |  |
| apps/api/app/main.py | 229 | Session assessment is not complete | error/api | assessment |
| apps/api/app/main.py | 231 | Session report is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 243 | Assessment processing is temporarily unavailable | error/api | assessment |
| apps/api/app/main.py | 245 | Assessment not found | error/api | assessment |
| apps/api/app/main.py | 268 | Assessment retry is temporarily unavailable | error/api | assessment |
| apps/api/app/main.py | 282 | Evidence workspace is temporarily unavailable | error/api | evidence |
| apps/api/app/main.py | 298 | Admin access required | error/api |  |
| apps/api/app/main.py | 300 | Session not found | error/api |  |
| apps/api/app/main.py | 303 | Skeptic inspection is temporarily unavailable | error/api | skeptic |
| apps/api/app/main.py | 326 | Claims service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 339 | Claim not found | error/api |  |
| apps/api/app/main.py | 342 | Claims service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 361 | Profile service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 377 | Profile service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 393 | Onboarding service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 414 | Complete all required onboarding fields before continuing | error/api |  |
| apps/api/app/main.py | 422 | Onboarding service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 439 | Resume must be a PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 444 | Resume upload is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 449 | Resume exceeds the configured file-size limit | error/api |  |
| apps/api/app/main.py | 456 | Resume content does not match an allowed PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 489 | Resume upload is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 510 | Document service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 528 | Role brief must be a PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 533 | Role brief upload is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 538 | Role brief exceeds the configured file-size limit | error/api |  |
| apps/api/app/main.py | 544 | Role brief content does not match an allowed PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 551 | Mirror could not extract text from this role brief | error/api |  |
| apps/api/app/main.py | 588 | Role brief upload is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 605 | Evidence library is temporarily unavailable | error/api | evidence |
| apps/api/app/main.py | 624 | Evidence uploads are not configured | error/api | evidence |
| apps/api/app/main.py | 627 | Evidence must be a PDF or DOCX file | error/api | evidence |
| apps/api/app/main.py | 630 | Evidence exceeds the configured file-size limit | error/api | evidence |
| apps/api/app/main.py | 633 | Evidence content does not match an allowed PDF or DOCX file | error/api | evidence |
| apps/api/app/main.py | 638 | Evidence context cannot exceed 4000 characters | error/api | evidence |
| apps/api/app/main.py | 647 | Mirror could not read this evidence file | error/api | evidence |
| apps/api/app/main.py | 689 | Evidence upload is temporarily unavailable | error/api | evidence |
| apps/api/app/main.py | 703 | Document service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 718 | Document service is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 721 | Document not found | error/api |  |
| apps/api/app/main.py | 735 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 737 | Evidence details are temporarily unavailable | error/api | evidence |
| apps/api/app/main.py | 762 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 764 | Restore this evidence before editing it | error/api | evidence |
| apps/api/app/main.py | 766 | We couldn't update this evidence. Your original details are unchanged. | error/api | evidence |
| apps/api/app/main.py | 786 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 788 | Evidence is already removed from the library | error/api | evidence |
| apps/api/app/main.py | 790 | We couldn't remove this evidence. It remains in your library. | error/api | evidence |
| apps/api/app/main.py | 803 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 805 | We couldn't restore this evidence. Try again. | error/api | evidence |
| apps/api/app/main.py | 818 | Original file not found | error/api |  |
| apps/api/app/main.py | 829 | The original file is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 849 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 851 | Evidence details are temporarily unavailable | error/api | evidence |
| apps/api/app/main.py | 854 | Evidence uploads are not configured | error/api | evidence |
| apps/api/app/main.py | 857 | Evidence must be a PDF or DOCX file | error/api | evidence |
| apps/api/app/main.py | 860 | Evidence exceeds the configured file-size limit | error/api | evidence |
| apps/api/app/main.py | 863 | Evidence content does not match an allowed PDF or DOCX file | error/api | evidence |
| apps/api/app/main.py | 874 | Evidence context cannot exceed 4000 characters | error/api | evidence |
| apps/api/app/main.py | 883 | Mirror could not read the replacement file. Your original file is unchanged. | error/api |  |
| apps/api/app/main.py | 918 | Restore this evidence before replacing its file | error/api | evidence |
| apps/api/app/main.py | 920 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 922 | We couldn't replace this evidence. Your original file is unchanged. | error/api | evidence |
| apps/api/app/main.py | 943 | Evidence not found | error/api | evidence |
| apps/api/app/main.py | 949 | We couldn't remove this evidence. It remains in your library. | error/api | evidence |
| apps/api/app/main.py | 967 | Resume not found | error/api |  |
| apps/api/app/main.py | 969 | Document is not a resume | error/api |  |
| apps/api/app/main.py | 976 | Resume analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 993 | Resume analysis not found | error/api | analysis |
| apps/api/app/main.py | 996 | Document is not a resume | error/api |  |
| apps/api/app/main.py | 999 | Resume analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 1017 | Resume claim not found | error/api |  |
| apps/api/app/main.py | 1019 | Document is not a resume | error/api |  |
| apps/api/app/main.py | 1022 | Resume analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 1038 | Job description document is not available | error/api |  |
| apps/api/app/main.py | 1041 | Role profile not found | error/api |  |
| apps/api/app/main.py | 1044 | Role profile belongs to a different target role | error/api |  |
| apps/api/app/main.py | 1048 | Role analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 1061 | Role profile not found | error/api |  |
| apps/api/app/main.py | 1064 | Role analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 1080 | Role profile not found | error/api |  |
| apps/api/app/main.py | 1083 | Role analysis is temporarily unavailable | error/api | analysis |
| apps/api/app/main.py | 1113 | Document not found | error/api |  |
| apps/api/app/main.py | 1117 | Restore this evidence before using it in a diagnostic | error/api | diagnostic, evidence |
| apps/api/app/main.py | 1125 | Only resume and role-brief documents can be linked | error/api |  |
| apps/api/app/main.py | 1132 | Session not found | error/api |  |
| apps/api/app/main.py | 1135 | Document linking is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1149 | Session not found | error/api |  |
| apps/api/app/main.py | 1161 | Session not found | error/api |  |
| apps/api/app/main.py | 1174 | Resume must be a PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 1177 | Resume upload is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1182 | Resume exceeds the configured file-size limit | error/api |  |
| apps/api/app/main.py | 1188 | Resume content does not match an allowed PDF or DOCX file | error/api |  |
| apps/api/app/main.py | 1214 | Resume storage is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1217 | Private resume storage failed | error/api | failed |
| apps/api/app/main.py | 1222 | Session not found | error/api |  |
| apps/api/app/main.py | 1246 | Interview planning failed | error/api | failed |
| apps/api/app/main.py | 1252 | Session not found | error/api |  |
| apps/api/app/main.py | 1255 | Illegal session transition | error/api |  |
| apps/api/app/main.py | 1259 | Session changed concurrently | error/api |  |
| apps/api/app/main.py | 1263 | Session changed concurrently | error/api |  |
| apps/api/app/main.py | 1268 | Resume and role intelligence are required before planning | error/api |  |
| apps/api/app/main.py | 1272 | Interview planning is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1293 | Session not found | error/api |  |
| apps/api/app/main.py | 1296 | Session is not available for planning | error/api |  |
| apps/api/app/main.py | 1301 | Resume and role intelligence are required before planning | error/api |  |
| apps/api/app/main.py | 1305 | Interview planning is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1318 | Interview plan not found | error/api |  |
| apps/api/app/main.py | 1321 | Interview planning is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1334 | Session not found | error/api |  |
| apps/api/app/main.py | 1337 | Illegal session transition | error/api |  |
| apps/api/app/main.py | 1352 | Session not found | error/api |  |
| apps/api/app/main.py | 1355 | An active interview plan is required | error/api |  |
| apps/api/app/main.py | 1359 | Interview cannot be started | error/api |  |
| apps/api/app/main.py | 1369 | Text interview is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1385 | Session not found | error/api |  |
| apps/api/app/main.py | 1388 | An active interview plan is required | error/api |  |
| apps/api/app/main.py | 1392 | This interview turn is not allowed | error/api |  |
| apps/api/app/main.py | 1396 | Text interview is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1411 | Session not found | error/api |  |
| apps/api/app/main.py | 1414 | An active interview plan is required | error/api |  |
| apps/api/app/main.py | 1418 | Interview cannot be started | error/api |  |
| apps/api/app/main.py | 1426 | Voice interview is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1455 | : exc.code,  | error/api |  |
| apps/api/app/main.py | 1455 | That recording is too large. | error/api |  |
| apps/api/app/main.py | 1460 | : exc.code,  | error/api |  |
| apps/api/app/main.py | 1460 | That audio format is not supported. | error/api |  |
| apps/api/app/main.py | 1465 | : exc.code,  | error/api |  |
| apps/api/app/main.py | 1465 | That recording is too short. | error/api |  |
| apps/api/app/main.py | 1470 | : exc.code,  | error/api |  |
| apps/api/app/main.py | 1470 | That recording could not be read. | error/api |  |
| apps/api/app/main.py | 1477 | We couldn't hear that clearly. Try that answer again. | error/api |  |
| apps/api/app/main.py | 1485 | That recording is still being processed. | error/api |  |
| apps/api/app/main.py | 1489 | Session not found | error/api |  |
| apps/api/app/main.py | 1492 | This interview turn is not allowed | error/api |  |
| apps/api/app/main.py | 1500 | Voice interview is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1513 | Turn not found | error/api |  |
| apps/api/app/main.py | 1516 | Question audio is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1529 | Session not found | error/api |  |
| apps/api/app/main.py | 1532 | Text interview is temporarily unavailable | error/api |  |
| apps/api/app/main.py | 1574 | Session not found | error/api |  |
| apps/api/app/main.py | 1577 | Illegal session transition | error/api |  |
| apps/api/app/main.py | 1581 | Session changed concurrently | error/api |  |
| apps/api/app/main.py | 1584 | Assessment processing is temporarily unavailable | error/api | assessment |
| apps/api/app/onboarding_repository.py | 33 | Supabase onboarding storage is not configured | error/api |  |
| apps/api/app/planner_models.py | 123 | COMPLETE is controlled by the state machine | error/api |  |
| apps/api/app/planner_models.py | 144 | objective ids must be unique | error/api |  |
| apps/api/app/planner_service.py | 70 | planner reserves cannot be negative | error/api |  |
| apps/api/app/planner_service.py | 399 | interview duration is too short | error/api |  |
| apps/api/app/planner_service.py | 445 | objectives cannot fit the configured duration | error/api |  |
| apps/api/app/profile_repository.py | 26 | Supabase profile storage is not configured | error/api |  |
| apps/api/app/resume_models.py | 187 | correct claims cannot include correction text | error/api |  |
| apps/api/app/resume_models.py | 192 | correction text is required | error/api |  |
| apps/api/app/resume_repository.py | 155 | completed analysis could not be read | error/api | analysis |
| apps/api/app/resume_service.py | 141 | resume source is unavailable | error/api |  |
| apps/api/app/resume_service.py | 145 | : DocumentStatus.PROCESSING,  | error/api |  |
| apps/api/app/resume_service.py | 156 | Resume text could not be extracted | error/api |  |
| apps/api/app/resume_service.py | 161 | resume source could not be read | error/api |  |
| apps/api/app/role_models.py | 119 | provide job description text or a document id, not both | error/api |  |
| apps/api/app/role_repository.py | 223 | completed role analysis could not be read | error/api | analysis |
| apps/api/app/schemas.py | 29 | full_name must not be blank | error/api |  |
| apps/api/app/schemas.py | 135 | evidence title must not be blank | error/api | evidence |
| apps/api/app/schemas.py | 148 | at least one evidence field is required | error/api | evidence |
| apps/api/app/schemas.py | 191 | job description must not be blank | error/api |  |
| apps/api/app/schemas.py | 202 | document_ids must be unique | error/api |  |
| apps/api/app/schemas.py | 254 | target_role must contain at least two characters | error/api |  |
| apps/api/app/schemas.py | 273 | inquiry_depth values must be unique | error/api |  |
| apps/api/app/schemas.py | 275 | complete readiness cannot be combined with another depth | error/api |  |
| apps/api/app/schemas.py | 281 | at least one onboarding field is required | error/api |  |
| apps/api/app/schemas.py | 502 | scored rows require every numeric dimension | error/api | scored |
| apps/api/app/schemas.py | 504 | scored rows require candidate evidence and turn ids | error/api | candidate, evidence, scored |
| apps/api/app/schemas.py | 515 | not_enough_signal rows must not contain numeric scores | error/api | scores |
| apps/api/app/schemas.py | 526 | low must not exceed high | error/api |  |
| apps/api/app/skeptic_models.py | 146 | duplicate observations are not allowed | error/api |  |
| apps/api/app/skeptic_processor.py | 69 | invalid Skeptic structured output | error/api | skeptic |
| apps/api/app/skeptic_processor.py | 98 | Skeptic shadow analysis extracted a spoken claim | error/api | analysis, skeptic |
| apps/api/app/skeptic_processor.py | 200 | new claim source is outside current turn | error/api |  |
| apps/api/app/skeptic_processor.py | 202 | new claim references unknown entities | error/api |  |
| apps/api/app/skeptic_processor.py | 205 | claim update references unknown context | error/api |  |
| apps/api/app/skeptic_processor.py | 208 | observation source is outside current turn | error/api |  |
| apps/api/app/skeptic_processor.py | 210 | observation references unknown claims | error/api |  |
| apps/api/app/skeptic_processor.py | 212 | observation references unknown turns | error/api |  |
| apps/api/app/skeptic_processor.py | 215 | flag source is outside current turn | error/api | flag |
| apps/api/app/skeptic_processor.py | 217 | flag references unknown claim | error/api | flag |
| apps/api/app/skeptic_processor.py | 219 | flag references unknown turns | error/api | flag |
| apps/api/app/skeptic_repository.py | 124 | Skeptic persistence is not configured | error/api | skeptic |
| apps/api/app/skeptic_repository.py | 156 | Skeptic job payload is invalid | error/api | skeptic |
| apps/api/app/skeptic_repository.py | 166 | Skeptic job payload is invalid | error/api | skeptic |
| apps/api/app/skeptic_repository.py | 179 | Candidate turn no longer exists | error/api | candidate |
| apps/api/app/skeptic_worker.py | 71 | job and context session do not match | error/api |  |
| apps/api/app/skeptic_worker.py | 158 | poll_seconds must be positive | error/api |  |
| apps/api/app/specialist_assessor_models.py | 49 | not-enough-signal assessments must have no signal strength | error/api | assessments |
| apps/api/app/specialist_assessor_models.py | 51 | completed assessments require evidence turns | error/api | assessments, evidence |
| apps/api/app/specialist_assessor_models.py | 53 | evidence quotes must reference declared turns | error/api | evidence |
| apps/api/app/specialist_assessor_models.py | 72 | not-enough-signal output cannot claim evidence | error/api | evidence |
| apps/api/app/specialist_assessor_models.py | 74 | complete output requires evidence | error/api | evidence |
| apps/api/app/specialist_assessor_models.py | 77 | output quotes must reference evidence turns | error/api | evidence |
| apps/api/app/speech_providers.py | 60 | Deepgram is not configured | error/api |  |
| apps/api/app/speech_providers.py | 155 | Sarvam is not configured | error/api |  |
| apps/api/app/speech_providers.py | 173 | Sarvam response did not include a transcript | error/api |  |
| apps/api/app/speech_providers.py | 233 | Sarvam is not configured | error/api |  |
| apps/api/app/speech_providers.py | 255 | empty TTS audio | error/api |  |
| apps/api/app/voice_repository.py | 68 | Interview audio storage is not configured | error/api |  |
| apps/api/app/voice_repository.py | 124 | Voice persistence is not configured | error/api |  |
| apps/api/app/voice_repository.py | 210 | owned turn not found | error/api |  |
| apps/api/app/voice_service.py | 108 | opening turn was not stored | error/api |  |
| apps/api/app/voice_service.py | 142 | session is not accepting candidate turns | error/api | candidate |
| apps/api/app/voice_service.py | 251 | candidate turn was not stored | error/api | candidate |
| apps/api/app/voice_service.py | 254 | interviewer turn was not stored | error/api |  |
| apps/api/app/voice_service.py | 414 | unsupported synthesized audio type | error/api |  |
| apps/web/src/app/app/loading.tsx | 3 | shell py-20 text-sm text-[var(--silver)] | other |  |
| apps/web/src/app/app/loading.tsx | 4 | Loading Mirror… | other |  |
| apps/web/src/app/app/page.tsx | 12 | Mirror could not load your onboarding status. Refresh to try again. | other |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 28 | Held | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 29 | Partially held | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 30 | Walked back | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 31 | Contradicted / unsupported | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 32 | Not enough evidence | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 33 | Unverified | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 40 | STRONG_EVIDENCE: "Strong evidence", | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 40 | Strong evidence | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 41 | RECOVERY: "Recovered after hesitation", | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 41 | Recovered after hesitation | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 42 | OWNERSHIP_CLARIFICATION: "Ownership became clearer", | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 42 | Ownership became clearer | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 43 | Metric could not be substantiated | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 43 | UNSUPPORTED_SCALE: "Metric could not be substantiated", | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 44 | TECHNICAL_DEPTH: "Technical depth", | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 44 | Technical depth | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 53 | Partially held | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 54 | Not enough evidence | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 74 | No linked evidence was captured. | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 89 | Source document | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 122 | Not enough signal | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 159 | We could not find that report. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 160 | Mirror could not load this report. Check your connection and try again. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 183 | Your interview has been saved. Mirror couldn't finish evaluating the evidence, so the assessment can be retried without repeating the interview. | report/session | assessment, evaluating, evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 193 | Your assessment is taking longer than expected. Please return shortly to check the report. | report/session | assessment |
| apps/web/src/app/app/report/[session_id]/page.tsx | 218 | Mirror could not retry this evaluation. | report/session | evaluation |
| apps/web/src/app/app/report/[session_id]/page.tsx | 231 | Loading report | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 246 | Evaluating evidence | report/session | evaluating, evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 248 | Mirror is examining your answers against your claims, available | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 252 | Return to your evidence workspace | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 266 | We couldn't complete the diagnostic | report/session | diagnostic |
| apps/web/src/app/app/report/[session_id]/page.tsx | 267 | Diagnostic unavailable | report/session | diagnostic |
| apps/web/src/app/app/report/[session_id]/page.tsx | 278 | Requesting retry… | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 278 | Retry evaluation | report/session | evaluation |
| apps/web/src/app/app/report/[session_id]/page.tsx | 282 | Return to your evidence workspace | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 296 | Report navigation | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 304 | Your verdict | report/session | verdict |
| apps/web/src/app/app/report/[session_id]/page.tsx | 312 | Readiness | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 313 | Two signals, kept separate. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 316 | Role readiness | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 318 | Interview readiness | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 323 | Shown as a range with a stated signal strength, not a single | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 332 | Evidence record | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 333 | What held under questioning | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 335 | Claims are shown as evidence records, not verdicts about you. | report/session | evidence, verdicts |
| apps/web/src/app/app/report/[session_id]/page.tsx | 336 | Start with what the interview supported. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 361 | Source | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 362 | Explanation | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 374 | No claims were available for this interview. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 381 | Capability evidence | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 382 | Skill evidence | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 395 | Not enough signal | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 411 | Skill-level evidence will appear here when available. | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 418 | Replay markers | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 419 | Session moments | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 442 | No time-linked moments were recorded. | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 449 | Your main bottleneck | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 457 | Mirror selected one primary area from the evidence in this | report/session | evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 469 | What this result means, and what it doesn’t | report/session |  |
| apps/web/src/app/app/report/[session_id]/page.tsx | 471 | Mirror evaluates evidence captured in this interview. | report/session | evaluates, evidence |
| apps/web/src/app/app/report/[session_id]/page.tsx | 473 | AI assessments can make mistakes, and you may challenge an | report/session | assessments |
| apps/web/src/app/app/report/[session_id]/page.tsx | 476 | Skills with too little evidence are not scored. | report/session | evidence, scored |
| apps/web/src/app/app/setup/page.tsx | 10 | Mirror could not load setup. Refresh to try again. | onboarding |  |
| apps/web/src/app/layout.tsx | 6 | Mirror by Pathwisse | landing/meta |  |
| apps/web/src/app/layout.tsx | 7 | An evidence-backed interview diagnostic and claims audit. | landing/meta | audit, diagnostic, evidence |
| apps/web/src/app/layout.tsx | 18 | Skip to content | landing/meta |  |
| apps/web/src/app/layout.tsx | 20 | Mirror | landing/meta |  |
| apps/web/src/app/layout.tsx | 20 | display text-lg font-semibold tracking-[-0.03em] | landing/meta |  |
| apps/web/src/app/layout.tsx | 21 | by Pathwisse | landing/meta |  |
| apps/web/src/app/login/page.tsx | 5 | Loading sign in… | auth |  |
| apps/web/src/app/login/page.tsx | 5 | shell py-20 text-[var(--silver)] | auth |  |
| apps/web/src/app/onboarding/loading.tsx | 6 | Diagnostic context | onboarding | diagnostic |
| apps/web/src/app/onboarding/loading.tsx | 6 | Restoring | onboarding |  |
| apps/web/src/app/onboarding/loading.tsx | 9 | Returning to your work | onboarding |  |
| apps/web/src/app/onboarding/loading.tsx | 10 | Restoring your diagnostic context. | onboarding | diagnostic |
| apps/web/src/app/onboarding/loading.tsx | 11 | Mirror is retrieving the role benchmark, starting evidence, and last completed stage. | onboarding | evidence |
| apps/web/src/app/onboarding/loading.tsx | 16 | Mirror is building | onboarding |  |
| apps/web/src/app/onboarding/loading.tsx | 17 | Your diagnostic | onboarding | diagnostic |
| apps/web/src/app/onboarding/page.tsx | 16 | Diagnostic unavailable | onboarding | diagnostic |
| apps/web/src/app/onboarding/page.tsx | 17 | Mirror could not restore your saved context. | onboarding |  |
| apps/web/src/app/onboarding/page.tsx | 18 | Your completed work has not been removed. Refresh the page to try the secure connection again. | onboarding |  |
| apps/web/src/app/onboarding/page.tsx | 21 | Mirror is building | onboarding |  |
| apps/web/src/app/onboarding/page.tsx | 21 | Your diagnostic | onboarding | diagnostic |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 9 | Questions are based on your resume, target role, and answers. | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 10 | Mirror may return to something you said earlier. | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 11 | The final report uses evidence captured during this interview. | report/session | evidence |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 12 | Thin evidence appears as Not enough signal rather than a guessed score. | report/session | evidence, score |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 13 | You can disagree with individual assessments after the session. | report/session | assessments |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 16 | shell py-12 sm:py-20 | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 18 | Session prepared | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 19 | Before we begin | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 19 | display mt-4 text-5xl font-semibold tracking-[-0.055em] | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 21 | Some answers may be challenged or revisited. This does not automatically mean Mirror has concluded you were wrong. | report/session | wrong |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 32 | Begin interview | report/session |  |
| apps/web/src/app/sessions/[id]/brief/page.tsx | 34 | Allow about 20 minutes. No scores or coaching appear during the interview. | report/session | scores |
| apps/web/src/app/sessions/layout.tsx | 12 | Mirror could not verify your setup. Refresh to try again. | landing/meta | verify |
| apps/web/src/app/sessions/new/page.tsx | 22 | Reading the job description | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 23 | Benchmarking the role | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 24 | Uploading your resume | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 25 | Mapping your evidence | workspace | evidence |
| apps/web/src/app/sessions/new/page.tsx | 26 | Preparing your diagnostic | workspace | diagnostic |
| apps/web/src/app/sessions/new/page.tsx | 53 | Choose a PDF or DOCX resume. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 80 | Mirror could not finish the role benchmark. Try again in a moment. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 106 | Mirror could not extract enough text from this resume. Try a text-based PDF or DOCX file. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 107 | Mirror could not build the evidence map from this resume. Try again in a moment. | workspace | evidence |
| apps/web/src/app/sessions/new/page.tsx | 111 | Evidence mapping is still in progress. Try again in a moment. | workspace | evidence |
| apps/web/src/app/sessions/new/page.tsx | 121 | Your session expired. Please sign in again. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 122 | The session could not be created. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 130 | shell py-12 sm:py-16 | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 131 | grid gap-12 lg:grid-cols-[.72fr_1.28fr] | workspace | gap |
| apps/web/src/app/sessions/new/page.tsx | 133 | New diagnostic | workspace | diagnostic |
| apps/web/src/app/sessions/new/page.tsx | 134 | Give Mirror the evidence it needs. | workspace | evidence |
| apps/web/src/app/sessions/new/page.tsx | 134 | display mt-4 text-4xl font-semibold tracking-[-0.05em] sm:text-5xl | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 135 | Your resume sets the claims to examine. The job description sets the competencies to investigate. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 138 | Resumes and interview data are isolated per candidate and are not intentionally used to train third-party models. | workspace | candidate |
| apps/web/src/app/sessions/new/page.tsx | 142 | space-y-7 border-t hairline pt-7 | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 144 | Target role | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 145 | Data Analyst | workspace | analyst |
| apps/web/src/app/sessions/new/page.tsx | 148 | Resume | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 149 | field flex cursor-pointer items-center gap-3 text-[var(--silver)] | workspace | gap |
| apps/web/src/app/sessions/new/page.tsx | 155 | Job description | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 156 | Paste the responsibilities, requirements, and role context. | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 156 | field min-h-56 resize-y | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 171 | Mirror is benchmarking the role and mapping your evidence against it. This usually takes under a minute. | workspace | evidence |
| apps/web/src/app/sessions/new/page.tsx | 182 | sn-pipeline-dot live-dot | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 195 | Continue to pre-brief | workspace |  |
| apps/web/src/app/sessions/new/page.tsx | 195 | Preparing diagnostic... | workspace | diagnostic |
| apps/web/src/app/signup/page.tsx | 5 | Loading sign up… | auth |  |
| apps/web/src/app/signup/page.tsx | 5 | shell py-20 text-[var(--silver)] | auth |  |
| apps/web/src/components/auth-form.tsx | 23 | The email or password is incorrect, or the email is not confirmed. | auth | incorrect |
| apps/web/src/components/auth-form.tsx | 25 | An account already exists for this email. Try signing in instead. | auth |  |
| apps/web/src/components/auth-form.tsx | 27 | Choose a stronger password with at least eight characters. | auth |  |
| apps/web/src/components/auth-form.tsx | 29 | Too many attempts. Wait a few minutes and try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 31 | New account creation is temporarily unavailable. | auth |  |
| apps/web/src/components/auth-form.tsx | 33 | We could not complete authentication. Check your details and try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 44 | Google sign-in could not be completed. Please try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 46 | Authentication is not configured for this environment. | auth |  |
| apps/web/src/components/auth-form.tsx | 48 | Mirror could not reach the authentication service. Check your connection and try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 50 | Your session is no longer active. Please sign in again. | auth |  |
| apps/web/src/components/auth-form.tsx | 61 | Authentication is not configured for this environment. | auth |  |
| apps/web/src/components/auth-form.tsx | 86 | Check your email to confirm your account, then return here to sign in. | auth |  |
| apps/web/src/components/auth-form.tsx | 92 | Mirror could not reach the authentication service. Check your connection and try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 99 | Authentication is not configured for this environment. | auth |  |
| apps/web/src/components/auth-form.tsx | 109 | Mirror could not reach Google sign-in. Check your connection and try again. | auth |  |
| apps/web/src/components/auth-form.tsx | 120 | Mirror / Evidence pipeline | auth | evidence |
| apps/web/src/components/auth-form.tsx | 122 | Find the evidence behind your experience. | auth | evidence |
| apps/web/src/components/auth-form.tsx | 126 | mirror-auth-panel-inner fade-in-once | auth |  |
| apps/web/src/components/auth-form.tsx | 127 | Private candidate access | auth | candidate |
| apps/web/src/components/auth-form.tsx | 128 | display mirror-auth-title | auth |  |
| apps/web/src/components/auth-form.tsx | 129 | Create your account | auth |  |
| apps/web/src/components/auth-form.tsx | 129 | Sign in to Mirror | auth |  |
| apps/web/src/components/auth-form.tsx | 133 | Continue your evidence-backed interview preparation. | auth | evidence |
| apps/web/src/components/auth-form.tsx | 134 | Start a private, evidence-backed interview diagnostic. | auth | diagnostic, evidence |
| apps/web/src/components/auth-form.tsx | 146 | Full name | auth |  |
| apps/web/src/components/auth-form.tsx | 151 | Email | auth |  |
| apps/web/src/components/auth-form.tsx | 155 | Password | auth |  |
| apps/web/src/components/auth-form.tsx | 159 | mirror-auth-message is-notice | auth |  |
| apps/web/src/components/auth-form.tsx | 162 | Create account | auth |  |
| apps/web/src/components/auth-form.tsx | 162 | Please wait… | auth |  |
| apps/web/src/components/auth-form.tsx | 182 | Already have an account? | auth |  |
| apps/web/src/components/auth-form.tsx | 182 | New to Mirror? | auth |  |
| apps/web/src/components/auth-form.tsx | 184 | Create an account | auth |  |
| apps/web/src/components/auth-form.tsx | 187 | Set the public Supabase URL and publishable/anonymous key to enable authentication. | auth |  |
| apps/web/src/components/auth/animated-energy-mesh.tsx | 47 | Claim source | auth |  |
| apps/web/src/components/auth/animated-energy-mesh.tsx | 48 | Target role | auth |  |
| apps/web/src/components/auth/animated-energy-mesh.tsx | 49 | Interview evidence | auth | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 45 | Your evidence workspace | workspace | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 46 | Continue where you left off, explore new opportunities, or strengthen your existing evidence. | workspace | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 57 | Loading evidence workspace | workspace | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 98 | Mirror could not load your evidence workspace. Your saved interviews have not been removed. | workspace | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 157 | Mirror could not retry this evaluation. | workspace | evaluation |
| apps/web/src/components/evidence-dashboard.tsx | 174 | Retry | workspace |  |
| apps/web/src/components/evidence-dashboard.tsx | 183 | Your first diagnostic | workspace | diagnostic |
| apps/web/src/components/evidence-dashboard.tsx | 184 | Build your first evidence case. | workspace | evidence |
| apps/web/src/components/evidence-dashboard.tsx | 185 | Give Mirror a role and the professional evidence you want tested. Mirror will identify what appears convincing, what remains uncertain, and where an interview needs to pr | workspace | evidence, tested |
| apps/web/src/components/evidence-dashboard.tsx | 186 | Start a diagnostic | workspace | diagnostic |
| apps/web/src/components/evidence-dashboard.tsx | 204 | Evaluation is taking longer than usual. You can leave this page and return later; Mirror will keep your interview saved. | workspace | evaluation |
| apps/web/src/components/landing-story.tsx | 11 | Skills need evidence | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 12 | Skills-based hiring shifts attention from titles alone toward demonstrated capability. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 13 | LinkedIn Economic Graph, 2025 | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 17 | Structure matters | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 18 | Job-relevant, structured interviews have stronger evidence than unstructured conversation. | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 19 | McDaniel et al., 1994 | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 23 | Polish is not proof | landing/meta | proof |
| apps/web/src/components/landing-story.tsx | 24 | A polished application cannot by itself show ownership, scope, or the basis for an outcome. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 25 | Mirror product framing | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 31 | Claims become starting points. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 31 | Resume | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 32 | Requirements set the context. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 32 | Target role | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 33 | Adaptive interview | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 33 | Follow-ups seek useful detail. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 34 | Evidence audit | landing/meta | audit, evidence |
| apps/web/src/components/landing-story.tsx | 34 | Support and uncertainty stay visible. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 35 | Findings become next actions. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 35 | Readiness diagnostic | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 39 | What did you personally own? | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 40 | How was the 18% calculated? | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 41 | Not enough signal | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 41 | What was the baseline? | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 42 | Who else contributed? | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 46 | what you personally owned | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 47 | the size and boundaries of the work | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 48 | outcomes and supporting measures | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 49 | whether the account holds across answers | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 50 | Role relevance | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 50 | connection to the target role | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 51 | clarity under probing | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 52 | Evidence strength | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 52 | what the session can support | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 56 | Generic or fixed | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 57 | Claims become traceable starting points | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 57 | Often treated as background | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 58 | Clarify ownership, scope, and measurement | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 58 | May stop at the first answer | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 59 | General feedback or a score | landing/meta | score |
| apps/web/src/components/landing-story.tsx | 60 | Often compressed away | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 60 | Shown when signal is insufficient | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 64 | No live performance score during the interview. | landing/meta | performance, score |
| apps/web/src/components/landing-story.tsx | 65 | Findings point to evidence from the session. | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 66 | Not enough signal is a valid outcome. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 68 | Mirror is a diagnostic, not a hiring authority. | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 80 | Evidence-backed interview diagnostic | landing/meta | diagnostic, evidence |
| apps/web/src/components/landing-story.tsx | 81 | Know what your resume can defend. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 81 | ld-hero-title display | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 83 | Mirror maps your resume against a target role, then uses an adaptive interview to produce an | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 94 | Resume + target role + adaptive interview + evidence audit | landing/meta | audit, evidence |
| apps/web/src/components/landing-story.tsx | 94 | ld-hero-proofline mono | landing/meta | proofline |
| apps/web/src/components/landing-story.tsx | 98 | Illustrative evidence diagnostic example | landing/meta | diagnostic, evidence |
| apps/web/src/components/landing-story.tsx | 101 | Illustrative diagnostic | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 102 | Evidence trace | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 106 | Claim | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 107 | &ldquo;Improved checkout conversion by 18%.&rdquo; | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 111 | Follow-up | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 112 | What part of the experiment did you personally own? | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 116 | Evidence | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 118 | Direct | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 118 | Ownership | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 119 | Metric support | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 119 | Partial | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 120 | Scope | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 120 | Verified | landing/meta | verified |
| apps/web/src/components/landing-story.tsx | 121 | Outcome evidence | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 121 | Supported | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 126 | Diagnostic | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 128 | 72&ndash;80% | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 128 | Role readiness | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 129 | 64&ndash;73% | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 129 | Interview readiness | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 140 | shell ld-section-grid | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 142 | The problem | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 143 | The resume is still the entry point. But it is no longer enough. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 168 | How Mirror works | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 169 | A connected trail from claim to diagnostic. | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 186 | shell ld-two-col | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 188 | A claim under questioning | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 189 | Precision arrives one question at a time. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 191 | Mirror does not decide whether a person is truthful. It asks for enough context to understand what an | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 196 | &ldquo;Improved checkout conversion by 18%.&rdquo; | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 212 | shell ld-two-col | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 214 | What Mirror evaluates | landing/meta | evaluates |
| apps/web/src/components/landing-story.tsx | 215 | Not confidence. The evidence behind it. | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 236 | Illustrative diagnostic | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 239 | Role readiness | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 240 | 72&ndash;80% | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 241 | Evidence supports several target-role claims. | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 244 | Interview readiness | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 245 | 64&ndash;73% | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 246 | Ownership and baseline need more precision. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 249 | Claims audit | landing/meta | audit |
| apps/web/src/components/landing-story.tsx | 250 | 1 supported &middot; 1 partial &middot; 1 needs signal | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 253 | Recommended action | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 254 | Practice explaining baseline, ownership, and scope. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 265 | Not another generic mock interview | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 266 | A diagnostic has a different job. | landing/meta | diagnostic |
| apps/web/src/components/landing-story.tsx | 267 | Mirror compared with a generic mock interview | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 269 | Approach | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 270 | Mirror | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 271 | Generic mock interview | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 288 | shell ld-two-col | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 290 | Trust and limits | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 291 | Useful signal should remain accountable. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 305 | shell ld-final-inner | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 307 | Start with the evidence | landing/meta | evidence |
| apps/web/src/components/landing-story.tsx | 308 | Know what holds before the interview asks. | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 322 | shell ld-footer-inner | landing/meta |  |
| apps/web/src/components/landing-story.tsx | 323 | Mirror evaluates evidence from this session. AI can make mistakes. Outcome validation is still in progress. | landing/meta | evaluates, evidence |
| apps/web/src/components/landing-story.tsx | 324 | by Pathwisse | landing/meta |  |
| apps/web/src/components/mirror-lens.tsx | 5 | ld-lens-ring ld-lens-ring-one | other |  |
| apps/web/src/components/mirror-lens.tsx | 6 | ld-lens-ring ld-lens-ring-two | other |  |
| apps/web/src/components/mirror-lens.tsx | 7 | ld-lens-ring ld-lens-ring-three | other |  |
| apps/web/src/components/mirror-lens.tsx | 9 | ld-lens-node ld-lens-node-a | other |  |
| apps/web/src/components/mirror-lens.tsx | 10 | ld-lens-node ld-lens-node-b | other |  |
| apps/web/src/components/mirror-orb.tsx | 102 | relative mx-auto flex min-h-[26rem] w-full max-w-[31rem] items-center justify-center | session |  |
| apps/web/src/components/mirror-orb.tsx | 103 | Mirror voice orb | session |  |
| apps/web/src/components/onboarding-flow.tsx | 46 | Reading your experience | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 47 | Mapping claims to role expectations | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 48 | Identifying evidence gaps | onboarding | evidence, gaps |
| apps/web/src/components/onboarding-flow.tsx | 49 | Preparing lines of inquiry | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 53 | Connecting claims to role demands | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 54 | Prioritising unresolved evidence | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 55 | Building adaptive lines of inquiry | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 56 | Preparing the interview thesis | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 67 | Evidence behind my claims | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 68 | Can I substantiate the achievements and responsibilities on my resume? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 72 | Depth of role knowledge | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 73 | Do I understand the role beyond terminology and frameworks? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 77 | Decision quality | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 78 | Can I explain how I approached ambiguous problems and made trade-offs? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 82 | Ownership and impact | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 83 | Can I separate what I personally contributed from what the team accomplished? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 87 | Communication under scrutiny | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 88 | Can I explain my thinking clearly when challenged? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 92 | Complete readiness assessment | onboarding | assessment |
| apps/web/src/components/onboarding-flow.tsx | 93 | Let Mirror decide where deeper questioning is warranted. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 101 | Why Mirror needs this | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 215 | Mirror could not restore your saved diagnostic context. Refresh to try again. | onboarding | diagnostic |
| apps/web/src/components/onboarding-flow.tsx | 265 | Establishing the role benchmark | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 269 | Opening the evidence interview | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 286 | Mirror could not save this part of your diagnostic. Check your connection and try again. | onboarding | diagnostic |
| apps/web/src/components/onboarding-flow.tsx | 344 | Upload or paste a role brief, or continue without one. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 354 | Paste the role brief or choose to continue without one. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 373 | Mirror could not finish the role benchmark yet. Try again in a moment. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 421 | Resume uploaded — ${document.original_filename ?? file.name}. Continue to build your evidence map. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 440 | Mirror could not extract enough text from this resume. Try a text-based PDF or DOCX file. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 446 | Evidence mapping is still in progress. Try again in a moment. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 466 | Describe the correction before saving it. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 482 | Mirror could not save that correction. Try again. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 557 | Mirror needs completed role and resume analysis before it can prepare the inquiry plan. | onboarding | analysis |
| apps/web/src/components/onboarding-flow.tsx | 559 | Interview planning is temporarily unavailable. Your role and evidence map remain saved. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 561 | Mirror could not prepare the interview thesis. Check your connection and try again. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 586 | Role benchmark | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 587 | Define the role you're aiming at. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 588 | Set the benchmark Mirror should use. Add the employer's brief when you have it, or continue with a role-level benchmark. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 592 | Target role | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 593 | Product Manager | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 596 | Company | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 596 | Optional | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 597 | Company name | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 602 | Role context | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 603 | Add the role brief | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 604 | Use the employer's brief to make the interview specific to this opportunity. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 614 | Continue without one | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 620 | Role brief | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 621 | Paste the responsibilities, expectations, and role context. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 625 | Role brief uploaded | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 630 | Upload complete. Extracting the role text… | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 632 | Role brief upload | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 637 | The role brief tells Mirror which expectations matter for this specific opportunity. Without one, Mirror uses a role-level benchmark and labels that limitation. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 642 | Continue to evidence | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 642 | Establishing benchmark | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 653 | Starting evidence | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 654 | Establish your starting evidence. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 655 | Your resume gives Mirror the claims, experience, and outcomes the interview should examine. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 659 | Resume | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 660 | Add my resume | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 660 | Resume uploaded | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 664 | Replace resume | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 671 | Upload complete. Saving to your evidence library… | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 673 | Resume upload | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 683 | Your resume establishes the claims Mirror will attempt to verify through evidence and questioning. | onboarding | evidence, verify |
| apps/web/src/components/onboarding-flow.tsx | 687 | Building your evidence map | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 689 | Mirror is connecting your experience to the role and deciding where deeper questioning could separate stated experience from demonstrated ability. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 715 | Evidence map | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 716 | This is the case your resume currently makes. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 717 | Review what Mirror inferred. Correct anything inaccurate before the diagnostic starts. | onboarding | diagnostic |
| apps/web/src/components/onboarding-flow.tsx | 722 | Role benchmark | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 724 | Specific role brief | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 727 | Capability signals | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 730 | No explicit capability signals were extracted. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 734 | Claims worth examining | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 741 | Confirmed by you | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 741 | Correction saved | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 744 | Accurate | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 745 | Correct | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 749 | What should this claim say? | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 752 | Cancel | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 753 | Save correction | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 753 | Saving correction | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 759 | Mirror found no sufficiently specific claims to display. You can replace the resume or retry analysis. | onboarding | analysis |
| apps/web/src/components/onboarding-flow.tsx | 763 | What documents cannot establish | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 764 | These are role expectations not clearly established by resume wording alone. They are questions for the interview, not judgments about ability. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 767 | Mirror will use the interview to test depth, ownership, and reasoning behind the visible claims. | onboarding | test |
| apps/web/src/components/onboarding-flow.tsx | 774 | Correct something | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 775 | This reflects my experience | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 786 | Depth of inquiry | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 787 | Decide where Mirror should probe deepest. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 788 | Choose where questioning should go deeper. The evaluation standard remains the same. | onboarding | evaluation |
| apps/web/src/components/onboarding-flow.tsx | 790 | Depth of inquiry | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 797 | Recommended | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 803 | Your selection becomes part of the planner's typed candidate context. It changes emphasis while the deterministic interview engine continues to enforce overall coverage a | onboarding | candidate |
| apps/web/src/components/onboarding-flow.tsx | 806 | Constructing the inquiry plan | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 808 | Mirror is using the saved role benchmark, reviewed claims, and your requested depth to prepare the evidence interview. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 824 | Interview thesis | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 825 | Mirror has built your interview thesis. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 826 | Your role, evidence, and requested depth are now connected in a prepared interview plan. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 830 | What you claim | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 831 | The experience and achievements your resume presents. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 835 | What the role demands | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 836 | The capabilities and depth expected for your target. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 840 | What remains unproven | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 841 | The areas where documents alone cannot establish readiness. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 845 | Depth, ownership, and decision reasoning behind the visible claims | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 852 | The evidence interview | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 853 | Mirror will now test the gaps between them. | onboarding | gaps, test |
| apps/web/src/components/onboarding-flow.tsx | 854 | Your questions will not follow a fixed script. Convincing evidence moves the interview forward; incomplete or ambiguous evidence leads to a deeper probe. | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 860 | Begin the evidence interview | onboarding | evidence |
| apps/web/src/components/onboarding-flow.tsx | 860 | Opening interview | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 870 | Step ${step} of 5 | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 871 | Building your diagnostic | onboarding | diagnostic |
| apps/web/src/components/onboarding-flow.tsx | 877 | Restoring diagnostic context | onboarding | diagnostic |
| apps/web/src/components/onboarding-flow.tsx | 878 | Reconnecting your saved work. | onboarding |  |
| apps/web/src/components/onboarding-flow.tsx | 879 | Mirror is loading the role, documents, and analysis already attached to this diagnostic. | onboarding | analysis, diagnostic |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 41 | Mirror is learning | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 42 | Diagnostic context | onboarding | diagnostic |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 46 | Benchmark | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 47 | Waiting for a target role | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 51 | Opportunity | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 57 | Starting evidence | onboarding | evidence |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 75 | The inquiry plan is ready. | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 76 | Each input changes what Mirror can investigate next. | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 96 | Role benchmark | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 96 | Role identified | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 100 | Role brief analysed | onboarding | analysed |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 100 | Role expectations inferred | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 104 | Evidence mapping | onboarding | evidence |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 108 | Evidence gaps | onboarding | evidence, gaps |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 112 | Lines of inquiry | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 116 | Interview thesis | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 122 | What Mirror is building | onboarding |  |
| apps/web/src/components/onboarding/diagnostic-panel.tsx | 127 | Diagnostic context | onboarding | diagnostic |
| apps/web/src/components/voice-interview.tsx | 71 | PREPARING: "Preparing the room", | session |  |
| apps/web/src/components/voice-interview.tsx | 71 | Preparing the room | session |  |
| apps/web/src/components/voice-interview.tsx | 72 | PREJOIN: "Ready to join", | session |  |
| apps/web/src/components/voice-interview.tsx | 72 | Ready to join | session |  |
| apps/web/src/components/voice-interview.tsx | 73 | CONNECTING: "Joining the interview", | session |  |
| apps/web/src/components/voice-interview.tsx | 73 | Joining the interview | session |  |
| apps/web/src/components/voice-interview.tsx | 74 | INTERVIEWER_SPEAKING: "Mirror is speaking", | session |  |
| apps/web/src/components/voice-interview.tsx | 74 | Mirror is speaking | session |  |
| apps/web/src/components/voice-interview.tsx | 75 | LISTENING: "Listening", | session |  |
| apps/web/src/components/voice-interview.tsx | 76 | CANDIDATE_SPEAKING: "You are speaking", | session |  |
| apps/web/src/components/voice-interview.tsx | 76 | You are speaking | session |  |
| apps/web/src/components/voice-interview.tsx | 77 | Mirror is considering your answer | session |  |
| apps/web/src/components/voice-interview.tsx | 77 | PROCESSING: "Mirror is considering your answer", | session |  |
| apps/web/src/components/voice-interview.tsx | 78 | Microphone muted | session |  |
| apps/web/src/components/voice-interview.tsx | 78 | PAUSED: "Microphone muted", | session |  |
| apps/web/src/components/voice-interview.tsx | 79 | ERROR: "Needs attention", | session |  |
| apps/web/src/components/voice-interview.tsx | 79 | Needs attention | session |  |
| apps/web/src/components/voice-interview.tsx | 80 | COMPLETE: "Interview complete", | session |  |
| apps/web/src/components/voice-interview.tsx | 80 | Interview complete | session |  |
| apps/web/src/components/voice-interview.tsx | 323 | This interview room is not ready yet. | session |  |
| apps/web/src/components/voice-interview.tsx | 344 | Mirror could not prepare this interview room. | session |  |
| apps/web/src/components/voice-interview.tsx | 423 | Mirror's audio is unavailable. The question remains visible. | session |  |
| apps/web/src/components/voice-interview.tsx | 432 | Select Replay question to hear Mirror. | session |  |
| apps/web/src/components/voice-interview.tsx | 528 | The microphone stopped unexpectedly. Select the microphone to reconnect. | session |  |
| apps/web/src/components/voice-interview.tsx | 582 | I couldn't hear that clearly. When you're ready, say your answer again. | session |  |
| apps/web/src/components/voice-interview.tsx | 583 | The conversation was interrupted. Try that answer again. | session |  |
| apps/web/src/components/voice-interview.tsx | 600 | Voice capture is not supported by this browser. | session |  |
| apps/web/src/components/voice-interview.tsx | 616 | Audio analysis is not supported. | session | analysis |
| apps/web/src/components/voice-interview.tsx | 642 | Microphone access is blocked. Allow it in browser settings to join by voice. | session |  |
| apps/web/src/components/voice-interview.tsx | 647 | Mirror could not connect your microphone. Check the device and try again. | session |  |
| apps/web/src/components/voice-interview.tsx | 717 | Mirror could not send that answer. | session |  |
| apps/web/src/components/voice-interview.tsx | 734 | Mirror's audio is still unavailable. | session |  |
| apps/web/src/components/voice-interview.tsx | 760 | Mirror could not end the interview. | session |  |
| apps/web/src/components/voice-interview.tsx | 782 | Mirror interview | session |  |
| apps/web/src/components/voice-interview.tsx | 783 | Private practice room | session |  |
| apps/web/src/components/voice-interview.tsx | 788 | ${remaining} seconds remaining | session |  |
| apps/web/src/components/voice-interview.tsx | 801 | Microphone blocked | session |  |
| apps/web/src/components/voice-interview.tsx | 801 | Microphone ready to connect | session |  |
| apps/web/src/components/voice-interview.tsx | 805 | Your private interview room | session |  |
| apps/web/src/components/voice-interview.tsx | 806 | Ready to meet Mirror? | session |  |
| apps/web/src/components/voice-interview.tsx | 808 | This works like a live call. Mirror asks a question, listens while you answer, | session |  |
| apps/web/src/components/voice-interview.tsx | 819 | Join interview | session |  |
| apps/web/src/components/voice-interview.tsx | 830 | Interview participants | session |  |
| apps/web/src/components/voice-interview.tsx | 833 | Mirror | session |  |
| apps/web/src/components/voice-interview.tsx | 834 | Interviewer | session |  |
| apps/web/src/components/voice-interview.tsx | 846 | Mirror is speaking | session |  |
| apps/web/src/components/voice-interview.tsx | 847 | Current question | session |  |
| apps/web/src/components/voice-interview.tsx | 864 | You · Live | session |  |
| apps/web/src/components/voice-interview.tsx | 868 | Keep going—Mirror is listening. | session |  |
| apps/web/src/components/voice-interview.tsx | 873 | Conversation transcript | session |  |
| apps/web/src/components/voice-interview.tsx | 876 | Conversation | session |  |
| apps/web/src/components/voice-interview.tsx | 877 | Live transcript | session |  |
| apps/web/src/components/voice-interview.tsx | 881 | Captions off | session |  |
| apps/web/src/components/voice-interview.tsx | 882 | Turn transcript | session |  |
| apps/web/src/components/voice-interview.tsx | 892 | The conversation will appear here as it unfolds. | session |  |
| apps/web/src/components/voice-interview.tsx | 895 | interview-transcript-turn is-candidate is-live | session | candidate |
| apps/web/src/components/voice-interview.tsx | 896 | You · Live | session |  |
| apps/web/src/components/voice-interview.tsx | 912 | Type your answer | session |  |
| apps/web/src/components/voice-interview.tsx | 913 | Voice pauses while you type. | session |  |
| apps/web/src/components/voice-interview.tsx | 919 | Write naturally, as you would say it… | session |  |
| apps/web/src/components/voice-interview.tsx | 925 | Cancel | session |  |
| apps/web/src/components/voice-interview.tsx | 926 | Send answer | session |  |
| apps/web/src/components/voice-interview.tsx | 934 | Continue | session |  |
| apps/web/src/components/voice-interview.tsx | 938 | Interview controls | session |  |
| apps/web/src/components/voice-interview.tsx | 943 | Preparing the next question | session |  |
| apps/web/src/components/voice-interview.tsx | 953 | Mute microphone | session |  |
| apps/web/src/components/voice-interview.tsx | 953 | Unmute microphone | session |  |
| apps/web/src/components/voice-interview.tsx | 966 | Type | session |  |
| apps/web/src/components/voice-interview.tsx | 974 | Turn live captions off | session |  |
| apps/web/src/components/voice-interview.tsx | 974 | Turn live captions on | session |  |
| apps/web/src/components/voice-interview.tsx | 975 | Live captions are not supported by this browser | session |  |
| apps/web/src/components/voice-interview.tsx | 978 | Captions | session |  |
| apps/web/src/components/voice-interview.tsx | 987 | Mirror could not speak this question. You can read it above and answer normally. | session |  |
| apps/web/src/components/voice-interview.tsx | 988 | Hear the question again | session |  |
| apps/web/src/components/voice-interview.tsx | 1000 | Pause briefly so Mirror can save your final answer | session |  |
| apps/web/src/components/voice-interview.tsx | 1003 | End interview | session |  |
| apps/web/src/components/workspace/account-settings.tsx | 31 | Mirror could not load your account details. | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 50 | Your profile has been updated. | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 52 | Mirror could not update your profile. | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 60 | ws-page-header is-stacked | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 61 | Manage the profile information attached to your private evidence workspace. | workspace | evidence |
| apps/web/src/components/workspace/account-settings.tsx | 61 | Settings | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 61 | Your account | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 64 | Retry | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 69 | Account details | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 69 | Profile | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 69 | This name appears in your Mirror workspace. Your sign-in email is managed by your authentication account. | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 69 | ws-section-heading is-flush | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 71 | Full name | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 72 | Email address | workspace |  |
| apps/web/src/components/workspace/account-settings.tsx | 73 | Save changes | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 22 | Home | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 23 | Diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/app-shell.tsx | 24 | Evidence Library | workspace | evidence |
| apps/web/src/components/workspace/app-shell.tsx | 25 | Role Explorer | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 26 | Settings | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 54 | Mirror could not sign you out. Please try again. | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 63 | Primary navigation | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 64 | Mirror home | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 66 | MIRROR | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 89 | Mirror candidate | workspace | candidate |
| apps/web/src/components/workspace/app-shell.tsx | 90 | Private workspace | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 92 | Log out | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 100 | Mirror home | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 102 | MIRROR | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 104 | Evidence workspace | workspace | evidence |
| apps/web/src/components/workspace/app-shell.tsx | 105 | Open account settings | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 107 | Your account | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 115 | Mobile navigation | workspace |  |
| apps/web/src/components/workspace/app-shell.tsx | 126 | Evidence Library | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 24 | Your diagnostic is ready | workspace | diagnostic |
| apps/web/src/components/workspace/current-diagnostic.tsx | 25 | Mirror has finished evaluating your interview against your claims and the expectations of the role. | workspace | evaluating |
| apps/web/src/components/workspace/current-diagnostic.tsx | 26 | Review findings | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 31 | We couldn't complete the diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/current-diagnostic.tsx | 32 | Your interview has been saved. Mirror couldn't finish evaluating the evidence, so the assessment can be retried without repeating the interview. | workspace | assessment, evaluating, evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 33 | Retry evaluation | workspace | evaluation |
| apps/web/src/components/workspace/current-diagnostic.tsx | 38 | Evaluating evidence | workspace | evaluating, evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 39 | Mirror is analysing your answers, matching them with your claims and role expectations. | workspace | analysing |
| apps/web/src/components/workspace/current-diagnostic.tsx | 45 | Interview in progress | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 46 | Your evidence interview is underway. Continue the conversation when you're ready. | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 47 | Continue interview | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 52 | Your evidence interview is ready | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 53 | Mirror has prepared the interview thesis for this role and your available evidence. | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 54 | Begin interview | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 58 | Continue building your evidence case | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 59 | Finish the role and evidence setup before starting your evidence interview. | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 60 | Continue setup | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 70 | Promise | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 84 | Current diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/current-diagnostic.tsx | 101 | We&apos;ll notify you as soon as your diagnostic is ready. | workspace | diagnostic |
| apps/web/src/components/workspace/current-diagnostic.tsx | 105 | Requesting retry... | workspace |  |
| apps/web/src/components/workspace/current-diagnostic.tsx | 105 | Retry evaluation | workspace | evaluation |
| apps/web/src/components/workspace/current-diagnostic.tsx | 117 | Turning your experience into evidence | workspace | evidence |
| apps/web/src/components/workspace/current-diagnostic.tsx | 119 | Turning your experience into evidence. | workspace | evidence |
| apps/web/src/components/workspace/diagnostic-progress.tsx | 16 | Interview captured | workspace |  |
| apps/web/src/components/workspace/diagnostic-progress.tsx | 17 | Evidence being evaluated | workspace | evaluated, evidence |
| apps/web/src/components/workspace/diagnostic-progress.tsx | 18 | Findings being reconciled | workspace |  |
| apps/web/src/components/workspace/diagnostic-progress.tsx | 19 | Diagnostic ready | workspace | diagnostic |
| apps/web/src/components/workspace/diagnostic-progress.tsx | 23 | Diagnostic lifecycle | workspace | diagnostic |
| apps/web/src/components/workspace/diagnostics-index.tsx | 40 | Mirror could not load your diagnostics. Your saved interviews have not been removed. | workspace | diagnostics |
| apps/web/src/components/workspace/diagnostics-index.tsx | 61 | Mirror could not retry this evaluation. | workspace | evaluation |
| apps/web/src/components/workspace/diagnostics-index.tsx | 70 | A record of the roles you&apos;ve tested, what you&apos;ve learned, and how your readiness has evolved. | workspace | tested |
| apps/web/src/components/workspace/diagnostics-index.tsx | 70 | Diagnostic record | workspace | diagnostic |
| apps/web/src/components/workspace/diagnostics-index.tsx | 70 | Your diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/diagnostics-index.tsx | 71 | Start new | workspace |  |
| apps/web/src/components/workspace/diagnostics-index.tsx | 74 | Filter diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/diagnostics-index.tsx | 82 | Retry | workspace |  |
| apps/web/src/components/workspace/diagnostics-index.tsx | 88 | No diagnostics here yet. | workspace | diagnostics |
| apps/web/src/components/workspace/diagnostics-index.tsx | 88 | Start a diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/diagnostics-index.tsx | 88 | Start a diagnostic to test your evidence against a role. | workspace | diagnostic, evidence, test |
| apps/web/src/components/workspace/diagnostics-index.tsx | 91 | ws-row-list reveal-stagger is-visible | workspace |  |
| apps/web/src/components/workspace/diagnostics-index.tsx | 94 | Open ${diagnostic.target_role} diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/diagnostics-index.tsx | 103 | Retry evaluation | workspace | evaluation |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 30 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 47 | ws-dialog-panel scale-in-once | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 49 | Add evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 49 | Give Mirror evidence to work from | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 50 | Close | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 53 | Historical versions stay intact. | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 56 | Choose a PDF or DOCX file | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 57 | Mirror validates the file before adding it | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 61 | Evidence title | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 62 | Category | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 64 | Add ownership, scope, dates, or outcomes the file does not make clear. | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 64 | Context for Mirror | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 64 | Optional | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 66 | Evidence upload progress | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 68 | Refreshing evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 74 | Cancel | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 75 | Add evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 75 | Replace file | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 93 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 102 | ws-dialog-panel scale-in-once | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 105 | Remove from library | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 106 | Close | workspace |  |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 110 | This evidence is being used. | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 111 | Professional evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-dialogs.tsx | 115 | Cancel | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 37 | Mirror has not extracted a candidate-facing summary from this version yet. | workspace | candidate |
| apps/web/src/components/workspace/evidence-drawer.tsx | 41 | Skills found | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 42 | Projects found | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 43 | Document excerpt | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 65 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 66 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 67 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 69 | Promise | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 74 | Professional evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 99 | Evidence record | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 100 | Close evidence details | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 105 | This evidence is part of an active diagnostic. | workspace | diagnostic, evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 106 | Changes apply to future diagnostics. The active diagnostic keeps the version it already references. | workspace | diagnostic, diagnostics |
| apps/web/src/components/workspace/evidence-drawer.tsx | 113 | Type | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 114 | Updated | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 115 | Original file | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 115 | Text evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 116 | Version | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 119 | Context for Mirror | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 119 | No additional context has been added. | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 120 | What Mirror extracted | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 122 | Used in diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/evidence-drawer.tsx | 128 | Open | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 132 | This version has not been linked to a diagnostic. | workspace | diagnostic |
| apps/web/src/components/workspace/evidence-drawer.tsx | 137 | Evidence title | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 138 | Evidence category | workspace | evidence |
| apps/web/src/components/workspace/evidence-drawer.tsx | 139 | Add ownership, scope, chronology, or outcomes that the document does not make clear. | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 139 | Context for Mirror | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 140 | Cancel | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 149 | Restore to library | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 152 | Edit details | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 153 | Replace file | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 154 | Download | workspace |  |
| apps/web/src/components/workspace/evidence-drawer.tsx | 155 | Remove | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 70 | Mirror could not load your professional evidence. Your saved files have not been changed. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 130 | Evidence added. Mirror will use this version in future diagnostics. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 132 | We couldn't add this evidence. Try again. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 145 | Professional evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 171 | File replaced, but Mirror could not finish reading this resume. Historical diagnostics remain unchanged. | workspace | diagnostics |
| apps/web/src/components/workspace/evidence-library.tsx | 172 | File replaced. Diagnostics already completed still use the previous version. | workspace | diagnostics |
| apps/web/src/components/workspace/evidence-library.tsx | 174 | We couldn't replace this evidence. Your original file is unchanged. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 192 | Evidence details updated for future diagnostics. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 194 | We couldn't update this evidence. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 209 | Evidence removed from future diagnostics. Historical references were preserved. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 211 | We couldn't remove this evidence. It remains in your library. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 224 | Evidence restored and available for future diagnostics. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 226 | We couldn't restore this evidence. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 243 | Mirror could not download the original file. | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 258 | Category updated for the selected evidence. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 260 | Mirror could not update the selected evidence. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 274 | Selected evidence restored for future diagnostics. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 276 | Mirror could not restore the selected evidence. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 297 | Evidence library | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 297 | The evidence Mirror is allowed to reason from—managed by you. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 297 | Your professional evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 298 | Add evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 301 | Evidence library summary | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 302 | Archived versions remain attached to historical findings | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 302 | in your library | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 302 | used in diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/evidence-library.tsx | 305 | Evidence state | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 306 | Current evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 307 | Recently removed | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 310 | Evidence tools | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 311 | Clear search | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 311 | Search evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 312 | All categories | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 312 | Filter by category | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 313 | Name | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 313 | Recently added | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 313 | Recently updated | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 313 | Sort evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 317 | Bulk evidence actions | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 319 | Change category | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 319 | Choose… | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 319 | Remove from library | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 319 | Restore selected | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 320 | Clear | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 324 | Dismiss | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 325 | Retry | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 332 | No evidence matches this view. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 332 | Nothing has been removed. | workspace |  |
| apps/web/src/components/workspace/evidence-library.tsx | 332 | Your evidence library is empty. | workspace | evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 333 | Add the documents, projects and achievements Mirror should use when evaluating your experience. | workspace | evaluating |
| apps/web/src/components/workspace/evidence-library.tsx | 333 | Evidence removed from future diagnostics will appear here and can be restored. | workspace | diagnostics, evidence |
| apps/web/src/components/workspace/evidence-library.tsx | 334 | Add evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-preview.tsx | 17 | Your evidence library | workspace | evidence |
| apps/web/src/components/workspace/evidence-preview.tsx | 18 | The context Mirror can use in a diagnostic. | workspace | diagnostic |
| apps/web/src/components/workspace/evidence-preview.tsx | 20 | View all | workspace |  |
| apps/web/src/components/workspace/evidence-preview.tsx | 23 | Your evidence library is temporarily unavailable. | workspace | evidence |
| apps/web/src/components/workspace/evidence-preview.tsx | 36 | No professional evidence has been added yet. | workspace | evidence |
| apps/web/src/components/workspace/evidence-preview.tsx | 37 | Add evidence | workspace | evidence |
| apps/web/src/components/workspace/evidence-row.tsx | 35 | Available for future diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/evidence-row.tsx | 84 | Needs reading | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 87 | Actions for ${title} | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 89 | Open | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 91 | Restore | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 94 | Edit details | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 95 | Replace file | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 96 | Change category | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 98 | Download original | workspace |  |
| apps/web/src/components/workspace/evidence-row.tsx | 99 | Remove from library | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 8 | Resume | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 9 | Project | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 10 | Case studies | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 10 | Case study | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 11 | Certificate | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 12 | Portfolio | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 13 | Cover letter | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 13 | Cover letters | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 14 | Achievement | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 15 | Work sample | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 15 | Work samples | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 16 | Role brief | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 17 | Other | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 23 | RESUME: "RESUME", | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 24 | JOB_DESCRIPTION: "ROLE_BRIEF", | workspace |  |
| apps/web/src/components/workspace/evidence-types.ts | 25 | PROJECT: "PROJECT", | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 7 | View past diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/quick-actions.tsx | 8 | Revisit your findings and track progress. | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 13 | Add or update evidence | workspace | evidence |
| apps/web/src/components/workspace/quick-actions.tsx | 14 | Upload new documents, projects or achievements. | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 19 | Explore new roles | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 20 | See role benchmarks and understand what's in demand. | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 30 | Continue building your case | workspace |  |
| apps/web/src/components/workspace/quick-actions.tsx | 31 | Choose the next useful step for your evidence. | workspace | evidence |
| apps/web/src/components/workspace/recent-diagnostics.tsx | 17 | Recent diagnostics | workspace | diagnostics |
| apps/web/src/components/workspace/recent-diagnostics.tsx | 18 | Revisit past roles and findings. | workspace |  |
| apps/web/src/components/workspace/recent-diagnostics.tsx | 20 | View all | workspace |  |
| apps/web/src/components/workspace/recent-diagnostics.tsx | 28 | General diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/recent-diagnostics.tsx | 39 | Completed and in-progress diagnostics will appear here. | workspace | diagnostics |
| apps/web/src/components/workspace/role-explorer.tsx | 31 | Mirror could not restore your role history. You can still begin a new diagnostic. | workspace | diagnostic |
| apps/web/src/components/workspace/role-explorer.tsx | 58 | ws-page-header is-stacked | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 59 | Explore roles with clarity | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 59 | Role explorer | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 59 | Understand what different roles demand and see how your experience can be tested against them. | workspace | tested |
| apps/web/src/components/workspace/role-explorer.tsx | 64 | Role to explore | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 65 | Search or enter a role, for example Product Manager | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 66 | Start diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/role-explorer.tsx | 69 | Retry | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 73 | Based only on your existing Mirror diagnostics. | workspace | diagnostics |
| apps/web/src/components/workspace/role-explorer.tsx | 73 | Roles you&apos;ve explored | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 73 | ws-section-heading is-flush | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 76 | Enter a role above to start building a benchmark with real role context. | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 76 | No role benchmarks yet. | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 79 | ws-role-grid reveal-stagger is-visible | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 81 | ws-role-card ws-panel | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 83 | No company specified | workspace |  |
| apps/web/src/components/workspace/role-explorer.tsx | 83 | Previously tested role | workspace | tested |
| apps/web/src/components/workspace/role-explorer.tsx | 84 | Start a new diagnostic | workspace | diagnostic |
| apps/web/src/components/workspace/workspace-unavailable.tsx | 7 | Workspace unavailable | workspace |  |
| apps/web/src/components/workspace/workspace-unavailable.tsx | 8 | Mirror could not restore your evidence workspace. | workspace | evidence |
| apps/web/src/components/workspace/workspace-unavailable.tsx | 9 | Your completed interviews remain saved. Refresh this page to try the secure connection again. | workspace |  |
| apps/web/src/components/workspace/workspace-utils.ts | 21 | Interview in progress | workspace |  |
| apps/web/src/components/workspace/workspace-utils.ts | 22 | Interview ready | workspace |  |
| apps/web/src/components/workspace/workspace-utils.ts | 27 | Setup in progress | workspace |  |
| apps/web/src/components/workspace/workspace-utils.ts | 52 | Pasted role brief | workspace |  |
| apps/web/src/lib/api.ts | 370 | (path: string, init?: RequestInit): Promise | other |  |
| apps/web/src/lib/api.ts | 411 | Authentication required | other |  |
| apps/web/src/lib/api.ts | 417 | The upload was cancelled. | other |  |
| apps/web/src/lib/api.ts | 432 | Mirror could not reach the voice service. | other |  |
| apps/web/src/lib/api.ts | 433 | That answer took too long to process. Try again. | other |  |
| apps/web/src/lib/api.ts | 434 | The upload was cancelled. | other |  |
| apps/web/src/lib/api.ts | 440 | = 200 && xhr.status | other |  |
| apps/web/src/lib/api.ts | 468 | Authentication required | other |  |
| apps/web/src/lib/api.ts | 477 | Mirror could not reach the document service. | other |  |
| apps/web/src/lib/api.ts | 481 | = 200 && request.status | other |  |
| apps/web/src/lib/api.ts | 487 | Mirror could not upload that resume. | other |  |
| apps/web/src/lib/api.ts | 500 | Authentication required | other |  |
| apps/web/src/lib/api.ts | 509 | Mirror could not reach the document service. | other |  |
| apps/web/src/lib/api.ts | 513 | = 200 && request.status | other |  |
| apps/web/src/lib/api.ts | 519 | Mirror could not upload that role brief. | other |  |
| apps/web/src/lib/api.ts | 539 | Authentication required | other |  |
| apps/web/src/lib/api.ts | 551 | Mirror could not reach the evidence service. | other | evidence |
| apps/web/src/lib/api.ts | 555 | = 200 && upload.status | other |  |
| apps/web/src/lib/api.ts | 569 | Mirror could not update that evidence. | other | evidence |
| apps/web/src/lib/api.ts | 588 | Authentication required | other |  |
| apps/web/src/lib/api.ts | 601 | Mirror could not download the original file. | other |  |
| apps/web/src/lib/api.ts | 608 | request | other |  |
| apps/web/src/lib/api.ts | 609 | request | other |  |
| apps/web/src/lib/api.ts | 614 | request | other |  |
| apps/web/src/lib/api.ts | 615 | request | other |  |
| apps/web/src/lib/api.ts | 620 | request | other |  |
| apps/web/src/lib/api.ts | 623 | request | other |  |
| apps/web/src/lib/api.ts | 626 | request | other |  |
| apps/web/src/lib/api.ts | 627 | request | other |  |
| apps/web/src/lib/api.ts | 636 | request | other |  |
| apps/web/src/lib/api.ts | 641 | request | other |  |
| apps/web/src/lib/api.ts | 649 | request | other |  |
| apps/web/src/lib/api.ts | 650 | request | other |  |
| apps/web/src/lib/api.ts | 655 | request | other |  |
| apps/web/src/lib/api.ts | 656 | request | other |  |
| apps/web/src/lib/api.ts | 659 | request | other |  |
| apps/web/src/lib/api.ts | 665 | request | other |  |
| apps/web/src/lib/api.ts | 680 | request | other |  |
| apps/web/src/lib/api.ts | 685 | request | other |  |
| apps/web/src/lib/api.ts | 686 | request | other |  |
| apps/web/src/lib/api.ts | 689 | request | other |  |
| apps/web/src/lib/api.ts | 699 | request | other |  |
| apps/web/src/lib/api.ts | 700 | request | other |  |
| apps/web/src/lib/api.ts | 701 | request | other |  |
| apps/web/src/lib/api.ts | 702 | request | other |  |
| apps/web/src/lib/api.ts | 703 | request | other |  |
| apps/web/src/lib/api.ts | 704 | request | other |  |
| apps/web/src/lib/api.ts | 711 | request | other |  |
| apps/web/src/lib/api.ts | 712 | request | other |  |
| apps/web/src/lib/api.ts | 713 | request | other |  |
| apps/web/src/lib/api.ts | 714 | request | other |  |
| apps/web/src/lib/api.ts | 715 | request | other |  |
| apps/web/src/lib/api.ts | 716 | request | other |  |
| apps/web/src/lib/documents.ts | 27 | Mirror could not extract text from that role brief. Try a text-based PDF or DOCX file. | other |  |
| apps/web/src/lib/documents.ts | 28 | Your session expired. Please sign in again. | other |  |
| apps/web/src/lib/supabase.ts | 14 | Supabase browser configuration is missing | other |  |
