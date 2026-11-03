/* Classic Worker: Go's matching wasm_exec.js provides the official js/wasm ABI. */
let initialized = false;
self.onmessage = async ({ data }) => {
  const { id, operation, source } = data;
  try {
    if (operation === 'init') {
      const start = performance.now();
      importScripts('./wasm_exec.js');
      const go = new Go();
      // No fs, network, JS callbacks or other capabilities are registered with Mio.
      const response = await fetch('./mio.wasm');
      if (!response.ok) throw new Error(`Wasm fetch: HTTP ${response.status}`);
      const { instance } = await WebAssembly.instantiate(await response.arrayBuffer(), go.importObject);
      go.run(instance).then(() => { throw new Error('Go runtime exited'); }).catch(error => {
        self.postMessage({ operation: 'error', id, error: String(error) });
      });
      if (typeof self.mioExecute !== 'function') throw new Error('Mio bridge unavailable');
      initialized = true;
      self.postMessage({ operation: 'ready', id, initMs: performance.now() - start });
    } else if (operation === 'run' || operation === 'check') {
      if (!initialized) throw new Error('Worker is not initialized');
      const start = performance.now();
      const result = JSON.parse(self.mioExecute(source, operation));
      self.postMessage({ operation: 'result', id, ...result, elapsedMs: performance.now() - start });
    } else throw new Error('Unsupported Worker operation');
  } catch (error) {
    self.postMessage({ operation: 'error', id, error: String(error) });
  }
};
