// Verify the official Harness MCP plugin in isolation, without a model request.
import assert from 'node:assert/strict';
import { readFileSync, realpathSync } from 'node:fs';
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';

const { values } = parseArgs({ options: {
  'harness-package': { type: 'string' }, overlay: { type: 'string' },
  'check-canvas': { type: 'boolean', default: false },
} });
assert(values['harness-package'] && values.overlay,
  'Usage: node scripts/verify_deepseek.mjs --harness-package /path/to/@deepseek-ai/dsh/package.json --overlay /path/to/export.yml [--check-canvas]');
const packagePath = realpathSync(values['harness-package']);
const metadata = JSON.parse(readFileSync(packagePath, 'utf8'));
assert.equal(metadata.name, '@deepseek-ai/dsh');
const requireHarness = createRequire(packagePath);
const load = name => import(pathToFileURL(requireHarness.resolve(name)).href);
const { Context } = await load('@deepseek-ai/cordis');
const tools = await load('@deepseek-ai/dsh-tools');
const prompt = await load('@deepseek-ai/dsh-system-prompt');
const client = await load('@deepseek-ai/dsh-mcp-client');
const overlay = JSON.parse(readFileSync(values.overlay, 'utf8'));
assert.equal(overlay.length, 1);
assert.equal(overlay[0].insert.length, 1);
const row = overlay[0].insert[0];
assert.equal(row.name, '@deepseek-ai/dsh-mcp-client');
const config = client.Config({ ...row.config, failOnStartupError: true });
const prefix = `mcp__${config.serverName}__`;
const ctx = new Context();
const fibers = [];
try {
  for (const [plugin, options] of [[prompt.default, undefined], [tools.default, undefined], [client, config]]) {
    const fiber = ctx.plugin(plugin, options);
    fibers.push(fiber);
    await fiber;
  }
  const deadline = Date.now() + 20000;
  let names = [];
  do {
    names = ctx.tools.schemas().map(tool => tool.name).filter(name => name.startsWith(prefix)).sort();
    if (names.length === 14) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  } while (Date.now() < deadline);
  assert.equal(names.length, 14, 'Harness must discover all 14 Canvas tools');
  assert(names.includes(prefix + 'get_upcoming_work'));
  assert(names.includes(prefix + 'get_assignment_context'));
  assert(names.includes(prefix + 'read_material'));
  // Invalid IDs fail before any Canvas HTTP request. Requires configured fixtures
  // or the user's locally authorized configuration; no credential is printed.
  const invalid = await ctx.tools.execute({ callId: 'canvas-invalid-id', name: prefix + 'get_assignment',
    arguments: { course_id: '../1', assignment_id: '2' }, signal: AbortSignal.timeout(15000) });
  assert.equal(invalid.isError, true, 'An MCP error must remain a Harness error');
  let account = { tested: false };
  if (values['check-canvas']) {
    const result = await ctx.tools.execute({ callId: 'canvas-courses', name: prefix + 'list_courses',
      arguments: { limit: 5 }, signal: AbortSignal.timeout(45000) });
    assert.equal(result.isError, false, 'Authorized Canvas call failed; private result withheld');
    account = { tested: true, ok: true };
  }
  console.log(JSON.stringify({ ok: true, harness_version: metadata.version, tool_count: names.length,
    tools: names, mcp_error_preserved: true, canvas_connection: account, model_requests: 0 }, null, 2));
} finally {
  for (const fiber of fibers.reverse()) await fiber.dispose();
}
