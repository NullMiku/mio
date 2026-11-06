// Runs the Web reference VM (build/web/mio.wasm) under Node with the same wasm_exec.js the
// browser uses. Reads one JSON request per line on stdin and answers one JSON result per line.
// Every request gets a fresh Go instance (as every browser request gets a fresh Worker).
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');

const dir = path.resolve(process.argv[2] || path.join(__dirname, '../../build/web'));
// Go runtime messages (wasm_exec routes fd 1/2 to console.log) must not mix with the protocol.
console.log = (...items) => process.stderr.write(items.join(' ') + '\n');
require(path.join(dir, 'wasm_exec.js'));
const modulePromise = WebAssembly.compile(fs.readFileSync(path.join(dir, 'mio.wasm')));

// Resolves with the bridge and a promise that rejects if the Go runtime exits (for example a
// fatal out-of-memory), which is what terminates the Worker in the browser.
async function instance() {
  const go = new globalThis.Go();
  const inst = await WebAssembly.instantiate(await modulePromise, go.importObject);
  const exited = go.run(inst).then(() => { throw new Error('Go runtime exited'); });
  const execute = globalThis.mioExecute;
  delete globalThis.mioExecute;
  if (typeof execute !== 'function') throw new Error('Mio bridge unavailable');
  return { execute, exited };
}

const lines = readline.createInterface({ input: process.stdin });
let queue = Promise.resolve();
lines.on('line', line => {
  queue = queue.then(async () => {
    let answer;
    try {
      const { execute, exited } = await instance();
      answer = await Promise.race([exited, new Promise((resolve, reject) => {
        const refusal = execute(line, resolve);
        if (refusal) reject(new Error(refusal));
      })]);
    } catch (error) {
      answer = JSON.stringify({ status: 'host_error', error: String(error) });
    }
    process.stdout.write(answer + '\n');
  });
});
lines.on('close', () => queue.then(() => process.exit(0)));
