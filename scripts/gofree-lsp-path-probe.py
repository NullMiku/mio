#!/usr/bin/env python3
"""Isolated live-pipe native LSP lifecycle audit, not a production dependency.

Scope is framing/lifecycle/document diagnostics and representative shared-core
semantic providers. Full semantic coverage and in-flight cancellation remain separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
cli = a.candidate.resolve()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
policy = out / 'native.sb'
policy.write_text('(version 1)(allow default)(deny network*)(deny process-fork)'
                  '(deny process-exec)(allow process-exec (literal ' + json.dumps(str(cli)) + '))\n')
base = ['/usr/bin/sandbox-exec', '-f', str(policy), str(cli), 'lsp']
results = []

class Peer:
    def __init__(self, name):
        self.path = out / name
        self.path.mkdir()
        self.stderr = (self.path / 'stderr').open('wb')
        self.proc = subprocess.Popen(base + ['--stdio'], cwd='/tmp', env={'PATH': ''}, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.stderr, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = bytearray()
        self.raw = bytearray()
        self.input = bytearray()
        self.events = []

    def send(self, message, fragmented=False):
        data = message if isinstance(message, bytes) else json.dumps(message, ensure_ascii=False).encode()
        frame = b'Content-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data
        self.input.extend(frame)
        if fragmented:
            for byte in frame:
                self.proc.stdin.write(bytes([byte]))
                self.proc.stdin.flush()
        else:
            self.proc.stdin.write(frame)
            self.proc.stdin.flush()

    def receive(self):
        deadline = time.monotonic() + 15
        while True:
            split = self.buffer.find(b'\r\n\r\n')
            if split >= 0:
                header = self.buffer[:split].decode('ascii')
                assert header.startswith('Content-Length: '), repr(header)
                length = int(header[len('Content-Length: '):])
                assert 0 <= length <= 67108864
                end = split + 4 + length
                if len(self.buffer) >= end:
                    reply = json.loads(self.buffer[split + 4:end])
                    del self.buffer[:end]
                    self.events.append(reply)
                    return reply
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'response timeout while stdin remains open'
            assert self.selector.select(remaining), 'no live-pipe response'
            data = os.read(self.proc.stdout.fileno(), 4096)
            assert data, f'EOF before response, process={self.proc.poll()}'
            self.buffer.extend(data)
            self.raw.extend(data)

    def request(self, id, method, params=None, fragmented=False):
        message = {'jsonrpc': '2.0', 'id': id, 'method': method}
        if params is not None:
            message['params'] = params
        self.send(message, fragmented)
        reply = self.receive()
        assert reply.get('id') == id, reply
        return reply

    def finish(self, expected):
        self.proc.stdin.close()
        code = self.proc.wait(timeout=15)
        remaining = self.proc.stdout.read()
        self.raw.extend(remaining)
        assert not self.buffer and not remaining, 'unexpected extra/unframed stdout'
        assert code == expected, (code, expected)

    def save(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        self.stderr.close()
        self.selector.close()
        (self.path / 'stdin.bin').write_bytes(self.input)
        (self.path / 'stdout.bin').write_bytes(self.raw)
        (self.path / 'messages.json').write_text(json.dumps(self.events, ensure_ascii=False, indent=2) + '\n')

def case(name, fn):
    peer = Peer(name)
    start = time.monotonic()
    try:
        fn(peer)
        result = {'case': name, 'status': 'PASS'}
    except Exception as exc:
        result = {'case': name, 'status': 'FAIL', 'error': repr(exc)}
    finally:
        peer.save()
    result['wall_seconds'] = time.monotonic() - start
    results.append(result)
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['status'], flush=True)

def code(reply, expected):
    assert reply.get('error', {}).get('code') == expected, reply

def normal(peer):
    code(peer.request(0, 'shutdown'), -32002)
    initialized = peer.request(9007199254740993, 'initialize', {'rootUri': 'file:///tmp/project'}, True)
    assert initialized['result']['capabilities']['positionEncoding'] == 'utf-16'
    assert initialized['result']['capabilities']['textDocumentSync']['change'] == 2
    peer.send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
    assert peer.receive()['method'] == 'window/logMessage'
    code(peer.request(2, 'initialize', {}), -32600)
    peer.send({'jsonrpc': '2.0', 'id': 123, 'result': None})
    peer.send({'jsonrpc': '2.0', 'method': 'unknown/notification'})
    code(peer.request('日本語', 'unknown/request'), -32601)
    assert peer.request(4, 'shutdown')['result'] is None
    code(peer.request(5, 'unknown/request'), -32600)
    peer.send({'jsonrpc': '2.0', 'method': 'exit'})
    peer.finish(0)

def documents(peer):
    uri = 'file:///tmp/目录%20space/main.mio'
    text = 'kaku text="😀"; chant(@);'
    peer.send({'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
        'textDocument': {'uri': uri, 'languageId': 'mio', 'version': 1, 'text': text}}})
    peer.request(1, 'initialize', {})
    initial = peer.receive()
    assert initial['method'] == 'textDocument/publishDiagnostics', initial
    params = initial['params']
    assert params['uri'] == uri and params['version'] == 1, initial
    assert params['diagnostics'][0]['code'] == 'E0001', initial
    character = len(text[:text.index('@')].encode('utf-16-le')) // 2
    assert params['diagnostics'][0]['range'] == {
        'start': {'line': 0, 'character': character},
        'end': {'line': 0, 'character': character + 1}}, initial
    peer.send({'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': uri, 'version': 2}, 'contentChanges': [{'text': 'kaku value: int64=1;'}]}})
    changed = peer.receive()
    assert changed['method'] == 'textDocument/publishDiagnostics', changed
    assert changed['params'] == {'uri': uri, 'version': 2, 'diagnostics': []}, changed
    peer.send({'jsonrpc': '2.0', 'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': uri, 'version': 3}, 'contentChanges': [{'text': 'kaku value: int64="wrong";'}]}})
    invalid = peer.receive()
    assert invalid['method'] == 'textDocument/publishDiagnostics', invalid
    assert invalid['params']['uri'] == uri and invalid['params']['version'] == 3, invalid
    assert invalid['params']['diagnostics'][0]['code'] == 'E0301', invalid
    peer.send({'jsonrpc': '2.0', 'method': 'textDocument/didSave', 'params': {'textDocument': {'uri': uri}}})
    peer.send({'jsonrpc': '2.0', 'id': 2, 'method': 'shutdown'})
    last = None
    while True:
        reply = peer.receive()
        if reply.get('id') == 2:
            assert reply == {'jsonrpc': '2.0', 'id': 2, 'result': None}, reply
            break
        assert reply['method'] == 'textDocument/publishDiagnostics', reply
        assert reply['params']['uri'] == uri, reply
        last = reply
    assert last['params'] == {'uri': uri, 'diagnostics': []}, last
    peer.finish(0)

def malformed(peer):
    peer.send(b'{', True)
    code(peer.receive(), -32700)
    peer.send(b'[]')
    code(peer.receive(), -32600)
    code(peer.request(1, 'initialize', []), -32602)
    peer.request(2, 'initialize', {})
    peer.request(3, 'shutdown')
    peer.send({'jsonrpc': '2.0', 'method': 'exit'})
    peer.finish(0)

def cancellation(peer):
    peer.request(1, 'initialize', {})
    peer.send({'jsonrpc': '2.0', 'method': '$/cancelRequest', 'params': {'id': 'unknown'}})
    code(peer.request('unknown', 'unknown/request'), -32601)
    peer.send({'jsonrpc': '2.0', 'method': '$/cancelRequest', 'params': {'id': 'stop'}})
    code(peer.request('stop', 'shutdown'), -32800)
    peer.send({'jsonrpc': '2.0', 'method': 'exit'})
    peer.finish(0)

def semantic_providers(peer):
    initialized = peer.request(1, 'initialize', {'initializationOptions': {'diagnosticsEnabled': False}})
    capabilities = initialized['result']['capabilities']
    for name in ['hoverProvider', 'definitionProvider', 'referencesProvider', 'documentSymbolProvider']:
        assert capabilities[name] is True, capabilities
    assert capabilities['completionProvider']['triggerCharacters'] == ['.']
    assert capabilities['signatureHelpProvider']['triggerCharacters'] == ['(', ',']
    uri = 'untitled:live-semantic-😀'
    text = ('kata Item {value: int64;}\n'
            'waza add(a: int64, b: int64) -> int64 {kaesu a+b;}\n'
            'kaku item=Item {value:7};\n'
            'chant(add(item.value,2)); // add is not a reference\n')
    peer.send({'method': 'textDocument/didOpen', 'params': {'textDocument': {
        'uri': uri, 'languageId': 'mio', 'version': 1, 'text': text}}})
    def position(offset):
        before = text[:offset]
        return {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}
    def query(id, method, offset, **extra):
        params = {'textDocument': {'uri': uri}, 'position': position(offset), **extra}
        return peer.request(id, 'textDocument/' + method, params)['result']
    call = text.index('chant(add') + 6
    hover = query(2, 'hover', call)
    assert 'add(a: int64, b: int64) -> int64' in hover['contents']['value'], hover
    definitions = query(3, 'definition', call)
    assert len(definitions) == 1 and definitions[0]['uri'] == uri, definitions
    assert definitions[0]['range']['start'] == position(text.index('add(')), definitions
    references = query(4, 'references', call, context={'includeDeclaration': True})
    assert len(references) == 2 and all(x['uri'] == uri for x in references), references
    symbols = query(5, 'documentSymbol', 0)
    assert {'Item', 'add', 'item'} <= {x['name'] for x in symbols}, symbols
    completion = query(6, 'completion', text.index('item.value') + 5)
    assert any(x['label'] == 'value' and x['detail'] == 'int64' for x in completion['items']), completion
    signature = query(7, 'signatureHelp', text.index('item.value,') + len('item.value,'))
    assert signature['activeParameter'] == 1, signature
    assert signature['signatures'][0]['label'] == 'add(a: int64, b: int64) -> int64', signature
    peer.send({'id': 8, 'method': 'shutdown'})
    cleared = peer.receive()
    assert cleared['params'] == {'uri': uri, 'diagnostics': []}, cleared
    assert peer.receive() == {'jsonrpc': '2.0', 'id': 8, 'result': None}
    peer.send({'method': 'exit'})
    peer.finish(0)


# These gates run the actual installed native CLI without repository reads or
# compiler/server subprocesses. Python is only the isolated audit controller.
from urllib.parse import urlparse, unquote
project_root = Path(__file__).resolve().parents[1]
policy.write_text(policy.read_text() +
    '(deny file-read* (subpath ' + json.dumps(str(project_root)) + '))\n' +
    '(deny file-read* (subpath "/Volumes/Sector0/AppData/Mio/mio"))\n' +
    '(allow file-read* (literal ' + json.dumps(str(cli)) + '))\n')

def opened(peer, uri, text, version=1):
    peer.send({'method': 'textDocument/didOpen', 'params': {'textDocument': {
        'uri': uri, 'languageId': 'mio', 'version': version, 'text': text}}})

def changed(peer, uri, text, version):
    peer.send({'method': 'textDocument/didChange', 'params': {
        'textDocument': {'uri': uri, 'version': version}, 'contentChanges': [{'text': text}]}})

def shut(peer, uris):
    peer.send({'id': 'shutdown', 'method': 'shutdown'})
    cleared = []
    while True:
        reply = peer.receive()
        if reply.get('id') == 'shutdown':
            assert reply == {'jsonrpc': '2.0', 'id': 'shutdown', 'result': None}, reply
            break
        assert reply['method'] == 'textDocument/publishDiagnostics', reply
        assert reply['params']['diagnostics'] == [], reply
        cleared.append(reply['params']['uri'])
    assert sorted(cleared) == sorted(uris), cleared
    peer.send({'method': 'exit'})
    peer.finish(0)

def quiet(peer, seconds):
    assert not peer.buffer, 'unexpected buffered output'
    assert not peer.selector.select(seconds), 'unexpected premature response/diagnostics'

def large_source():
    return ''.join(f'kaku value{i}: int64={i};\n' for i in range(50000))

def in_flight(peer):
    peer.request(1, 'initialize', {'initializationOptions': {'diagnosticsEnabled': False}})
    uri = 'untitled:in-flight-native'
    source = large_source()
    opened(peer, uri, source)
    code(peer.request('barrier', 'audit/unknown'), -32601)
    id = 9007199254740993
    start = time.monotonic()
    peer.send({'id': id, 'method': 'textDocument/hover', 'params': {
        'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': 6}}})
    quiet(peer, .05)
    data = json.dumps({'method': '$/cancelRequest', 'params': {'id': id}}).encode()
    frame = b'Content-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data
    peer.input.extend(frame)
    middle = len(frame) // 2
    peer.proc.stdin.write(frame[:middle]); peer.proc.stdin.flush()
    quiet(peer, .02)
    cancelled = time.monotonic()
    peer.proc.stdin.write(frame[middle:]); peer.proc.stdin.flush()
    reply = peer.receive()
    assert reply.get('id') == id, reply
    code(reply, -32800)
    latency = time.monotonic() - cancelled
    assert latency < 3, latency
    tiny = 'waza value() -> int64 {kaesu 7;} chant(value());'
    changed(peer, uri, tiny, 2)
    result = peer.request(id, 'textDocument/hover', {'textDocument': {'uri': uri},
                          'position': {'line': 0, 'character': tiny.index('chant(value') + 6}})
    assert 'value() -> int64' in result['result']['contents']['value'], result
    (peer.path / 'timing.json').write_text(json.dumps({'total_seconds': time.monotonic()-start,
          'cancel_to_response_seconds': latency, 'source_bytes': len(source)}, indent=2)+'\n')
    shut(peer, [uri])

def debounce(peer):
    peer.request(1, 'initialize', {'initializationOptions': {'diagnosticsDelayMs': 200}})
    uri = 'untitled:debounce-native'
    opened(peer, uri, 'kaku value: int64="wrong";')
    changed(peer, uri, 'kaku value: int64=1;', 2)
    changed(peer, uri, 'kaku value: int64="wrong";', 3)
    changed(peer, uri, 'kaku value: int64=4;', 4)
    start = time.monotonic()
    code(peer.request('barrier', 'audit/unknown'), -32601)
    quiet(peer, .08)
    reply = peer.receive()
    assert reply['method'] == 'textDocument/publishDiagnostics', reply
    assert reply['params'] == {'uri': uri, 'version': 4, 'diagnostics': []}, reply
    elapsed = time.monotonic() - start
    assert elapsed >= .15, elapsed
    quiet(peer, .03)
    (peer.path / 'timing.json').write_text(json.dumps({'debounce_seconds': elapsed}, indent=2)+'\n')
    shut(peer, [uri])

def stale_diagnostics(peer):
    peer.request(1, 'initialize', {'initializationOptions': {'diagnosticsDelayMs': 0}})
    uri = 'untitled:stale-native'
    opened(peer, uri, large_source() + 'chant(undefined_name);\n')
    code(peer.request('barrier', 'audit/unknown'), -32601)
    quiet(peer, .05)
    start = time.monotonic()
    changed(peer, uri, 'kaku value: int64=2;', 2)
    reply = peer.receive()
    assert reply['method'] == 'textDocument/publishDiagnostics', reply
    assert reply['params'] == {'uri': uri, 'version': 2, 'diagnostics': []}, reply
    assert time.monotonic()-start < 3
    quiet(peer, .03)
    shut(peer, [uri])

def embedded_navigation(peer):
    peer.request(1, 'initialize', {'initializationOptions': {'diagnosticsEnabled': False}})
    uri = 'untitled:embedded-native'
    source = 'yobu "kiso/path"; kaku joined=path.join("a","b");chant(joined);'
    opened(peer, uri, source)
    params = {'textDocument': {'uri': uri}, 'position': {'line': 0, 'character': source.index('path.join') + 5}}
    reply = peer.request(2, 'textDocument/definition', params)
    locations = reply['result']
    assert len(locations) == 1, reply
    target_uri = locations[0]['uri']
    parsed = urlparse(target_uri)
    assert parsed.scheme == 'file' and parsed.path.startswith('/tmp/mio-lsp-sources-'), target_uri
    path = Path(unquote(parsed.path))
    expected = (project_root/'bunko/kiso/path/path.mio').read_bytes()
    assert path.read_bytes() == expected, path
    assert path.stat().st_mode & 0o222 == 0, path.stat().st_mode
    assert peer.request(3, 'textDocument/definition', params)['result'] == locations, 'stable identity across repeated lookup'
    # Treat edits to the owned cache exactly like user changes: preserve them,
    # but issue another readable immutable source for the real embedded bytes.
    original_path=path; modified=expected+b'\n// retained external edit\n'
    path.chmod(0o644);path.write_bytes(modified)
    refreshed=peer.request(31, 'textDocument/definition', params)['result']
    assert len(refreshed)==1 and refreshed[0]['uri']!=target_uri,refreshed
    target_uri=refreshed[0]['uri'];path=Path(unquote(urlparse(target_uri).path));locations=refreshed
    assert path.read_bytes()==expected and original_path.read_bytes()==modified,'preserve modified cache and materialize correct source'
    assert path.stat().st_mode & 0o222==0
    text = expected.decode()
    opened(peer, target_uri, text)
    pos = text.index('join(')
    prefix = text[:pos]
    hover = peer.request(4, 'textDocument/hover', {'textDocument': {'uri': target_uri},
        'position': {'line': prefix.count('\n'), 'character': len(prefix.rsplit('\n',1)[-1].encode('utf-16-le'))//2}})
    assert 'join(' in hover['result']['contents']['value'], hover
    again = peer.request(5, 'textDocument/definition', params)['result']
    assert again == locations, (locations, again)
    shut(peer, [uri, target_uri])
    assert path.read_bytes() == expected, 'navigation source remains readable after server exit'
    (peer.path/'library.json').write_text(json.dumps({'uri':target_uri,'bytes':len(expected),
        'sha256':hashlib.sha256(expected).hexdigest()},indent=2)+'\n')


import tempfile

def alias_overlay(peer):
    base=Path(tempfile.mkdtemp(prefix='mio-lsp-path-',dir='/tmp'))
    real=base/'工程 空格';(real/'dep').mkdir(parents=True);alias=base/'alias';alias.symlink_to(real,target_is_directory=True)
    lib=real/'dep/library.mio';lib.write_text('koukai waza old() -> int64 {kaesu 1;}')
    main=real/'main.mio';source='yobu "./dep";chant(dep.fresh());';main.write_text(source)
    peer.request(1,'initialize',{'rootUri':real.as_uri(),'initializationOptions':{'diagnosticsEnabled':False}})
    alias_uri=(alias/'dep/library.mio').as_uri();opened(peer,alias_uri,'koukai waza fresh() -> int64 {kaesu 2;}')
    opened(peer,main.as_uri(),source)
    reply=peer.request(2,'textDocument/definition',{'textDocument':{'uri':main.as_uri()},'position':{'line':0,'character':source.index('dep.fresh')+4}})
    assert len(reply['result'])==1 and reply['result'][0]['uri']==alias_uri,reply
    assert lib.read_text()=='koukai waza old() -> int64 {kaesu 1;}','overlay leaves disk source untouched'
    shut(peer,[alias_uri,main.as_uri()])
    (peer.path/'fixture.json').write_text(json.dumps({'root':str(base),'alias_uri':alias_uri,'main_uri':main.as_uri()},indent=2)+'\n')

case('symlink-library-overlay-preserves-client-uri',alias_overlay)
(out/'provenance.json').write_text(json.dumps({'candidate':str(cli),'candidate_sha256':hashlib.sha256(cli.read_bytes()).hexdigest(),'scope':'Physical path alias overlay identity and original URI retention; native service only'},indent=2)+'\n')
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
