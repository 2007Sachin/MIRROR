# Claim state resolution

## Authority boundary

Agents, the Skeptic, evidence processing, users, and administrators may propose
a state. Only `ClaimResolutionService` can commit it. The previous generic
`update_claim_status` RPC is revoked from the service role by migration 015, and
`ClaimsGraphService.update_status` rejects all calls.

```text
proposal + validated evidence + trigger
                  │
                  v
       ClaimResolutionService
       ├─ legal transition table
       ├─ evidence sufficiency rules
       ├─ correction semantics
       └─ expected current status
                  │
                  v
       resolve_claim_state transaction
       ├─ lock owned claim
       ├─ compare expected state
       ├─ verify evidence ownership/validation
       ├─ append claim_versions
       ├─ update claims.status
       └─ insert claim_resolutions
```

The claim text and its original source are never overwritten during resolution.
`claim_versions` and `claim_resolutions` preserve the full status history and
the evidence IDs that justified each decision.

## Legal transitions

`UNVERIFIED` may become any evidence-bearing terminal/intermediate state.
`CORROBORATED` may become `PARTIALLY_HELD`, `WALKED_BACK`, or `CONTRADICTED`
when new evidence warrants it. `PARTIALLY_HELD` and
`INSUFFICIENT_EVIDENCE` can be revised when substantive evidence arrives.
`WALKED_BACK` remains historical even if later evidence changes the current
status. A previously contradicted claim can only recover to partial or
corroborated status through a new resolution.

No-op transitions are rejected except a pre-interview extraction correction,
which records `UNVERIFIED → UNVERIFIED` audit history. This distinguishes “the
AI extracted my resume incorrectly” from a candidate narrowing a claim during
an interview. An extraction correction can never create `WALKED_BACK`.

## Evidence requirements

- `CORROBORATED` requires moderate/strong support without material weakening.
- `PARTIALLY_HELD` requires meaningful evidence in both directions.
- `WALKED_BACK` requires explicit retraction or ownership narrowing.
- `CONTRADICTED` requires support for the original claim plus strong, direct,
  mutually incompatible evidence. Ambiguity is insufficient.
- `INSUFFICIENT_EVIDENCE` requires the absence of substantive support or
  weakening evidence.

Evidence IDs supplied to PostgreSQL must belong to the claim and user and have
`validated=true`. LLM recommendations alone cannot satisfy these rules.

## Concurrency and finalization

Every proposal carries the status observed before validation. PostgreSQL locks
the claim and compares this expected status. If another worker resolved it
first, the transaction fails with `ConcurrentClaimResolution`; callers must
reload and reconsider rather than overwrite the newer result.

During session finalization, an unresolved high-priority claim with no
meaningful evidence may become `INSUFFICIENT_EVIDENCE`. Resolution never forces
a binary true/false outcome.

## Audit grouping

`ClaimsAuditService` groups a user's claims as held, partially held, walked
back, contradicted, insufficient evidence, or unverified. It is an internal
backend view for later reporting and scoring work; this milestone adds no
candidate report or readiness score.

