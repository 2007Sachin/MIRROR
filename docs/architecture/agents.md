# Agent infrastructure

Mirror uses multiple narrowly scoped agents because interview preparation requires different kinds of reasoning: extracting evidence, understanding a role, conducting an interview, challenging claims, and assessing performance. Those product agents are intentionally not part of this milestone. This package establishes the shared execution boundary they will use.

## Application control boundary

Agents reason and produce validated data. Application code retains control of authentication, authorization, persistence, billing, job retries, session lifecycle, and interview phase transitions. An agent input must therefore contain only the context the application has already authorized; a model-provided user identifier is never authority.

`BaseAgent` is a declarative definition. It names the input and output Pydantic schemas, model alias resolved from centralized settings, prompt version, temperature, tool allow-list, timeout, and malformed-output retry limit. Product agents do not need provider transport boilerplate.

`AgentRegistry` is instance-based and designed for dependency injection. Registration is explicit, duplicates are rejected, unknown names are typed errors, and no process-global mutable registry is created.

## AgentRunner

`AgentRunner` owns execution:

1. Resolve the definition and validate input with its Pydantic schema.
2. Load the versioned system prompt.
3. Construct a provider-neutral request containing the output JSON Schema and permitted tool specifications.
4. Ask Groq for strict structured JSON within the agent timeout.
5. Validate the decoded JSON with the output Pydantic schema.
6. Retry only malformed JSON or schema-invalid model output, up to the definition's limit.
7. Return an `AgentExecutionResult` containing execution identity, model and prompt metadata, latency, retry count, optional token usage, output, and a normalized error type.

Provider failures, timeouts, malformed JSON, schema-validation failures, tool failures, permission failures, and unexpected internal failures remain distinct. Provider and tool exceptions are not exposed as model output or API details.

## Prompt versioning

Prompts live at `apps/api/app/prompts/<agent_name>/<version>.md`. `PromptLoader.load(agent_name, version)` accepts constrained identifiers and prevents path traversal. A definition pins one prompt version, and every result and structured log records it. The empty `resume`, `role`, `interviewer`, `skeptic`, `evidence`, and `assessor` directories reserve the future product layout without inventing business prompts. `framework_test/v1.md` belongs only to automated infrastructure tests.

## Models and credentials

`Settings` centralizes `INTERVIEWER_MODEL`, `SKEPTIC_MODEL`, `ASSESSOR_MODEL`, and `BATCH_MODEL`, with development defaults that can be overridden by environment. `GROQ_API_KEY` has no source-code default and must remain server-side. Agent definitions receive model values from application composition rather than hardcoding provider model names in business agents.

## Tool restrictions

`ToolRegistry` registers application-owned typed handlers. A tool is sent to the provider only when it is registered and included in the agent definition's `allowed_tools`. Every model-requested call is checked again before execution and its arguments are validated with Pydantic. Tool results must be JSON-serializable.

There is no arbitrary SQL tool. Agents must never receive database credentials or construct privileged queries. Future tools such as `get_claims` or `get_recent_turns` must call authorization-aware application services or repositories, using trusted execution context supplied by application code. RLS and backend authorization remain defense-in-depth rather than model responsibilities.

## Logging and privacy

One structured event is emitted per execution with execution ID, agent, session/user identifiers when supplied, model, prompt version, latency, retry count, success, and normalized error type. Inputs, prompts, outputs, resumes, transcripts, tool arguments, and tool results are deliberately excluded by default to avoid logging PII.

