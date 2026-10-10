"""Disposable PostgreSQL 16 exercise of Loop 5A SQL (scratch directory only)."""
import shutil, subprocess, uuid, time, json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path

PG=Path('C:/Program Files/PostgreSQL/16/bin')
ROOT=Path('C:/Users/sachi/OneDrive/Desktop/MIRROR')
SCRATCH=Path('C:/Users/sachi/AppData/Local/hermes/cache/scratch')
BASE=SCRATCH/f'loop5a_pg_{uuid.uuid4().hex[:8]}'
PORT=str(56000+int(uuid.uuid4().hex[:3],16)%3000)
DATA=BASE/'data'
UP=ROOT/'supabase/migrations/20261004200000_loop2_candidate_targets.sql'
PROMPT=ROOT/'supabase/migrations/20261005210000_target_prompt_completeness.sql'
MIG=ROOT/'supabase/migrations/20261008230000_loop5a_candidate_stages.sql'
DOWN=ROOT/'supabase/rollbacks/20261008230000_loop5a_candidate_stages_down.sql'
A='10000000-0000-4000-8000-000000000001'; B='20000000-0000-4000-8000-000000000001'; S='60000000-0000-4000-8000-000000000001'
T='30000000-0000-4000-8000-000000000001'; TB='30000000-0000-4000-8000-000000000002'; TC='30000000-0000-4000-8000-000000000003'
R='40000000-0000-4000-8000-000000000001'; RB='40000000-0000-4000-8000-000000000002'
ST='50000000-0000-4000-8000-000000000001'; ST2='50000000-0000-4000-8000-000000000002'
SHA='a'*64
checks=[]
def call(args,input=None,ok=True):
 print('RUN',Path(args[0]).name,flush=True)
 p=subprocess.run(args,input=input,text=True,capture_output=True,timeout=30)
 print('DONE',Path(args[0]).name,p.returncode,flush=True)
 if ok and p.returncode: raise RuntimeError(p.stderr+'\\n'+p.stdout)
 return p

def sql(s,ok=True):
 p=call([str(PG/'psql.exe'),'-X','-qAt','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p',PORT,'-U','postgres','-d','testdb','-c',s],ok=ok)
 return (p.stdout.strip(),p.stderr.strip(),p.returncode)
def check(name,s,want):
 got=sql(s)[0]; checks.append((name,got==want,got))
def expect(name,s,needle):
 _,err,rc=sql(s,False); checks.append((name,rc!=0 and needle.lower() in err.lower(),err.strip()[:190]))
def concurrent_sql(statements):
 barrier=Barrier(len(statements))
 def run(statement):
  barrier.wait(timeout=10)
  p=subprocess.run([str(PG/'psql.exe'),'-X','-qAt','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p',PORT,'-U','postgres','-d','testdb','-c',statement],text=True,capture_output=True,timeout=30)
  return p.returncode,p.stdout.strip(),p.stderr.strip()
 with ThreadPoolExecutor(max_workers=len(statements)) as pool: return list(pool.map(run,statements))
def reader_writer_race(reader_statement,writer_statement,lock_key):
 args=[str(PG/'psql.exe'),'-X','-qAt','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p',PORT,'-U','postgres','-d','testdb','-c']
 reader=subprocess.Popen([*args,reader_statement],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 writer=None
 try:
  deadline=time.monotonic()+10
  lock_seen=False
  while time.monotonic()<deadline:
   poll=subprocess.run([*args,f'select pg_try_advisory_lock({lock_key})'],text=True,capture_output=True,timeout=10)
   if poll.returncode: raise RuntimeError(poll.stderr)
   if poll.stdout.strip()=='f':
    lock_seen=True
    break
   time.sleep(0.02)
  if not lock_seen: raise RuntimeError('reader advisory lock was not observed')
  writer=subprocess.Popen([*args,writer_statement],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  wait_deadline=time.monotonic()+1.0
  writer_blocked=False
  while time.monotonic()<wait_deadline and writer.poll() is None:
   wait_query="select count(*) from pg_stat_activity where application_name='loop5a_stage_writer' and wait_event_type='Lock'"
   wait_state=subprocess.run([*args,wait_query],text=True,capture_output=True,timeout=10)
   if wait_state.returncode: raise RuntimeError(wait_state.stderr)
   if wait_state.stdout.strip()!='0':
    writer_blocked=True
    break
   time.sleep(0.02)
  reader_stdout,reader_stderr=reader.communicate(timeout=10)
  writer_stdout,writer_stderr=writer.communicate(timeout=10)
  return (writer_blocked,reader.returncode,reader_stdout.strip(),reader_stderr.strip(),writer.returncode,writer_stdout.strip(),writer_stderr.strip())
 finally:
  for process in (reader,writer):
   if process is not None and process.poll() is None:
    process.kill()
    process.communicate()
def main():
 BASE.mkdir(parents=True)
 try:
  call([str(PG/'initdb.exe'),'-D',str(DATA),'-U','postgres','-A','trust','-E','UTF8'])
  # On Windows pg_ctl's postmaster inherits child pipes; capture_output keeps the pipe open and hangs.
  # Match the proven Loop 2 disposable-PG harness: detach stdio, then read pg.log only on failure.
  start_rc=subprocess.call([str(PG/'pg_ctl.exe'),'-D',str(DATA),'-o',f'-p {PORT} -c listen_addresses=127.0.0.1','-l',str(BASE/'pg.log'),'-w','start'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL)
  if start_rc: raise RuntimeError((BASE/'pg.log').read_text(encoding='utf-8',errors='replace'))
  call([str(PG/'createdb.exe'),'-h','127.0.0.1','-p',PORT,'-U','postgres','testdb'])
  fixture=f"""create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
  grant usage on schema public to anon,authenticated,service_role;
  alter default privileges in schema public grant all on tables to anon,authenticated,service_role;
  alter default privileges in schema public grant all on functions to anon,authenticated,service_role;
  create schema auth; grant usage on schema auth to anon,authenticated,service_role;
  create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claims',true)::jsonb->>'sub','')::uuid $$;
  create function auth.role() returns text language sql stable as $$ select current_setting('request.jwt.claims',true)::jsonb->>'role' $$;
  create table public.profiles(id uuid primary key); create table public.role_profiles(id uuid primary key,user_id uuid not null references public.profiles(id) on delete cascade,target_role text not null);
  create table public.sessions(id uuid primary key default gen_random_uuid(),user_id uuid not null references public.profiles(id) on delete cascade,role_profile_id uuid references public.role_profiles(id) on delete set null);
  insert into profiles values('{A}'),('{B}'); insert into role_profiles values('{R}','{A}','SDE II'),('{RB}','{B}','SDE II');"""
  sql(fixture)
  sql(UP.read_text(encoding='utf-8'))
  sql(PROMPT.read_text(encoding='utf-8'))
  sql(f"insert into candidate_targets(id,user_id,role_profile_id,company_label,company_key,role_family_key) values('{T}','{A}','{R}','X','x','software_development_engineering'),('{TB}','{B}','{RB}','Y','y','business_analysis'),('{TC}','{A}','{R}','Z','z','software_development_engineering'); insert into interview_blueprints(user_id,candidate_target_id,version,catalog_version,catalog_sha256,match_state,rules_version) values('{A}','{T}',1,1,'{SHA}','NOT_RESEARCHED','base'),('{B}','{TB}',1,1,'{SHA}','NOT_RESEARCHED','base');")
  sql(MIG.read_text(encoding='utf-8'))
  sql(f"insert into sessions(id,user_id,role_profile_id) values('{S}','{A}','{R}'); insert into target_session_links(session_id,user_id,candidate_target_id,blueprint_id,round_key,competency_key) select '{S}','{A}','{T}',id,'general','behavioral' from interview_blueprints where candidate_target_id='{T}' and version=1;")
  check('session links pin the original blueprint version',f"select b.version from target_session_links l join interview_blueprints b on b.id=l.blueprint_id where l.session_id='{S}'",'1')
  expect('session link cannot be repointed',f"update target_session_links set blueprint_id=(select id from interview_blueprints where candidate_target_id='{T}' and version=2) where session_id='{S}'",'write-once')
  checks.append(('migration applies on actual base migrations',True,'ok'))
  server_version=sql('show server_version;')[0]
  checks.append(('PostgreSQL server version 16',server_version.startswith('16.'),server_version))
  check('legacy stage defaults','select candidate_stage_state||\':\'||candidate_stage_order_known||\':\'||candidate_stages::text||\':\'||candidate_stage_mapping_version||\':\'||candidate_stage_notes_revision from interview_blueprints where candidate_target_id=\''+T+'\';','NOT_ASKED:false:[]:0:0')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{TC}',0,1,'{SHA}','NOT_RESEARCHED','base');")
  check('new target first pin uses mapping version one',f"select version||':'||candidate_stage_state||':'||candidate_stage_mapping_version from interview_blueprints where candidate_target_id='{TC}'",'1:NOT_ASKED:1')
  append_same=f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{TC}',1,1,'{SHA}','NOT_RESEARCHED','base')"
  append_race=concurrent_sql([append_same,append_same])
  checks.append(('concurrent identical append pins are idempotent',len(append_race)==2 and all(rc==0 and out=='1' for rc,out,err in append_race),str(append_race)))
  check('identical append creates no duplicate blueprint',f"select count(*) from interview_blueprints where candidate_target_id='{TC}'",'1')
  expect('append rejects stale expected version',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{TC}',0,2,'{SHA}','GENERAL_ONLY','rules2')",'stale blueprint pin')
  check('atomic reader returns complete pinned blueprint',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{TC}',null)->'blueprint'->>'catalog_version'",'1')
  reader_stage=f'[{{"stage_id":"{ST2}","kind":"TECHNICAL_INTERVIEW","custom_label":null,"certainty":"SURE","sequence":null}}]'
  reader_notes=f'{{"{ST2}":"Before"}}'
  reader_after_stage=reader_stage.replace('"certainty":"SURE"','"certainty":"UNCERTAIN"')
  reader_after_notes=f'{{"{ST2}":"After"}}'
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{TC}',1,'KNOWN',false,'{reader_stage}'::jsonb,'{reader_notes}'::jsonb);")
  reader_sql=f"begin; set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{TC}',null); select pg_advisory_lock(810081); select pg_sleep(2.0); select pg_advisory_unlock(810081); commit"
  writer_sql=f"set application_name='loop5a_stage_writer'; set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{TC}',2,'KNOWN',false,'{reader_after_stage}'::jsonb,'{reader_after_notes}'::jsonb)"
  reader_race=reader_writer_race(reader_sql,writer_sql,810081)
  reader_blocked,reader_rc,reader_stdout,reader_stderr,writer_rc,writer_stdout,writer_stderr=reader_race
  reader_json=next((line for line in reader_stdout.splitlines() if line.startswith('{')),None)
  reader_value=json.loads(reader_json) if reader_json else {}
  coherent_old=reader_value.get('version')==2 and reader_value.get('blueprint',{}).get('version')==2 and reader_value.get('notes')=={ST2:'Before'}
  checks.append(('reader sees a coherent blueprint/notes snapshot before writer',reader_blocked and reader_rc==0 and coherent_old,str(reader_race)))
  checks.append(('writer resumes after reader transaction and saves successor',writer_rc==0 and writer_stdout=='3',str(reader_race)))
  check('concurrent reader/writer leaves new snapshot and note together',f"select version||':'||candidate_stage_notes_revision||':'||(candidate_stages->0->>'certainty')||':'||(select note from candidate_stage_notes where candidate_target_id='{TC}' and stage_id='{ST2}') from interview_blueprints where candidate_target_id='{TC}' order by version desc limit 1",'3:2:UNCERTAIN:After')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{T}',1,2,'{SHA}','GENERAL_ONLY','rules2');")
  check('append pin increments and preserves legacy state',f"select version||':'||candidate_stage_state||':'||candidate_stage_mapping_version from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'2:NOT_ASKED:0')
  expect('append rejects catalog version regression',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{T}',2,1,'{SHA}','GENERAL_ONLY','rules2')",'catalog version regression')
  expect('append rejects same-version hash change',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{T}',2,2,'{'b'*64}','GENERAL_ONLY','rules2')",'catalog version hash mismatch')
  for label,catalog_version,catalog_sha,match_state,rules_version in [
   ('append rejects invalid catalog version',0,SHA,'GENERAL_ONLY','rules2'),
   ('append rejects malformed catalog hash',3,'bad-sha','GENERAL_ONLY','rules2'),
   ('append rejects invalid match state',3,SHA,'FAKE_STATE','rules2'),
   ('append rejects blank rules version',3,SHA,'GENERAL_ONLY','   '),
  ]:
   expect(label,f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{T}',2,{catalog_version},'{catalog_sha}','{match_state}','{rules_version}')",'invalid blueprint pin')
  expect('append rejects mismatched owner and target',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{TB}',0,1,'{SHA}','NOT_RESEARCHED','base')",'target does not belong')
  expect('read rpc hides another owner target',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{TB}',null)",'target does not belong')
  stage=f'[{{"stage_id":"{ST}","kind":"OTHER","custom_label":"Panel","certainty":"SURE","sequence":null}}]'
  ordered_stage=stage.replace('"sequence":null','"sequence":1')
  notes=f'{{"{ST}":"Current only"}}'
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',2,'KNOWN',false,'{stage}'::jsonb,'{notes}'::jsonb);")
  check('valid plan and note save creates one successor',f"select version||':'||candidate_stage_mapping_version||':'||candidate_stage_notes_revision from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'3:1:1')
  long_label_stage=stage.replace('"custom_label":"Panel"','"custom_label":"'+'x'*81+'"')
  non_other_label_stage=stage.replace('"kind":"OTHER"','"kind":"BEHAVIORAL_INTERVIEW"')
  bad_certainty_stage=stage.replace('"certainty":"SURE"','"certainty":"MAYBE"')
  bad_uuid_stage=stage.replace(ST,'not-a-uuid')
  stage_missing_label=stage.replace('"custom_label":"Panel",','')
  stage_missing_sequence=stage.replace(',"sequence":null','')
  huge_sequence_stage=stage.replace('"sequence":null','"sequence":999999999999')
  uuidv7_stage=stage.replace(ST,'70000000-0000-7000-8000-000000000001')
  uuidv7_notes='{"70000000-0000-7000-8000-000000000001":"v7 note"}'
  gap_stage=stage.replace('"sequence":null','"sequence":2')
  duplicate_stage='['+stage[1:-1]+','+stage[1:-1]+']'
  too_many_stages='['+','.join([stage[1:-1]]*13)+']'
  absent_notes='{"50000000-0000-4000-8000-000000000002":"orphan"}'
  oversized_notes='{"'+ST+'":"'+'x'*501+'"}'
  invalid_cases=[
   ('null expected version','NULL',"'KNOWN'",'false',stage,notes,'invalid expected blueprint version'),
   ('negative expected version','-1',"'KNOWN'",'false',stage,notes,'invalid expected blueprint version'),
   ('null stage state','3','NULL','false','[]','{}','invalid candidate stage state or array'),
   ('null order flag','3',"'NOT_YET'",'NULL','[]','{}','invalid candidate stage state or array'),
   ('empty NOT_YET cannot assert known order','3',"'NOT_YET'",'true','[]','{}','non-known stage state'),
   ('KNOWN requires a stage','3',"'KNOWN'",'false','[]','{}','state/list mismatch'),
   ('known-order sequence gap rejected','3',"'KNOWN'",'true',gap_stage,'{}','contiguous and canonical'),
   ('oversized known sequence rejected safely','3',"'KNOWN'",'true',huge_sequence_stage,'{}','invalid stage sequence'),
   ('missing custom label rejected by exact-key validator','3',"'KNOWN'",'false',stage_missing_label,'{}','keys must be exact'),
   ('missing sequence rejected by exact-key validator','3',"'KNOWN'",'false',stage_missing_sequence,'{}','keys must be exact'),
   ('invalid stage certainty rejected','3',"'KNOWN'",'false',bad_certainty_stage,'{}','invalid stage certainty'),
   ('invalid stage UUID rejected','3',"'KNOWN'",'false',bad_uuid_stage,'{}','invalid stage UUID'),
   ('duplicate stage UUID rejected','3',"'KNOWN'",'false',duplicate_stage,'{}','duplicate stage uuid'),
   ('stage count above limit rejected','3',"'KNOWN'",'false',too_many_stages,'{}','invalid candidate stage state or array'),
   ('OTHER label above limit rejected','3',"'KNOWN'",'false',long_label_stage,'{}','invalid other custom label'),
   ('custom label rejected for standard kind','3',"'KNOWN'",'false',non_other_label_stage,'{}','custom_label only allowed'),
   ('note above limit rejected','3',"'KNOWN'",'false',stage,oversized_notes,'invalid candidate stage note'),
   ('note for absent stage rejected','3',"'KNOWN'",'false',stage,absent_notes,'note stage is absent'),
  ]
  for label,expected,state,order,stages,note_json,needle in invalid_cases:
   expect(label,f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',{expected},{state},{order},'{stages}'::jsonb,'{note_json}'::jsonb)",needle)
  check('RFC UUIDv7 stage and note IDs are accepted by RPC',f"begin; set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',3,'KNOWN',false,'{uuidv7_stage}'::jsonb,'{uuidv7_notes}'::jsonb); rollback",'4')
  check('authenticated owner reads own stage snapshot',f"set role authenticated; set request.jwt.claims='{{\"sub\":\"{A}\",\"role\":\"authenticated\"}}'; select count(*) from interview_blueprints where candidate_target_id='{T}' and candidate_stage_state='KNOWN'",'1')
  check('other owner cannot read stage snapshot',f"set role authenticated; set request.jwt.claims='{{\"sub\":\"{B}\",\"role\":\"authenticated\"}}'; select count(*) from interview_blueprints where candidate_target_id='{T}'",'0')
  uncertain=stage.replace('"certainty":"SURE"','"certainty":"UNCERTAIN"')
  identical_sql=f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',3,'KNOWN',false,'{uncertain}'::jsonb,'{notes}'::jsonb)"
  identical_results=concurrent_sql([identical_sql,identical_sql])
  checks.append(('concurrent identical writers converge on one version',len(identical_results)==2 and all(rc==0 and out=='4' for rc,out,err in identical_results),str(identical_results)))
  check('identical race inserts exactly one successor',f"select max(version)||':'||count(*) from interview_blueprints where candidate_target_id='{T}'",'4:4')
  check('candidate certainty accepts and stores uncertainty',f"select candidate_stages->0->>'certainty' from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'UNCERTAIN')
  stage_a=stage.replace('"custom_label":"Panel"','"custom_label":"Panel A"')
  stage_b=stage.replace('"custom_label":"Panel"','"custom_label":"Panel B"')
  conflict_sql=[f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',4,'KNOWN',false,'{candidate}'::jsonb,'{notes}'::jsonb)" for candidate in (stage_a,stage_b)]
  conflict_results=concurrent_sql(conflict_sql)
  successes=[r for r in conflict_results if r[0]==0 and r[1]=='5']
  stale_failures=[r for r in conflict_results if r[0]!=0 and 'stale candidate stage plan' in r[2].lower()]
  checks.append(('concurrent conflicting writers produce one commit and one stale rejection',len(successes)==1 and len(stale_failures)==1,str(conflict_results)))
  winner_label=sql(f"select candidate_stages->0->>'custom_label' from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1")[0]
  checks.append(('conflicting race leaves one contender snapshot',winner_label in ('Panel A','Panel B'),winner_label))
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',5,'KNOWN',false,'{stage}'::jsonb,'{notes}'::jsonb);")
  check('conflicting race can be followed by a versioned edit',f"select version||':'||candidate_stage_state from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'6:KNOWN')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.append_target_blueprint_pin('{A}','{T}',6,3,'{SHA}','GENERAL_ONLY','rules3');")
  check('refresh preserves stage snapshot and note revision',f"select version||':'||candidate_stage_state||':'||candidate_stage_mapping_version||':'||candidate_stage_notes_revision||':'||(candidate_stages->0->>'kind') from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'7:KNOWN:1:1:OTHER')
  check('refresh preserves current note',f"select count(*)||':'||max(note) from candidate_stage_notes where candidate_target_id='{T}'",'1:Current only')
  check('session remains pinned after plan edits and refresh',f"select b.version from target_session_links l join interview_blueprints b on b.id=l.blueprint_id where l.session_id='{S}'",'1')
  check('exact stale retry returns the current version',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',6,'KNOWN',false,'{stage}'::jsonb,'{notes}'::jsonb)",'7')
  check('exact stale retry creates no duplicate revision',f"select count(*) from interview_blueprints where candidate_target_id='{T}'",'7')
  check('current read latest_version',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{T}',null)->>'latest_version'",'7')
  check('historical read latest_version',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{T}',2)->>'latest_version'",'7')
  check('current read includes note',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{T}',null)->>'notes'",'{"50000000-0000-4000-8000-000000000001": "Current only"}')
  check('historical read excludes note',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.read_candidate_stage_plan('{A}','{T}',2)->>'notes'",'{}')
  for label,s,n in [
   ('extra JSON key',stage.replace('"sequence":null','"sequence":null,"extra":1'),'keys must be exact'),
   ('unknown sequence rejected',stage.replace('"sequence":null','"sequence":1'),'unknown order requires null'),
   ('wrong owner rejected',f"select public.save_candidate_stage_plan('{A}','{TB}',1,'KNOWN',false,'{stage}'::jsonb,'{{}}'::jsonb)",'target does not belong'),
   ('stale conflict rejected',f"select public.save_candidate_stage_plan('{A}','{T}',2,'NOT_YET',false,'[]'::jsonb,'{{}}'::jsonb)",'stale candidate'),
  ]:
   expect(label,f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',3,'KNOWN',false,'{s}'::jsonb,'{{}}'::jsonb)" if label in ('extra JSON key','unknown sequence rejected') else f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; {s}",n)
  check('stale conflict had no partial effect',f"select count(*) from interview_blueprints where candidate_target_id='{T}'",'7')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',7,'KNOWN',false,'{stage}'::jsonb,'{{}}'::jsonb);")
  check('explicit note clear creates revision and increments note counter',f"select version||':'||candidate_stage_state||':'||candidate_stage_notes_revision from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'8:KNOWN:2')
  check('explicit note clear physically deletes note row',f"select count(*) from candidate_stage_notes where candidate_target_id='{T}'",'0')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',8,'KNOWN',false,'{stage}'::jsonb,'{notes}'::jsonb);")
  check('readded note gets a fresh current row',f"select count(*)||':'||max(note) from candidate_stage_notes where candidate_target_id='{T}'",'1:Current only')
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',9,'NOT_YET',false,'[]'::jsonb,'{{}}'::jsonb);")
  check('stage removal creates empty plan and increments note counter',f"select version||':'||candidate_stage_state||':'||candidate_stages::text||':'||candidate_stage_notes_revision from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'10:NOT_YET:[]:4')
  check('stage removal physically deletes its note',f"select count(*) from candidate_stage_notes where candidate_target_id='{T}'",'0')
  check('removed stage remains in historical snapshot',f"select candidate_stage_state||':'||(candidate_stages->0->>'stage_id') from interview_blueprints where candidate_target_id='{T}' and version=9",'KNOWN:'+ST)
  sql(f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',10,'KNOWN',true,'{ordered_stage}'::jsonb,'{notes}'::jsonb);")
  check('restored ordered stage plan has new immutable version',f"select version||':'||candidate_stage_notes_revision from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'11:5')
  check('known order stores contiguous sequence one',f"select candidate_stage_order_known||':'||(candidate_stages->0->>'sequence') from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1",'true:1')
  expect('direct notes read denied',f"set role authenticated; set request.jwt.claims='{{\"sub\":\"{A}\",\"role\":\"authenticated\"}}'; select * from candidate_stage_notes",'permission denied')
  expect('anonymous notes read denied',"set role anon; set request.jwt.claims='{\"role\":\"anon\"}'; select * from candidate_stage_notes",'permission denied')
  expect('service-role blueprint insert denied',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; insert into interview_blueprints(user_id,candidate_target_id,version,catalog_version,catalog_sha256,match_state,rules_version) values('{A}','{T}',99,1,'{SHA}','NOT_RESEARCHED','direct')",'permission denied')
  check('RPC execution denied to anon and authenticated',"select has_function_privilege('anon','public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb)','execute')::text||':'||has_function_privilege('authenticated','public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb)','execute')::text",'false:false')
  check('RPC execution granted to service role',"select has_function_privilege('service_role','public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb)','execute')::text",'true')
  expect('anon cannot invoke stage reader',f"set role anon; set request.jwt.claims='{{\"role\":\"anon\"}}'; select public.read_candidate_stage_plan('{A}','{T}',null)",'permission denied')
  expect('authenticated cannot invoke stage save',f"set role authenticated; set request.jwt.claims='{{\"sub\":\"{A}\",\"role\":\"authenticated\"}}'; select public.save_candidate_stage_plan('{A}','{T}',7,'KNOWN',false,'{stage}'::jsonb,'{notes}'::jsonb)",'permission denied')
  expect('authenticated cannot invoke blueprint append',f"set role authenticated; set request.jwt.claims='{{\"sub\":\"{A}\",\"role\":\"authenticated\"}}'; select public.append_target_blueprint_pin('{A}','{T}',11,1,'{SHA}','NOT_RESEARCHED','base')",'permission denied')
  expect('immutable blueprint UPDATE preserved',f"update interview_blueprints set candidate_stage_state='NOT_YET' where candidate_target_id='{T}' and version=3",'immutable')
  archive_writer=f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',11,'KNOWN',false,'{uncertain}'::jsonb,'{notes}'::jsonb)"
  archive_update=f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; update candidate_targets set status='ARCHIVED',archived_at=now() where id='{T}'"
  archive_race=concurrent_sql([archive_writer,archive_update])
  write_result,archive_result=archive_race
  write_ok=write_result[0]==0 and write_result[1]=='12'
  write_rejected=write_result[0]!=0 and 'target is archived' in write_result[2].lower()
  checks.append(('save/archive race serializes to save-then-clear or archive-then-reject',archive_result[0]==0 and (write_ok or write_rejected),str(archive_race)))
  check('archiving target physically clears current notes',f"select count(*) from candidate_stage_notes where candidate_target_id='{T}'",'0')
  latest_snapshot=sql(f"select version||':'||candidate_stage_state||':'||(candidate_stages->0->>'stage_id') from interview_blueprints where candidate_target_id='{T}' order by version desc limit 1")[0]
  checks.append(('archive preserves immutable stage history',latest_snapshot in ('11:KNOWN:'+ST,'12:KNOWN:'+ST),latest_snapshot))
  check('session remains pinned after archive race',f"select b.version from target_session_links l join interview_blueprints b on b.id=l.blueprint_id where l.session_id='{S}'",'1')
  expect('archived target rejects stage save',f"set role service_role; set request.jwt.claims='{{\"role\":\"service_role\"}}'; select public.save_candidate_stage_plan('{A}','{T}',11,'NOT_YET',false,'[]'::jsonb,'{{}}'::jsonb)",'target is archived')
  before_refused_rollback=sql(f"select count(*) from interview_blueprints where candidate_target_id='{T}'")[0]
  _,err,rc=sql(DOWN.read_text(encoding='utf-8'),False); checks.append(('populated rollback refuses loss',rc!=0 and 'rollback refused' in err.lower(),err.strip()[:180]))
  after_refused_rollback=sql(f"select count(*) from interview_blueprints where candidate_target_id='{T}'")[0]
  checks.append(('refused rollback left stage history unchanged',after_refused_rollback==before_refused_rollback,after_refused_rollback))
  # Remove current plan/note and pin rows strictly on disposable database to exercise loss-free rollback.
  sql(f"delete from candidate_stage_notes where candidate_target_id='{T}'; delete from interview_blueprints where candidate_target_id='{T}' and version>1; delete from candidate_targets where id='{TC}';")
  sql(DOWN.read_text(encoding='utf-8'))
  check('rollback leaves base targets and blueprints',"select count(*) from interview_blueprints",'2')
  checks.append(('loss-free rollback applied',True,'ok'))
 finally:
  subprocess.run([str(PG/'pg_ctl.exe'),'-D',str(DATA),'-m','fast','-w','stop'],capture_output=True,text=True)
  shutil.rmtree(BASE,ignore_errors=True)
  print(f'cluster cleanup verified={not BASE.exists()}')
  for name,ok,detail in checks: print(('PASS' if ok else 'FAIL')+' '+name+(' :: '+detail if detail else ''))
  print(f'{sum(ok for _,ok,_ in checks)}/{len(checks)} checks passed')
  if not checks or not all(ok for _,ok,_ in checks): raise SystemExit(1)
if __name__=='__main__': main()
