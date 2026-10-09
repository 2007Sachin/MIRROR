import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { tmpdir } from 'node:os';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import ts from 'typescript';

const source = new URL('../src/lib/candidate-stage-editor-state.ts', import.meta.url);
const dir = await mkdtemp(join(tmpdir(), 'stage-state-'));
const js = join(dir, 'state.mjs');
await writeFile(js, ts.transpile(await (await import('node:fs/promises')).readFile(source, 'utf8'), { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 }));
const state = await import(pathToFileURL(js));
const stage = (id, kind='OTHER') => ({stage_id:id, kind, custom_label:kind==='OTHER'?'Panel':null, certainty:'SURE', sequence:1});

test('clones drafts and reorders without mutating source', () => {
 const plan={candidate_stage_state:'KNOWN',candidate_stage_order_known:true,candidate_stages:[stage('a'),stage('b')],notes:{a:'x'}};
 const draft=state.cloneStageDraft(plan); assert.notEqual(draft, plan); assert.notEqual(draft.stages, plan.candidate_stages);
 assert.deepEqual(state.moveStage(draft, 'a', 1).stages.map(x=>x.stage_id), ['b','a']);
 assert.deepEqual(plan.candidate_stages.map(x=>x.stage_id), ['a','b']);
});
test('removing a stage also removes its private note', () => { const d=state.cloneStageDraft({candidate_stage_state:'KNOWN',candidate_stage_order_known:false,candidate_stages:[stage('a')],notes:{a:'private'}}); const r=state.removeStage(d,'a'); assert.deepEqual(r.notes,{}); });
test('normalizes sequence only when order is known', () => { const d={state:'KNOWN',orderKnown:true,stages:[stage('a'),stage('b')],notes:{}}; assert.deepEqual(state.toStageSavePayload(d,7).stages.map(x=>x.sequence),[1,2]); d.orderKnown=false; assert.deepEqual(state.toStageSavePayload(d,7).stages.map(x=>x.sequence),[null,null]); });
test('clearing to unknown state removes stages and notes', () => { const d=state.setStageState({state:'KNOWN',orderKnown:true,stages:[stage('a')],notes:{a:'x'}},'NOT_YET'); assert.deepEqual(d.stages,[]); assert.deepEqual(d.notes,{}); });
test('rejects OTHER with blank custom label and KNOWN with no stages', () => { assert.equal(state.validateStageDraft({state:'KNOWN',stages:[{...stage('a'),custom_label:'  '}]}).valid,false); assert.equal(state.validateStageDraft({state:'KNOWN',stages:[]}).valid,false); });
test('caps additions at twelve and generates stable unique stage ids', () => { const d={state:'KNOWN',orderKnown:false,stages:Array.from({length:12},(_,i)=>stage(String(i))),notes:{}}; assert.equal(state.addStage(d).stages.length,12); const a=state.newStage(), b=state.newStage(); assert.ok(a.stage_id); assert.notEqual(a.stage_id,b.stage_id); });
test('a new stage starts uncertain until the person marks it more certain', () => { assert.equal(state.newStage().certainty, 'UNCERTAIN'); });
test('save payload trims notes and omits blank notes', () => { const d={state:'KNOWN',orderKnown:false,stages:[stage('a')],notes:{a:'  remember this  ', orphan:'x', blank:'   '}}; const payload=state.toStageSavePayload(d,3); assert.deepEqual(payload.notes,{a:'remember this'}); });
test('save payload uses the API certainty values without translating uncertainty', () => { const d={state:'KNOWN',orderKnown:false,stages:[{...stage('a'),certainty:'UNCERTAIN'}],notes:{}}; const payload=state.toStageSavePayload(d,3); assert.deepEqual(payload.stages.map((item) => item.certainty),['UNCERTAIN']); d.stages[0].certainty='SURE'; assert.deepEqual(state.toStageSavePayload(d,3).stages.map((item) => item.certainty),['SURE']); });
test('validator rejects too many stages and custom labels over the API limit', () => { const tooMany={state:'KNOWN',stages:Array.from({length:13},(_,i)=>stage(String(i),'TECHNICAL_INTERVIEW'))}; assert.equal(state.validateStageDraft(tooMany).valid,false); assert.equal(state.validateStageDraft({state:'KNOWN',stages:[{...stage('a'),custom_label:'x'.repeat(81)}]}).valid,false); });
after(async()=>rm(dir,{recursive:true,force:true}));
