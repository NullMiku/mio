#!/usr/bin/env python3
"""Actual CLI stdio session: IDs, Unicode paths, overlays and cancellation."""
from pathlib import Path
import hashlib,json,os,selectors,signal,subprocess,sys,time,urllib.parse
compiler=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();bunko=Path(sys.argv[3]).resolve()
out.mkdir();workspace=out/'space 日本語';workspace.mkdir();source=workspace/'main.mio'
source.write_text('kaku answer="disk";chant(answer);\n')
uri=source.as_uri();wire_in=bytearray();wire_out=bytearray();messages=[];buffer=bytearray()
start=time.monotonic();sel=selectors.DefaultSelector()
stderr=(out/'native.stderr').open('xb')
child=subprocess.Popen([str(compiler),'lsp','--stdio'],cwd=workspace,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,env=dict(os.environ,MIO_BUNKO=str(bunko)),start_new_session=True)
sel.register(child.stdout,selectors.EVENT_READ)
def frame(payload):
 body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
 return b'Content-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body
def send(*payloads):
 raw=b''.join(frame(p) for p in payloads);wire_in.extend(raw);child.stdin.write(raw);child.stdin.flush()
def receive(identifier):
 deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  while b'\r\n\r\n' in buffer:
   split=buffer.index(b'\r\n\r\n');header=bytes(buffer[:split])
   length=int(next(line.split(b':',1)[1] for line in header.split(b'\r\n') if line.lower().startswith(b'content-length:')))
   assert 0<=length<=16*1024*1024
   if len(buffer)<split+4+length:break
   body=bytes(buffer[split+4:split+4+length]);del buffer[:split+4+length]
   reply=json.loads(body);messages.append(reply)
   if reply.get('id')==identifier:return reply
  assert child.poll() is None,'LSP exited before reply'
  if sel.select(min(.5,max(0,deadline-time.monotonic()))):
   data=os.read(child.stdout.fileno(),65536);assert data,'LSP EOF before reply';wire_out.extend(data);buffer.extend(data)
 raise TimeoutError('LSP response deadline: '+str(identifier))
def request(identifier,method,params=None):
 message=dict(jsonrpc='2.0',id=identifier,method=method)
 if params is not None:message['params']=params
 send(message);return receive(identifier)
def query(text):return dict(textDocument=dict(uri=uri),position=dict(line=0,character=text.rindex('answer')+1))
try:
 init=request(9007199254740993,'initialize',dict(processId=None,rootUri=workspace.as_uri(),capabilities={}))
 assert init['id']==9007199254740993 and 'capabilities' in init['result']
 send(dict(jsonrpc='2.0',method='initialized',params={}))
 overlay='kaku answer=41;chant(answer);\n'
 send(dict(jsonrpc='2.0',method='textDocument/didOpen',params=dict(textDocument=dict(uri=uri,languageId='mio',version=1,text=overlay))))
 hover=request(1,'textDocument/hover',query(overlay));assert 'int64' in json.dumps(hover['result']),hover
 definition=request(2,'textDocument/definition',query(overlay));assert definition['result'],definition
 assert any(urllib.parse.unquote(x['uri'])==urllib.parse.unquote(uri) for x in definition['result']),definition
 # Both frames are sent together, so transport's real cooperative pump sees
 # cancellation before it commits the semantic response. No timing/sleep bet.
 send(dict(jsonrpc='2.0',id='cancel-me',method='textDocument/hover',params=query(overlay)),dict(jsonrpc='2.0',method='$/cancelRequest',params=dict(id='cancel-me')))
 cancelled=receive('cancel-me');assert cancelled['error']['code']==-32800,cancelled
 again=request('cancel-me','textDocument/hover',query(overlay));assert 'int64' in json.dumps(again['result']),again
 changed='kaku answer=hai;chant(answer);\n'
 send(dict(jsonrpc='2.0',method='textDocument/didChange',params=dict(textDocument=dict(uri=uri,version=2),contentChanges=[dict(text=changed)])))
 hover=request(3,'textDocument/hover',query(changed));assert 'bool' in json.dumps(hover['result']),hover
 assert source.read_text()=='kaku answer="disk";chant(answer);\n','overlay modified disk'
 closed=dict(jsonrpc='2.0',method='textDocument/didClose',params=dict(textDocument=dict(uri=uri)))
 send(closed);stopped=request('終了','shutdown');assert stopped['result'] is None
 send(dict(jsonrpc='2.0',method='exit'));child.stdin.close()
 deadline=time.monotonic()+10
 while True:
  got,status,usage=os.wait4(child.pid,os.WNOHANG)
  if got:break
  if time.monotonic()>deadline:raise TimeoutError('LSP shutdown')
  time.sleep(.01)
 child.returncode=os.waitstatus_to_exitcode(status);assert child.returncode==0
 (out/'summary.json').write_text(json.dumps(dict(status='PASS_REAL_CLI_LSP_STDIO',compiler_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),exit=child.returncode,wall_seconds=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_bytes_darwin=usage.ru_maxrss,checks=['exact_integer_id','unicode_space_path','open_overlay_int64','definition_uri','transport_cancellation','cancelled_id_reuse','changed_overlay_bool','disk_unchanged','shutdown_exit']),indent=2)+'\n')
finally:
 if child.returncode is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  try:os.wait4(child.pid,0)
  except ChildProcessError:pass
 stderr.close();sel.close()
 (out/'input.bin').write_bytes(wire_in);(out/'output.bin').write_bytes(wire_out)
 (out/'messages.json').write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n')
