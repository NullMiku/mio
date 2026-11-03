import { Playground } from './client.js';
const $ = id => document.getElementById(id);
const examples = await (await fetch('./examples.json')).json();
for (const [index, example] of examples.entries()) $('examples').add(new Option(example.name, index));
function choose() { $('source').value = examples[$('examples').value].source; }
$('examples').onchange = choose;
choose();
let lastInit = 0;
const playground = new Playground((state, data) => {
  $('loading').textContent = { loading: 'Loading Wasm…', ready: 'Wasm ready · local execution', running: 'Wasm running', error: 'Worker failed · reload to retry' }[state];
  $('run').disabled = $('check').disabled = state !== 'ready';
  if (state === 'ready') { lastInit = data.initMs; }
  if (state === 'running') $('status').textContent = 'Running…';
}, result => {
  $('stdout').textContent = result.stdout || '';
  $('diagnostics').textContent = [...(result.diagnostics || []), ...(result.error ? [result.error] : [])].join('\n');
  $('status').textContent = result.status;
  $('timing').textContent = `Init ${lastInit.toFixed(1)} ms` + (result.compileMs !== undefined ? ` · Compile ${result.compileMs.toFixed(1)} ms · VM ${result.runMs.toFixed(1)} ms · Total ${result.elapsedMs.toFixed(1)} ms` : '');
});
for (const op of ['run', 'check']) $(op).onclick = () => {
  $('stdout').textContent = $('diagnostics').textContent = '';
  playground.execute(op, $('source').value);
};
$('stop').onclick = () => playground.stop();
window.addEventListener('pagehide', () => playground.dispose());
