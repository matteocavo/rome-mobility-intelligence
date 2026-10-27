// Controlled interpreter for this export's graph/expressions, not an n8n runtime.
import fs from 'node:fs';
import vm from 'node:vm';

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const nodes = Object.fromEntries(input.workflow.nodes.map(n => [n.name, n]));
const seen = {};
const calls = [];
const waits = [];
const attempts = {};
let data = {};
let name = input.start || 'Manual Trigger';
let terminal;
const context = () => ({
  $json: data,
  $now: {toUTC: () => ({toISO: () => '2026-10-27T12:00:00.000Z'})},
  $: key => ({first: () => {
    if (!(key in seen)) throw new Error('Missing previous-node data');
    return {json: seen[key]};
  }}),
});
function evaluate(value) {
  if (typeof value !== 'string' || !value.startsWith('={{ ')) return value;
  return vm.runInNewContext('(' + value.slice(3, -2) + ')', context(), {timeout: 100});
}
for (let steps = 0; steps < 100; steps++) {
  const node = nodes[name];
  if (!node) throw new Error('Unknown node');
  let branch = 0;
  const type = node.type.split('.').at(-1);
  if (type === 'httpRequest') {
    const url = new URL(evaluate(node.parameters.url));
    const endpoint = url.pathname + url.search;
    calls.push({method: node.parameters.method, endpoint});
    const replies = input.responses[endpoint];
    if (!replies?.length) throw new Error('Unexpected endpoint');
    const index = attempts[endpoint] || 0;
    data = structuredClone(replies[Math.min(index, replies.length - 1)]);
    attempts[endpoint] = index + 1;
  } else if (type === 'set') {
    const fields = Object.fromEntries(node.parameters.assignments.assignments.map(
      assignment => [assignment.name, evaluate(assignment.value)]));
    data = node.parameters.includeOtherFields ? {...data, ...fields} : fields;
  } else if (type === 'if') {
    const conditions = node.parameters.conditions;
    if (conditions.conditions.length !== 1) throw new Error('Unsupported condition');
    branch = evaluate(conditions.conditions[0].leftValue) === true ? 0 : 1;
  } else if (type === 'wait') {
    waits.push(node.parameters.amount); // Simulated time: no actual wait/network access.
  } else if (type === 'webhook') {
    data = input.authenticatedPayload || {};
  } else if (type === 'respondToWebhook') {
    data = {http_status: node.parameters.options.responseCode,
            body: JSON.parse(node.parameters.responseBody)};
  } else if (!['manualTrigger', 'scheduleTrigger'].includes(type)) {
    throw new Error('Forbidden node');
  }
  seen[name] = structuredClone(data);
  const next = input.workflow.connections[name]?.main?.[branch] || [];
  if (next.length > 1) throw new Error('Fan-out forbidden');
  if (!next.length) {terminal = name; break;}
  name = next[0].node;
}
if (!terminal) throw new Error('Graph did not terminate');
process.stdout.write(JSON.stringify({terminal, summary: data, calls, waits}));
