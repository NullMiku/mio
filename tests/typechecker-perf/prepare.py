#!/usr/bin/env python3
"""Make frozen, opt-in instrumentation copies; production API/state is unchanged."""
import argparse, json, pathlib, re, shutil
p=argparse.ArgumentParser();p.add_argument('evidence',type=pathlib.Path);a=p.parse_args();e=a.evidence.resolve();root=pathlib.Path(__file__).resolve().parents[2]
for name in ['after','baseline-profile','after-profile','input.mio']:
 if (e/name).exists():raise SystemExit('refusing to overwrite existing evidence: '+str(e/name))
for label,source in [('after',root)]:
 target=e/label
 for folder in ('selfhost','bunko'):
  shutil.copytree(source/folder,target/folder,dirs_exist_ok=True)
functions=[('environment.mio','binding_of','len(env.resolved.bindings)'),('environment.mio','set_node_type','len(env.result.node_types)'),('type.mio','intern_type','len(result.types)'),('environment.mio','symbol_type',None),('environment.mio','signature_of','len(env.result.signatures)')]
for label in ('baseline','after'):
 target=e/(label+'-profile');target.mkdir(exist_ok=True)
 for folder in ('selfhost','bunko'):shutil.copytree(e/label/folder,target/folder,dirs_exist_ok=True)
 package=target/'selfhost/typecheck'
 # Profiling-only state is carried by the invocation result; no package globals.
 f=package/'type.mio';s=f.read_text().replace('koukai kata TypeCheckResult {','koukai kata TypeCheckResult {\n    lookup_profile: []int64;');f.write_text(s)
 f=package/'environment.mio';s=f.read_text().replace('        package_path: path,','        lookup_profile: ['+','.join(['0']*15)+'],\n        package_path: path,');f.write_text(s)

 for slot,(file,name,scan) in enumerate(functions):
  f=package/file;s=f.read_text();start=s.index('waza '+name+'(');brace=s.index('{',start);level=1;end=brace+1
  while level:
   if s[end]=='{':level+=1
   elif s[end]=='}':level-=1
   end+=1
  body=s[brace+1:end-1]
  # Count actual inspected entries (including facts in symbol_type), rather
  # than estimating scans from table sizes.
  body=re.sub(r'(aida \(index < len\([^\n]+\)\) \{)',r'\1 lookup_profile['+str(slot*3+1)+'] = lookup_profile['+str(slot*3+1)+'] + 1;',body)
  body=re.sub(r'kaesu([^;]*);',lambda m:'lookup_profile['+str(slot*3+2)+'] = lookup_profile['+str(slot*3+2)+'] + runtime.monotonic_ms() - lookup_started; kaesu'+m[1]+';',body)
  body='\n    lookup_profile['+str(slot*3)+'] = lookup_profile['+str(slot*3)+'] + 1;\n    kaku lookup_started = runtime.monotonic_ms();\n'+body
  if 'yobu "mio/os/runtime";' not in s:s='yobu "mio/os/runtime";\n'+s;start=s.index('waza '+name+'(');brace=s.index('{',start);level=1;end=brace+1
  # Recompute end after insertion of import.
  level=1;end=brace+1
  while level:
   if s[end]=='{':level+=1
   elif s[end]=='}':level-=1
   end+=1
  body=body.replace('lookup_profile[', ('result.' if name=='intern_type' else 'env.result.')+'lookup_profile[')
  f.write_text(s[:brace+1]+body+s[end-1:])
# deterministic mixed workload, large enough to expose quadratic writes/reads
lines=['waza id<T: Number>(x: T) -> T {kaesu x;}','waza nullable(x: int64?) -> int64 {moshi(x != mu){kaesu x;}kaesu 0;}','kaku items: []int64 = [1,2,3];','kaku entries: Map<string, int64> = Map[string, int64]();']
for i in range(800):lines.append(f'waza fn{i}(x: int64) -> int64 {{kaku y: int64 = x + {i}; kaesu y;}} kaku value{i}: int64 = fn{i}(id({i}));')
(e/'input.mio').write_text('\n'.join(lines)+'\n')
base='''yobu "kiso/fs";
yobu "mio/os/runtime";
yobu "selfhost/parser";
yobu "selfhost/resolver";
yobu "selfhost/typecheck";
waza run() -> unit {
 kaku loaded=fs.read_all(INPUT);
 kaku parsed=parser.parse(loaded.data);
 kaku resolved=resolver.resolve_program("perf",parsed);
 chant(len(parsed.errors));chant(len(resolved.errors));
 kaku started=runtime.monotonic_ms();
 kaku result=typecheck.check_program(resolved);
 chant(runtime.monotonic_ms()-started);
 chant(len(result.types));chant(len(result.node_types));chant(len(result.symbol_types));chant(len(result.signatures));chant(len(result.substitutions));
 kaku i=0;
 aida(i<len(result.node_types)){kaku item=result.node_types[i];chant(item.node.file_id);chant(item.node.node_id);chant(item.type_id);i=i+1;}
 i=0;aida(i<len(result.types)){chant(result.types[i].identity);i=i+1;}
 i=0;aida(i<len(result.symbol_types)){kaku item=result.symbol_types[i];chant(item.symbol_id);chant(item.type_id);i=i+1;}
 i=0;aida(i<len(result.signatures)){kaku item=result.signatures[i];chant(item.symbol_id);chant(item.name);chant(item.result);kaku j=0;aida(j<len(item.parameters)){chant(item.parameters[j]);j=j+1;}i=i+1;}
 i=0;aida(i<len(result.substitutions)){kaku item=result.substitutions[i];chant(item.node.file_id);chant(item.node.node_id);kaku j=0;aida(j<len(item.types)){chant(item.types[j]);j=j+1;}i=i+1;}
 chant(len(result.errors));i=0;aida(i<len(result.errors)){kaku item=result.errors[i];chant(item.code);chant(item.node.file_id);chant(item.node.node_id);chant(item.span.start.offset);chant(item.span.end.offset);chant(item.expected);chant(item.actual);chant(item.detail);i=i+1;}
 PROFILE
}
run();
'''.replace('INPUT',json.dumps(str(e/'input.mio')))
for label in ('baseline','after','baseline-profile','after-profile'):
 prof='kaku counts=result.lookup_profile;i=0;aida(i<len(counts)){chant(counts[i]);i=i+1;}' if label.endswith('-profile') else ''
 (e/label/'harness.mio').write_text(base.replace('PROFILE',prof))
(e/'profile-schema.json').write_text(json.dumps({name:{'calls':slot*3,'scanned_entries':slot*3+1,'inclusive_ms':slot*3+2} for slot,(_,name,_) in enumerate(functions)},indent=2))
print(e)
