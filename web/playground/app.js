import { Playground, LIMITS } from './client.js';

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const timeoutMs = Number(params.get('timeout')) || LIMITS.timeoutMs;
const instructionLimit = Number(params.get('instructions')) || 0;

const examples = await (await fetch('./examples.json')).json();
for (const [index, example] of examples.entries()) $('examples').add(new Option(example.name, index));
$('examples').onchange = () => { $('source').value = examples[$('examples').value].source; };
$('source').value = examples[0].source;
$('limits').textContent = `${timeoutMs / 1000} s per run · ${instructionLimit || '50,000,000'} VM instructions · ` +
  `${LIMITS.sourceBytes / 1024} KiB source · 1 MiB stdout · ${LIMITS.mochiBytes / 1024 / 1024} MiB .mochi`;

let imported = null;    // { name, bytes }
let pendingDownload = false;
let state = 'loading';

const STATUS_TEXT = {
  ok: 'Finished', checked: 'Check passed', compiled: 'Compiled', diagnostic: 'Compile error',
  runtime_error: 'Runtime error', rejected: 'Rejected', internal_error: 'Internal error',
  timeout: 'Timed out', cancelled: 'Stopped',
};

function setBusy() {
  const ready = state === 'ready';
  for (const id of ['run', 'check', 'download', 'import', 'run-bytecode']) $(id).disabled = !ready;
  $('import-label').setAttribute('aria-disabled', String(!ready));
  $('stop').disabled = state !== 'running';
}

const playground = new Playground((next, data) => {
  state = next;
  $('engine').textContent = {
    loading: 'Starting Worker…', ready: 'Ready · runs locally', running: 'Running…',
    error: `Worker failed${data?.error ? ': ' + data.error : ''} · reload to retry`,
  }[next];
  $('engine').dataset.state = next;
  if (next === 'running') $('status').textContent = data.operation === 'exec' ? 'Running .mochi…' : 'Running…';
  setBusy();
}, result => {
  document.body.dataset.lastStatus = result.status;
  $('stdout').textContent = result.stdout || '';
  const lines = (result.diagnostics || []).map(d => d.rendered);
  if (result.error && lines.length === 0) lines.push(result.error);
  $('diagnostics').textContent = lines.join('');
  const parts = [`${STATUS_TEXT[result.status] || result.status}`, `exit ${result.exitCode ?? 1}`];
  if (result.mochiVersion) parts.push(`Mochi v${result.mochiVersion}`);
  if (result.compileMs !== undefined) parts.push(`compile ${result.compileMs.toFixed(1)} ms`);
  if (result.runMs) parts.push(`VM ${result.runMs.toFixed(1)} ms`);
  $('status').textContent = parts.join(' · ');
  $('status').dataset.status = result.status;
  if (pendingDownload && result.status === 'compiled' && result.mochi) {
    const url = URL.createObjectURL(new Blob([result.mochi], { type: 'application/octet-stream' }));
    const link = Object.assign(document.createElement('a'), { href: url, download: 'main.mochi' });
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  pendingDownload = false;
}, { timeoutMs, instructionLimit });

function clearOutput() {
  $('stdout').textContent = $('diagnostics').textContent = '';
  delete document.body.dataset.lastStatus;
}

function start(operation, payload) {
  clearOutput();
  pendingDownload = operation === 'compile';
  if (!playground.execute(operation, payload)) pendingDownload = false;
}

$('run').onclick = () => start('run', $('source').value);
$('check').onclick = () => start('check', $('source').value);
$('download').onclick = () => start('compile', $('source').value);
$('stop').onclick = () => playground.stop();
$('run-bytecode').onclick = () => imported && start('exec', imported.bytes);
$('clear-bytecode').onclick = () => { imported = null; $('bytecode').hidden = true; };
$('import').onchange = async event => {
  const file = event.target.files[0];
  event.target.value = '';
  if (!file) return;
  if (file.size > LIMITS.mochiBytes) {
    clearOutput();
    $('status').textContent = 'Rejected · exit 1';
    $('diagnostics').textContent = `Mochi file limit exceeded (${LIMITS.mochiBytes} bytes)`;
    return;
  }
  imported = { name: file.name, bytes: new Uint8Array(await file.arrayBuffer()) };
  const b = imported.bytes;
  const header = b.length >= 7 && String.fromCharCode(...b.subarray(0, 5)) === 'MOCHI' ? `header v${(b[5] << 8) | b[6]}` : 'no Mochi header';
  $('bytecode-info').textContent = `${file.name} · ${b.length} bytes · ${header}`;
  $('bytecode').hidden = false;
  start('exec', imported.bytes);
};
$('source').addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); if (!$('run').disabled) $('run').click(); }
  if (event.key === 'Tab' && !event.shiftKey) {
    event.preventDefault();
    const { selectionStart: a, selectionEnd: z, value } = event.target;
    event.target.value = value.slice(0, a) + '    ' + value.slice(z);
    event.target.selectionStart = event.target.selectionEnd = a + 4;
  }
});
window.addEventListener('pagehide', () => playground.dispose());
window.mioPlayground = playground; // for automated browser tests
