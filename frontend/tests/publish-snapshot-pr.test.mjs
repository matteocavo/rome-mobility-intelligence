import { test } from 'node:test';
import assert from 'node:assert/strict';
import { publishSnapshot, sameSnapshot } from '../scripts/publish-snapshot-pr.mjs';

const stamp = '2026-10-29T06:00:00Z';
const snapshot = {
  version: 1, capturedAt: stamp,
  summary: {coverage:'current_scoring_population',scored_count:1,route_count:1,
    observed_delay_distribution:{early:0,minor:1,moderate:0,major:0,critical:0},source_watermark:stamp,query_generated_at:stamp},
  current: {coverage:'current_scoring_population',total:1,page:1,page_size:20,total_pages:1,
    source_watermark:stamp,population_generated_at:stamp,
    items:[{observation_id:'observation',stop_id:'stop',threshold:.35,major_delay_probability:.6,
      predicted_major_delay:true,source_watermark:stamp}]},
};
function harness({existing=true,pr='12',previous={},candidate=snapshot,failMerge=false}={}) {
  const calls=[]; let reads=0;
  return {
    calls,
    options: {
      read:()=>JSON.stringify(reads++===0?candidate:previous),
      write:(_path,bytes)=>calls.push(['write',bytes]),
      run:(exe,args)=>{
        calls.push([exe,...args]);
        if (exe==='git' && args[0]==='branch') return args[1]==='--show-current'?'main':existing?'origin/snapshot-refresh':'';
        if (exe==='git' && args[0]==='diff') return args[1]==='--name-only'?'frontend/src/data/snapshot.json':'snapshot diff';
        if (exe==='git' && args[0]==='merge' && failMerge) throw new Error('merge conflict');
        if (exe==='gh' && args[0]==='pr' && args[1]==='list') return pr;
        return '';
      },
    },
  };
}
const has=(calls,exe,...args)=>calls.some(call=>call[0]===exe && args.every((arg,i)=>call[i+1]===arg));

test('unchanged data ignores capture time and JSON property order',()=>{
  assert.equal(sameSnapshot(snapshot,{...snapshot,capturedAt:'2026-10-30T00:00:00Z'}),true);
  assert.equal(sameSnapshot({a:1,b:2},{b:2,a:1}),true);
});
test('existing PR is reused; candidate survives checkout; CI dispatch targets refresh branch',()=>{
  const {calls,options}=harness();publishSnapshot(options);
  assert.equal(has(calls,'gh','pr','create'),false);
  assert.ok(has(calls,'git','push','origin','snapshot-refresh'));
  assert.ok(calls.findIndex(c=>c[0]==='write')>calls.findIndex(c=>c[1]==='merge'));
  assert.deepEqual(JSON.parse(calls.find(c=>c[0]==='write')[1]),snapshot);
  for(const workflow of ['quality.yml','frontend.yml'])assert.ok(has(calls,'gh','workflow','run',workflow,'--ref','snapshot-refresh'));
  assert.equal(calls.some(c=>c.includes('--hard')||c.includes('--force')),false);
});
test('new branch creates exactly one PR',()=>{
  const {calls,options}=harness({existing:false,pr:''});publishSnapshot(options);
  assert.ok(has(calls,'git','switch','--create','snapshot-refresh','origin/main'));
  assert.equal(calls.filter(c=>c[0]==='gh'&&c[1]==='pr'&&c[2]==='create').length,1);
});
test('unchanged main snapshot creates no commit, branch push or PR',()=>{
  const {calls,options}=harness({existing:false,previous:snapshot});publishSnapshot(options);
  assert.equal(has(calls,'git','commit'),false);assert.equal(has(calls,'git','push'),false);
  assert.equal(has(calls,'gh','pr','create'),false);
});
test('repeated run reuses existing PR without capture-only commit',()=>{
  const {calls,options}=harness({previous:{...snapshot,capturedAt:'older capture'}});publishSnapshot(options);
  assert.equal(has(calls,'git','commit'),false);assert.equal(has(calls,'gh','pr','create'),false);
  assert.ok(has(calls,'gh','workflow','run','quality.yml'));
});
test('invalid candidate is rejected before any Git operation',()=>{
  const {calls,options}=harness({candidate:{}});assert.throws(()=>publishSnapshot(options));assert.equal(calls.length,0);
});
test('merge conflict fails closed without pushing or opening a PR',()=>{
  const {calls,options}=harness({failMerge:true});assert.throws(()=>publishSnapshot(options));
  assert.equal(has(calls,'git','push'),false);assert.equal(has(calls,'gh','pr','create'),false);
});
