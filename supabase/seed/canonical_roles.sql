-- Synthetic development role vocabulary only. Competency maps are versioned in
-- app/role_canonical.py and are never represented as employer-validated.
insert into public.roles (name)
values
  ('Data Analyst'),
  ('Business Analyst'),
  ('Software Engineer'),
  ('Product Analyst')
on conflict (name) do nothing;

