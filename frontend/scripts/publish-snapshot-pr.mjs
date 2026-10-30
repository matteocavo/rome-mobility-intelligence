import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { validateSnapshot } from '../src/api/snapshotSchema.js';

const file = 'frontend/src/data/snapshot.json';
const branch = 'snapshot-refresh';
function command(executable, args) {
  return execFileSync(executable, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.keys(value).sort().filter(key => key !== 'capturedAt').map(key => [key, canonical(value[key])]),
  );
  return value;
}
export function sameSnapshot(a, b) {
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

// Dependency injection permits offline tests; the CLI is restricted to the main workflow.
export function publishSnapshot({ run = command, read = readFileSync, write = writeFileSync } = {}) {
  const candidateBytes = read(file, 'utf8');
  const candidate = JSON.parse(candidateBytes);
  if (!validateSnapshot(candidate)) throw new Error('Invalid candidate; refusing publication');
  const git = (...args) => run('git', args);
  const gh = (...args) => run('gh', args);
  if (git('branch', '--show-current') !== 'main') throw new Error('Refresh must start on main');
  const dirty = git('diff', '--name-only', 'HEAD').split(/\r?\n/).filter(Boolean);
  if (dirty.some(path => path !== file)) throw new Error('Unexpected changes in workflow checkout');
  // Preserve the candidate in memory before checkout, never reset away the generated file.
  git('restore', '--source=HEAD', '--staged', '--worktree', '--', file);
  git('fetch', 'origin', '+refs/heads/*:refs/remotes/origin/*');
  const existing = git('branch', '--remotes', '--list', `origin/${branch}`).trim();
  if (existing) {
    git('switch', '--create', branch, '--track', `origin/${branch}`);
    git('merge', '--no-edit', 'origin/main'); // Conflicts fail closed; no force push.
  } else git('switch', '--create', branch, 'origin/main');
  const previous = JSON.parse(read(file, 'utf8'));
  const changed = !sameSnapshot(previous, candidate);
  if (changed) {
    write(file, candidateBytes);
    git('add', '--', file);
    git('commit', '-m', 'chore: refresh last-known-good frontend snapshot');
  }
  // A merge from main may need pushing even when snapshot content is unchanged.
  if (!changed && !existing) return { status: 'unchanged' };
  git('push', 'origin', branch);
  let pr = gh('pr', 'list', '--state', 'open', '--base', 'main', '--head', branch,
    '--json', 'number', '--jq', '.[0].number // empty');
  if (!pr) {
    // Do not create an empty PR if the old refresh branch was already merged.
    if (!git('diff', 'origin/main...HEAD', '--', file)) return { status: 'unchanged' };
    pr = gh('pr', 'create', '--base', 'main', '--head', branch,
      '--title', 'Refresh last-known-good frontend snapshot', '--body',
      'Validated public data refresh. Required CI is explicitly dispatched on this branch. Human review and merge required.');
  }
  // workflow_dispatch is explicitly supported with GITHUB_TOKEN; no PAT or approval bypass.
  for (const workflow of ['quality.yml', 'frontend.yml']) {
    gh('workflow', 'run', workflow, '--ref', branch);
  }
  return { status: changed ? 'updated' : 'unchanged', pr };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { console.log(JSON.stringify(publishSnapshot())); }
  catch { console.error('Snapshot PR publication failed; inspect the workflow step. No automatic merge.'); process.exitCode = 1; }
}
