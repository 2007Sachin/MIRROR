# Resume Intelligence Agent

## Purpose

The Resume Intelligence Agent converts processed resume text into neutral, structured candidate information for later claims-graph and interview-planning work. It records what the resume claims. It does not decide whether a claim is true.

This milestone contains only resume intelligence. Role intelligence, interview planning, interviewing, skepticism, evidence analysis, and assessment remain outside its scope.

## Processing flow

1. The authenticated API resolves the resume through an owner-scoped document repository query. A request cannot supply or override a user ID.
2. If the document has not been parsed, `ResumeDocumentParser` downloads it from private Supabase Storage and deterministically extracts text. PDF pages receive `[Page N]` markers; DOCX paragraphs receive `[Paragraph N]` markers.
3. File parsing updates the document's `raw_text` and processing status. Raw files are never sent to the model.
4. `ResumeAnalysisService` creates a new immutable analysis version and invokes the shared `AgentRunner` with the versioned `resume/v1` prompt.
5. The runner requests strict JSON, validates the response with Pydantic, and retries malformed model output according to the agent definition.
6. A completed analysis stores its full structured output and document-linked claim rows. Failure stores a normalized error type without exposing provider details.

The service is synchronous for development, but orchestration is separate from FastAPI routes and can move behind the existing jobs/worker boundary without changing the agent or persistence contracts.

## Inputs

`ResumeAgentInput` contains:

- `document_id` and `user_id`, used only as trusted application execution metadata and excluded from the provider payload.
- `resume_text`, parsed text with source markers where available.
- `candidate_profile`, limited to non-identifying career stage, target role, and preferred-language metadata.

Names, email addresses from the profile, database credentials, storage credentials, and raw file bytes are not added to the model request by application code. A resume may itself contain personal data, so prompts, input, and output are excluded from default agent logs.

## Outputs

The strict `ResumeAgentOutput` schema contains:

- Skills with category, source reference, and confidence.
- Projects with technologies, claimed responsibilities, and claimed outcomes.
- Work experience and education.
- Tools and achievements.
- Atomic claims with type, `RESUME` source, source reference, confidence, and interview-usefulness verification priority.
- Optional claim structure for skill, project, metric, ownership wording, outcome, and tool.

`HIGH` verification priority means that a claim is specific or useful to discuss in an interview. It never means suspicious.

## Versioning and review

Every run inserts a new `resume_analyses` version containing model, prompt version, analysis version, execution ID, timestamps, and the original model output. Earlier versions are preserved.

Resume claims are attached to their source document and analysis. Candidate reviews are append-only rows in `resume_claim_corrections`; marking a claim `CORRECT` or `NEEDS_CORRECTION` never modifies the original AI extraction. The API returns the latest correction alongside the immutable original claim.

A partial unique database index permits only one `PROCESSING` analysis per document, preventing duplicate concurrent inference. Completion and claim insertion occur in one PostgreSQL function/transaction.

## Prompt-injection boundary

Resume content is untrusted data in a user-role JSON payload. The versioned system prompt explicitly rejects embedded commands, schema changes, expertise assignments, and instructions such as “ignore previous instructions.” The agent has no tools, SQL access, storage access, or application permissions.

This boundary reduces prompt-injection risk but cannot prove that a probabilistic model will never misbehave. Strict output validation, source references, neutral candidate review, private logging defaults, and synthetic adversarial test cases provide additional controls.

## Explicit limitations and non-goals

The Resume Intelligence Agent does not:

- Verify truthfulness or accuse a candidate of dishonesty, exaggeration, or deception.
- Produce readiness, expertise, personality, or hiring scores.
- Infer achievements, ownership, causality, or metrics not stated in the resume.
- Read image-only/scanned PDFs with OCR.
- Resolve roles, plan interviews, ask questions, challenge claims, score evidence, or assess candidates.
- Execute SQL or control authentication, authorization, sessions, jobs, retries outside its own malformed-output handling, or interview phases.

PDF/DOCX extraction quality depends on the source document structure. Ambiguous ownership remains explicitly ambiguous and should be clarified neutrally in a later interview milestone.

