// Real-browser tests of the static playground (build/web) and its Web reference VM.
// Fixtures (reference results and .mochi files from the Go reference CLI and the native
// pure-Mio CLI) are written by tests/web/differential.py --fixtures; they are required.
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixtures = path.resolve(here, process.env.MIO_WEB_FIXTURES || '../../../build/web-fixtures');
const requestsLog = path.resolve(here, '../../../build/web-report/requests.jsonl');
const index = JSON.parse(fs.readFileSync(path.join(fixtures, 'index.json'), 'utf8'));

let pageErrors;
test.beforeEach(async ({ page }) => {
  pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') pageErrors.push(message.text()); });
});
test.afterEach(() => { expect(pageErrors).toEqual([]); });

async function open(page, query = '') {
  await page.goto('index.html' + query);
  await expect(page.locator('#run')).toBeEnabled();
}

async function finished(page) {
  await expect(page.locator('body')).toHaveAttribute('data-last-status', /.+/);
  await expect(page.locator('#run')).toBeEnabled(); // replacement Worker is ready
  return {
    status: await page.locator('body').getAttribute('data-last-status'),
    stdout: await page.locator('#stdout').textContent(),
    diagnostics: await page.locator('#diagnostics').textContent(),
    line: await page.locator('#status').textContent(),
  };
}

async function runSource(page, source, button = '#run') {
  await page.locator('#source').fill(source);
  await page.locator(button).click();
  return finished(page);
}

async function importMochi(page, file) {
  await page.locator('#import').setInputFiles(path.join(fixtures, file));
  return finished(page);
}

test('loads the static build and runs the default example locally', async ({ page }) => {
  await open(page);
  await expect(page).toHaveTitle('Mio Playground');
  await page.locator('#run').click();
  const result = await finished(page);
  expect(result.status).toBe('ok');
  expect(result.stdout).toBe('こんにちは、Mio 🍡\n');
  expect(result.line).toContain('exit 0');
});

test('source runs match the reference CLI exactly', async ({ page }) => {
  await open(page);
  for (const entry of index.cases) {
    const result = await runSource(page, entry.source);
    expect(result.stdout, entry.name).toBe(entry.stdout);
    expect(result.diagnostics, entry.name).toBe(entry.stderr);
    expect(result.line, entry.name).toContain(`exit ${entry.exitCode}`);
  }
});

test('imported .mochi from the native CLI (mio build --emit=mochi) matches the reference VM', async ({ page }) => {
  await open(page);
  const native = index.cases.filter(entry => entry.nativeMochi);
  expect(native.length).toBeGreaterThanOrEqual(7);
  for (const entry of native) {
    const result = await importMochi(page, entry.nativeMochi);
    expect(result.stdout, entry.name).toBe(entry.nativeExec.stdout);
    expect(result.diagnostics, entry.name).toBe(entry.nativeExec.stderr);
    expect(result.line, entry.name).toContain(`exit ${entry.nativeExec.exitCode}`);
    expect(result.line, entry.name).toContain('Mochi v16');
    await expect(page.locator('#bytecode-info')).toContainText('header v16');
  }
  // Re-run the last imported file without re-importing.
  await page.locator('#run-bytecode').click();
  expect((await finished(page)).status).toMatch(/ok|runtime_error/);
});

test('imported .mochi from the Go reference CLI runs and Download .mochi matches mio build bytes', async ({ page }) => {
  await open(page);
  const entry = index.cases.find(item => item.name === 'enums');
  const result = await importMochi(page, entry.goMochi);
  expect(result.stdout).toBe(entry.stdout);
  await page.locator('#source').fill(entry.source);
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#download').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('main.mochi');
  const bytes = fs.readFileSync(await download.path());
  expect(Buffer.compare(bytes, fs.readFileSync(path.join(fixtures, entry.goMochi)))).toBe(0);
  expect((await finished(page)).status).toBe('compiled');
});

test('Check reports diagnostics without executing', async ({ page }) => {
  await open(page);
  const clean = await runSource(page, 'chant("must not run");', '#check');
  expect(clean.status).toBe('checked');
  expect(clean.stdout).toBe('');
  const bad = index.cases.find(item => item.name === 'compile_type_error');
  const result = await runSource(page, bad.source, '#check');
  expect(result.status).toBe('diagnostic');
  expect(result.diagnostics).toBe(bad.stderr);
  expect(result.diagnostics).toContain('main.mio:1:17');
});

test('runtime errors are reported with partial stdout', async ({ page }) => {
  await open(page);
  const entry = index.cases.find(item => item.name === 'runtime_divide_by_zero');
  const result = await runSource(page, entry.source);
  expect(result.status).toBe('runtime_error');
  expect(result.stdout).toBe('before\n');
  expect(result.diagnostics).toContain('division by zero');
});

test('invalid .mochi files are rejected safely and the playground recovers', async ({ page }) => {
  await open(page);
  const result = await importMochi(page, 'bad-version.mochi');
  expect(result.status).toBe('rejected');
  expect(result.diagnostics).toContain('unsupported format version 99');
  await page.locator('#import').setInputFiles({ name: 'junk.mochi', mimeType: 'application/octet-stream', buffer: Buffer.from('not mochi') });
  expect((await finished(page)).diagnostics).toContain('invalid file signature');
  expect((await runSource(page, 'chant("still fine");')).stdout).toBe('still fine\n');
});

test('host capabilities in a .mochi are denied', async ({ page }) => {
  await open(page);
  expect(index.capability).toContain('native');
  for (const origin of index.capability) {
    const result = await importMochi(page, `capability.${origin}.mochi`);
    expect(result.status, origin).toBe('runtime_error');
    expect(result.stdout, origin).toBe('before\n');
    expect(result.diagnostics, origin).toContain('host capability is not available in the Web playground: mio/fs/runtime.open');
  }
  const source = await runSource(page, 'yobu "kiso/fs";\nchant("never");');
  expect(source.status).toBe('diagnostic');
  expect(source.diagnostics).toContain('unsupported Bunko package "kiso/fs"');
});

test('Stop terminates an infinite loop and a new Worker takes over', async ({ page }) => {
  await open(page, '?timeout=60000&instructions=2000000000');
  const before = await page.evaluate(() => window.mioPlayground.workersCreated);
  await page.locator('#source').fill('kaku i = 0;\naida (hai) { i = i + 1; }');
  await page.locator('#run').click();
  await expect(page.locator('#stop')).toBeEnabled();
  await page.waitForTimeout(500);
  await page.locator('#stop').click();
  const stopped = await finished(page);
  expect(stopped.status).toBe('cancelled');
  expect(stopped.diagnostics).toContain('Worker terminated');
  expect(await page.evaluate(() => window.mioPlayground.workersCreated)).toBe(before + 1);
  expect((await runSource(page, 'chant("after stop");')).stdout).toBe('after stop\n');
});

test('the time limit terminates a run and the Worker is recreated', async ({ page }) => {
  await open(page, '?timeout=1500&instructions=2000000000');
  const started = Date.now();
  const result = await runSource(page, 'aida (hai) {}');
  expect(result.status).toBe('timeout');
  expect(result.diagnostics).toContain('timed out after 1500 ms');
  expect(Date.now() - started).toBeLessThan(15000);
  expect((await runSource(page, 'chant("recreated");')).stdout).toBe('recreated\n');
});

test('VM instruction, stdout and source limits', async ({ page }) => {
  await open(page, '?instructions=1000');
  const budget = await runSource(page, 'aida (hai) {}');
  expect(budget.status).toBe('runtime_error');
  expect(budget.diagnostics).toContain('instruction limit 1000 exceeded');
  await open(page);
  const flood = await runSource(page, 'aida (hai) { chant("0123456789abcdef0123456789abcdef"); }');
  expect(flood.status).toBe('runtime_error');
  expect(flood.diagnostics).toContain('output limit exceeded');
  expect(Buffer.byteLength(flood.stdout)).toBe(1024 * 1024);
  const big = await runSource(page, 'chant(1);' + ' '.repeat(256 * 1024));
  expect(big.status).toBe('rejected');
  expect(big.diagnostics).toContain('source limit exceeded');
});

test('runs are isolated: every request gets a fresh Worker and runtime', async ({ page }) => {
  await open(page);
  const first = await page.evaluate(() => window.mioPlayground.workersCreated);
  await runSource(page, 'kaku only_here = 42; chant(only_here);');
  const second = await runSource(page, 'chant(only_here);');
  expect(second.status).toBe('diagnostic');
  expect(second.diagnostics).toContain('only_here');
  expect(await page.evaluate(() => window.mioPlayground.workersCreated)).toBe(first + 2);
});

test('source code never leaves the browser', async ({ page }) => {
  await open(page);
  const marker = 'SECRET_MARKER_' + Date.now();
  const seen = [];
  page.on('request', request => seen.push({ method: request.method(), url: request.url(), body: request.postData() }));
  await runSource(page, `chant("${marker}");`);
  await runSource(page, `chant("${marker}");`, '#check');
  for (const request of seen) {
    expect(request.method).toBe('GET');
    expect(request.url).not.toContain(marker);
    expect(request.body ?? '').not.toContain(marker);
  }
  const logged = fs.readFileSync(requestsLog, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  expect(logged.every(entry => entry.method === 'GET' && entry.body === 0)).toBe(true);
});
