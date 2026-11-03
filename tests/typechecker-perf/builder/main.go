// Compile the selected source with an existing native Mio seed, then execute
// the existing pure Mio lowering backend in the Go VM. Runs are native.
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	mio "Mio"
)

func main() {
	if len(os.Args) != 4 {
		panic("builder SOURCE_ROOT HARNESS OUTPUT")
	}
	root, err := filepath.Abs(os.Args[1])
	must(err)
	out, err := filepath.Abs(os.Args[3])
	must(err)
	for _, path := range []string{out, out + ".mochi", out + ".builder.mio"} {
		if _, err := os.Stat(path); err == nil {
			panic("refusing to overwrite " + path)
		} else if !os.IsNotExist(err) {
			must(err)
		}
	}
	env, err := mio.NewStandardEnvironment()
	must(err)
	defer env.Close()
	seed := os.Getenv("MIO_PERF_SEED")
	if seed == "" {
		panic("MIO_PERF_SEED is required")
	}
	harness, err := filepath.Abs(os.Args[2])
	must(err)
	cmd := exec.Command(seed, "build", harness, "--emit=mochi", "--bunko-root", filepath.Join(root, "bunko"), "-o", out+".mochi")
	cmd.Dir = root
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	must(cmd.Run())
	source := fmt.Sprintf(`yobu "kiso/fs";
yobu "kiso/encoding/mochi";
yobu "kiso/aot/lower";
yobu "kiso/aot/macho";
waza run() -> unit {
 kaku decoded=mochi.decode_file(%q);kaku file=decoded.value;
 moshi(file != mu){
  kaku result=lower.compile_with_observation(file,268435456,iie);
  kaku problem=result.error;
  moshi(problem != mu){chant(lower.error_code(problem));chant(lower.error_detail(problem));}
  sore {kaku image=macho.executable(macho.ImageSpec {words:result.words,constants:result.constants,globals:result.globals,patches:result.patches});
   moshi(image.error != mu){chant(-2);} sore {kaku written=fs.write_all(%q,image.bytes);moshi(written.error != mu){chant(-3);}}
  }
 } sore {chant(-1);}
}
run();`, out+".mochi", out)
	must(os.WriteFile(out+".builder.mio", []byte(source), 0600))
	builder, err := env.CompileFile(out+".builder.mio", filepath.Join(root, "bunko"))
	must(err)
	must(env.RunWithOptions(builder, os.Stdout, mio.ExecutionOptions{InstructionLimit: 100_000_000_000}))
	must(os.Chmod(out, 0755))
	run("codesign", "-s", "-", out)
	fmt.Println("native image ready", out)
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}
func run(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	must(cmd.Run())
}
