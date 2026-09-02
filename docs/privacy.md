# Privacy and access

Candidate resumes, recordings, transcripts, claims, and assessments are private per-user records. Browser clients receive only the Supabase anonymous key. Service-role credentials and model-provider keys remain server-side.

Production provider agreements and account settings must be configured so interview recordings, transcripts, and resumes are not intentionally used for third-party model training. Real traffic and synthetic evaluation workflows use separate storage prefixes, `synthetic` markers, and job queues.

RLS grants candidates access to their own data. No TPO policy grants access to individual transcripts or recordings. Signed audio URLs should be short-lived and generated only after owner authorization.

Deletion/retention controls and provider DPAs are deployment gates before real candidate data is accepted.


