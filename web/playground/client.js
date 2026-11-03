// One Worker owns one Go runtime. Recycle after every request to release its memory.
export class Playground {
  constructor(onState, onResult, options = {}) {
    this.onState = onState;
    this.onResult = onResult;
    this.workerURL = options.workerURL || './worker.js';
    this.timeoutMs = options.timeoutMs || 5000;
    this.sequence = 0;
    this.generation = 0;
    this.reset();
  }
  dispose() {
    clearTimeout(this.timer);
    this.generation++;
    this.worker?.terminate();
    this.worker = null;
    this.ready = false;
    this.active = null;
  }
  reset() {
    this.dispose();
    const generation = this.generation;
    this.onState('loading');
    const worker = this.worker = new Worker(this.workerURL);
    const id = ++this.sequence;
    const fail = error => {
      if (generation !== this.generation) return;
      const requestId = this.active;
      this.dispose();
      this.onState('error');
      this.onResult({ id: requestId, status: 'error', error });
    };
    worker.onerror = event => { event.preventDefault(); fail(event.message || 'Worker failed'); };
    worker.onmessageerror = () => fail('Worker message could not be decoded');
    worker.onmessage = ({ data }) => {
      if (generation !== this.generation) return;
      if (data.operation === 'ready' && data.id === id && this.active === null) {
        clearTimeout(this.timer);
        this.ready = true;
        this.onState('ready', data);
      } else if (data.operation === 'error') {
        fail(data.error);
      } else if (data.operation === 'result' && data.id === this.active) {
        clearTimeout(this.timer);
        this.onResult(data);
        this.reset();
      }
    };
    this.timer = setTimeout(() => fail('Wasm initialization timed out (15 seconds)'), 15000);
    worker.postMessage({ operation: 'init', id });
  }
  execute(operation, source) {
    if (!this.ready || this.active !== null) return false;
    if (!['run', 'check'].includes(operation)) return false;
    if (new TextEncoder().encode(source).length > 65536) {
      this.onResult({ status: 'error', error: 'Source limit exceeded (65536 bytes)' });
      return false;
    }
    this.active = ++this.sequence;
    this.onState('running');
    this.timer = setTimeout(() => this.stop('timeout'), this.timeoutMs);
    this.worker.postMessage({ operation, id: this.active, source });
    return true;
  }
  stop(status = 'cancelled') {
    const id = this.active;
    this.dispose(); // terminate() works even while Go is synchronously running.
    if (id !== null) this.onResult({ id, status, error: status === 'timeout' ? 'Execution timed out (Worker terminated)' : '' });
    this.reset();
  }
}
