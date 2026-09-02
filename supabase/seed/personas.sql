-- Synthetic development fixtures only. Never use these rows for real calibration thresholds.
insert into public.golden_cases (case_type, transcript, expected_flags, expected_claim_states, expected_score_band, source, version) values
('P1_INFLATER', '[]', '[{"type":"contradiction","min":1},{"type":"unsupported_scale","min":1}]', '{"reliability":"needs_clarification"}', '{"role":"low","interview":"mixed"}', 'synthetic', 'persona-v1'),
('P2_UNDERSELLER', '[]', '[]', '{"reliability":"strong"}', '{"role":"high","interview":"lower_than_role"}', 'synthetic', 'persona-v1'),
('P3_REHEARSED', '[]', '[{"type":"vagueness","min":1}]', '{"depth":"falls_after_probe_2"}', '{"role":"medium","interview":"mixed"}', 'synthetic', 'persona-v1'),
('P4_COLLAPSER', '[]', '[]', '{"technical":"corroborated"}', '{"role":"high","interview":"lower_than_role"}', 'synthetic', 'persona-v1'),
('P5_HONEST_BEGINNER', '[]', '[]', '{"reliability":"strong","contradiction_max":0}', '{"role":"low","interview":"low"}', 'synthetic', 'persona-v1'),
('P6_COASTING_CONTRIBUTOR', '[]', '[{"type":"ownership_drift","min":1}]', '{"ownership":"walked_back"}', '{"role":"low_to_medium","interview":"mixed"}', 'synthetic', 'persona-v1'),
('P7_STRONG_CANDIDATE', '[]', '[]', '{"reliability":"strong"}', '{"role":"top","interview":"top"}', 'synthetic', 'persona-v1');


