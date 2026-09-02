---
name: mirror-quality
description: Testing and completion standards for Mirror.
---

Add focused unit/integration tests for domain rules, auth/ownership, schemas, provider fakes, retries, and failure paths. Use synthetic fixtures; never call paid providers in tests. Validate migrations when possible. Run `python -m pytest`, `npm run lint`, `npm run test`, and `npm run build` when supported, separating pre-existing environment failures from regressions.

