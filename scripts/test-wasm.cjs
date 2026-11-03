// Run against scripts/serve-wasm.sh. Requires Playwright + Chromium/Chrome.
const { chromium } = require(process.env.MIO_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const base = process.env.MIO_PLAYGROUND_URL || 'http://127.0.0.1:8787';
const reportDir = path.join(root, 'build/wasm-report');
fs.mkdirSync(reportDir, { recursive: true });
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.MIO_BROWSER_CHANNEL ? { channel: process.env.MIO_BROWSER_CHANNEL } : {}) });
  const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
  const checks = [];
  const record = (name, details) => { checks.push({ name, pass: true, details }); console.log(`PASS ${name}`); };
  try {
    await page.goto(base);
    assert.equal(await page.title(), 'Mio · Browser Playground');
    await page.waitForFunction(() => !document.getElementById('run').disabled);
    record('Browser loads Go Wasm, meaningful UI and controls', await page.locator('#loading').innerText());
    const baseline = JSON.parse(fs.readFileSync(path.join(root, 'build/playground/native-results.json'), 'utf8'));
    const examples = JSON.parse(fs.readFileSync(path.join(root, 'web/playground/examples.json'), 'utf8'));
    const timings = [];
    const ready = () => page.waitForFunction(() => !document.getElementById('run').disabled);
    const run = async (source, operation = 'run') => {
      await ready();
      await page.locator('#source').fill(source);
      await page.locator(`#${operation}`).click();
      await page.waitForFunction(() => !['Running…', 'Initializing'].includes(document.getElementById('status').textContent));
      await ready();
      return { status: await page.locator('#status').innerText(), stdout: await page.locator('#stdout').innerText(), diagnostics: await page.locator('#diagnostics').innerText() };
    };
    for (const example of examples.filter(example => !example.limited)) {
      const actual = await run(example.source);
      assert.equal(actual.status, baseline[example.name].status);
      assert.equal(actual.stdout, baseline[example.name].stdout);
      if (example.diagnostic) assert.equal(actual.diagnostics, baseline[example.name].diagnostics.join('\n'));
      else assert.equal(actual.diagnostics, '');
      timings.push({ example: example.name, timing: await page.locator('#timing').innerText() });
      record(`${example.name}: browser/native parity`);
    }
    for (let index = 0; index < 3; index++) {
      assert.equal((await run(examples[0].source)).stdout, examples[0].stdout);
      timings.push({ example: `Hello World repeat ${index + 1}`, timing: await page.locator('#timing').innerText() });
    }
    record('Three repeated Hello World executions return identical output');
    const checked = await run('chant("must not execute");', 'check');
    assert.equal(checked.status, 'checked'); assert.equal(checked.stdout, '');
    const badCheck = await run(examples.find(e => e.diagnostic).source, 'check');
    assert.equal(badCheck.status, 'diagnostic'); assert.equal(badCheck.diagnostics, baseline['Type error'].diagnostics.join('\n'));
    record('Check compiles without execution and reports real type error');
    await run('kaku only_here = 42;');
    assert.equal((await run('chant(only_here);')).status, 'diagnostic');
    assert.equal((await run('chant("clean");')).stdout, 'clean\n');
    record('Consecutive requests have isolated globals and recover from diagnostics');
    for (const source of ['yobu "kiso/fs";', 'yobu "kiso/io";', 'yobu "../secrets";']) {
      const result = await run(source); assert.equal(result.status, 'diagnostic');
      assert.match(result.diagnostics, /unsupported|invalid Bunko/);
    }
    record('Closed Bunko FS rejects unavailable capabilities and traversal');
    const flood = await run('aida (hai) { chant("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"); }');
    assert.equal(flood.status, 'error'); assert.match(flood.diagnostics, /output limit exceeded/);
    assert.equal(Buffer.byteLength(flood.stdout), 65536);
    record('Output stops at 65536 bytes');
    const budget = await run('aida (hai) {}');
    assert.equal(budget.status, 'error'); assert.match(budget.diagnostics, /instruction limit/);
    record('Existing VM instruction budget ends infinite loop');
    await ready(); await page.locator('#source').fill('aida (hai) {}');
    await page.locator('#run').click(); await page.locator('#stop').click();
    assert.equal(await page.locator('#status').innerText(), 'cancelled');
    assert.equal((await run('chant("after stop");')).stdout, 'after stop\n');
    record('Real Stop terminates infinite Worker; recreated runtime runs again');
    // Use real controllers and real Workers for lifecycle race, timeout and error tests.
    const lifecycle = await page.evaluate(async () => {
      const { Playground } = await import('./client.js');
      const results = [];
      const p = new Playground(() => {}, r => results.push(r), { timeoutMs: 1 });
      const until = async fn => { const deadline = Date.now() + 20000; while (!fn()) { if (Date.now() > deadline) throw Error('lifecycle timeout'); await new Promise(r => setTimeout(r, 10)); } };
      await until(() => p.ready);
      const oldMessage = p.worker.onmessage;
      p.execute('run', 'aida (hai) {}');
      await until(() => results.length > 0);
      const timedOut = results[0].status;
      await until(() => p.ready);
      p.timeoutMs = 5000;
      p.execute('run', 'chant("new generation");');
      oldMessage({ data: { operation: 'result', id: p.active, status: 'ok', stdout: 'STALE' } });
      await until(() => results.length > 1);
      p.dispose();
      return { timedOut, results };
    });
    assert.equal(lifecycle.timedOut, 'timeout');
    assert.equal(lifecycle.results.length, 2);
    assert.equal(lifecycle.results[1].stdout, 'new generation\n');
    record('External timeout kills Worker; late old-generation message ignored');
    // Inject a real Worker exception into the actual UI, then restore and reload.
    await page.route('**/worker.js', route => route.fulfill({ contentType: 'application/javascript', body: 'throw new Error("injected Worker crash");' }));
    await page.locator('#stop').click();
    await page.waitForFunction(() => document.getElementById('diagnostics').textContent.includes('injected Worker crash'));
    assert.equal(await page.locator('#status').innerText(), 'error');
    await page.unroute('**/worker.js');
    await page.locator('#stop').click(); await ready();
    assert.equal((await run('chant("recovered");')).stdout, 'recovered\n');
    record('Worker exception displayed in UI; reload recovers');
    // Expected injected Worker exception is handled, not a main-thread pageerror.
    assert.deepEqual(errors, []);
    record('No unhandled page errors, console warnings or errors');
    await page.screenshot({ path: path.join(reportDir, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(reportDir, 'mobile.png'), fullPage: true });
    record('Desktop and mobile render without horizontal overflow');
    fs.writeFileSync(path.join(reportDir, 'browser-results.json'), JSON.stringify({ browser: await browser.version(), url: base, checks, timings, errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
