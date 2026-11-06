# Mio Web Playground

A static, self-contained browser playground for Mio 2.1. Source code is compiled and run
entirely in the browser; the page only fetches its own static files.

## What runs in the browser

`mio.wasm` is the **Web reference VM**: the Go reference front end (lexer, parser, resolver,
type checker, compiler), the Mochi codec and the Go reference VM, built from `cmd/mio-wasm`
with `GOOS=js GOARCH=wasm`. It is **not** a native AOT backend and produces no machine code.
The pure-Mio native backends (darwin-arm64, linux-amd64, windows-amd64) are separate and unchanged.

* **Run / Check / Download .mochi**: compile the editor buffer (`main.mio`) with the bundled,
  allowlisted Bunko packages (`internal/playground/library.go`). Run always goes through the real
  Mochi encoder and decoder. Download gives the same bytes as `mio build`.
* **Import .mochi**: decode, validate and run a Mochi file, exactly as `mio exec` does. Files from
  the native CLI (`mio build <file.mio> --emit=mochi -o file.mochi`) use Mochi v16 (v14 plus the
  typed opcodes 66 `TYPE_CONSTRAINT` and 67 `CALL_TYPED` defined by `bunko/kiso/encoding/mochi`);
  files from the Go reference CLI use the lowest version that represents them (at most v14).
* Output, compile diagnostics and runtime errors are rendered like the reference CLI
  (`--color=never`), with `main.mio` as the file name.

## Isolation and limits

* Every request runs in a fresh Web Worker with its own Go runtime; nothing carries over.
  Stop and the time limit terminate the Worker and a new one is started.
* Limits: 10 s per run (`?timeout=ms`), 50,000,000 VM instructions (`?instructions=n`, at most
  2,000,000,000), 256 KiB source, 4 MiB `.mochi`, 1 MiB stdout, a 1 GiB soft heap limit
  (a program that keeps more alive ends its Worker, which is reported and replaced).
* No host capability is reachable. Host MMA functions (`mio/fs/runtime`, `mio/sys/socket`) are
  bound to stubs that fail with `host capability is not available in the Web playground`, so a
  `.mochi` that merely declares them (every native-CLI file does) still runs, and a call stops
  with a runtime error. `kiso/fs`, `kiso/io`, `kiso/os`, `kiso/net`, `kiso/runtime`, `kiso/aot`
  and `kiso/testing` cannot be imported from source. The Worker also removes `fetch`,
  `XMLHttpRequest`, `WebSocket` and `importScripts` after start-up.

## Build and test

```sh
bash scripts/web/build.sh build/web             # static site: serve build/web with any file server
go build -o build/reference/mio ./cmd/mio        # reference CLI
bash scripts/web/native-cli.sh build/native-cli  # pure-Mio linux-amd64 CLI (Mochi producer)
python3 tests/web/differential.py --reference-mio build/reference/mio \
  --native-mio build/native-cli/mio --fixtures build/web-fixtures
(cd tests/web/browser && npm ci && npx playwright install chromium && npx playwright test)
```

`tests/web/differential.py` compares the Web VM (under Node) with the reference CLI for every case
in `tests/web/cases` and `tests/native-differential/cases`: source runs, checks, `mio build` bytes,
Native CLI `.mochi` execution, malformed Mochi files and the limits. CI: `.github/workflows/web.yml`.
