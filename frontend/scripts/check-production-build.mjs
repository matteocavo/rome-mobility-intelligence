/** Validate the actual Pages artifact, not just the source Vite config. */
import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
const root=resolve('dist');
const base='/rome-mobility-intelligence/';
const html=readFileSync(join(root,'index.html'),'utf8');
const urls=[...html.matchAll(/(?:src|href)="([^"#]+)"/g)].map(match=>match[1]);
const local=urls.filter(url=>!url.startsWith('https://')&&!url.startsWith('data:'));
assert.ok(local.length>=2,'Missing production JS/CSS');
for(const url of local){
  assert.ok(url.startsWith(base),`Invalid asset base: ${url}`);
  assert.ok(existsSync(join(root,url.slice(base.length))),'Missing local asset');
}
const files=readdirSync(join(root,'assets'));
for(const file of files.filter(name=>name.endsWith('.css'))){
  const css=readFileSync(join(root,'assets',file),'utf8');
  for(const match of css.matchAll(/url\(["']?([^"')]+)["']?\)/g)){
    const url=match[1];
    if(url.startsWith('data:')||url.startsWith('https://')||url.startsWith('#'))continue;
    const resolved=new URL(url,`https://matteocavo.github.io${base}assets/${file}`).pathname;
    assert.ok(resolved.startsWith(base),'CSS asset escapes Pages base');
    assert.ok(existsSync(join(root,decodeURIComponent(resolved.slice(base.length)))),'Missing CSS/Leaflet asset');
  }
}
assert.ok(!files.some(file=>file.endsWith('.map')),'Source maps must not be published');
const js=files.filter(file=>file.endsWith('.js')).map(file=>readFileSync(join(root,'assets',file),'utf8')).join('\n');
assert.ok(js.includes('https://rome-mobility-intelligence-matteocavo.onrender.com'));
for(const forbidden of ['RMI_SERVICE_API_KEY','DATABRICKS_CLIENT_SECRET','DATABASE_URL',
  'pipeline.joblib','/predictions/current/persist'])assert.ok(!js.includes(forbidden),`Forbidden production reference: ${forbidden}`);
assert.ok(!/gh[pousr]_[A-Za-z0-9]{30,}|dapi[a-f0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(js),'Potential secret in artifact');
assert.ok(!html.includes('/src/main.tsx'),'Uncompiled entry point');
console.log(`Pages artifact PASS: ${base}; ${files.length} assets; fixed public API origin; no source maps/mocks/private routes`);
