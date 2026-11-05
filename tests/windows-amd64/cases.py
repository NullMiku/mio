"""Source-level cases for the Mio -> Windows AMD64 scalar pipeline. Expected values come from the language semantics,
not from running lowerwin; stderr/stdout are compared exactly (bytes)."""

EXIT = 'waza windows_test_exit(code: int64) -> unit { chant(code); }\n'

# name, source, exit_code, stdout, stderr
RUN = [
    ("exit42", EXIT + "windows_test_exit(42);\n", 42, b"", b""),
    ("exit0_implicit", "chant(1);\n", 0, b"1\n", b""),
    ("arith", "chant(1 + 2 * 3); chant(10 - 25); chant(7 / 2); chant(-9 / 2); chant(0 - 5);\n", 0, b"7\n-15\n3\n-4\n-5\n", b""),
    ("bool", "chant(hai); chant(iie); chant(1 < 2); chant(2 <= 1); chant(3 == 3); chant(3 != 3); chant(!hai);\n", 0,
     b"hai\niie\nhai\niie\nhai\niie\niie\n", b""),
    ("locals_loop", "kaku i = 0; kaku sum = 0;\naida (i < 100) { sum = sum + i; i = i + 1; }\nchant(sum);\n", 0, b"4950\n", b""),
    ("branch", "waza sign(n: int64) -> int64 { moshi (n < 0) { kaesu -1; } sore { moshi (n == 0) { kaesu 0; } } kaesu 1; }\n"
               "chant(sign(-5)); chant(sign(0)); chant(sign(9));\n", 0, b"-1\n0\n1\n", b""),
    ("args_order", "waza f(a: int64, b: int64, c: int64) -> int64 { kaesu a * 100 + b * 10 + c; }\nchant(f(1, 2, 3));\n", 0, b"123\n", b""),
    ("func_locals", "waza g(n: int64) -> int64 { kaku t = n * 2; kaku u = t + 1; kaesu u; }\nchant(g(20)); chant(g(g(1)));\n", 0, b"41\n7\n", b""),
    ("recursion", "waza fib(n: int64) -> int64 { moshi (n < 2) { kaesu n; } kaesu fib(n - 1) + fib(n - 2); }\nchant(fib(20));\n", 0, b"6765\n", b""),
    ("deep_recursion", "waza depth(n: int64) -> int64 { moshi (n == 0) { kaesu 0; } kaesu depth(n - 1) + 1; }\nchant(depth(5000));\n", 0, b"5000\n", b""),
    ("exit_from_function", EXIT + "waza fib(n: int64) -> int64 { moshi (n < 2) { kaesu n; } kaesu fib(n - 1) + fib(n - 2); }\n"
                           "chant(fib(10)); windows_test_exit(fib(7));\nchant(999);\n", 13, b"55\n", b""),
    ("string_stdout", 'chant("Mio Windows"); chant("");\n', 0, b"Mio Windows\n\n", b""),
    ("string_local", 'waza say(s: string) -> unit { chant(s); }\nkaku m = "hello"; say(m); say("x");\n', 0, b"hello\nx\n", b""),
    ("int32_wrap", "kaku a: int32 = 2147483647; kaku b: int32 = a + 1; chant(b);\n", 0, b"-2147483648\n", b""),
    ("global_state", "kaku counter = 0;\nwaza bump() -> unit { counter = counter + 1; }\nbump(); bump(); bump(); chant(counter);\n", 0, b"3\n", b""),
    ("divide_by_zero", "kaku z = 0; chant(1 / z);\n", 1, b"", b"runtime error: division by zero\n"),
]

# Unsupported constructs must fail explicitly at build time (never produce an image).
REJECT = [
    ("float", "kaku x = 1.5; chant(x + 1.5);\n", "UNSUPPORTED"),
    ("array", "kaku a = [1, 2, 3]; chant(a[0]);\n", "UNSUPPORTED_OPCODE"),
    ("closure", "waza mk() -> int64 { kaku n = 1; kaku f = waza() -> int64 { kaesu n; }; kaesu f(); }\nchant(mk());\n", "UNSUPPORTED"),
    ("string_concat", 'kaku s = "a"; chant(s == "a");\n', "UNSUPPORTED"),
]

# Cases that need the heap-capable backend (lowerwinrt): NativeFS, UTF-8 paths, large transfers. Files are created in the
# working directory of the run (the evidence directory).
FS = 'yobu "kiso/fs";\nyobu "kiso/string";\n'
RUN_HEAP = [
    ("fs_roundtrip", FS + 'kaku w = fs.write_all("fs-roundtrip.txt", string.to_bytes("hello file\\n"));\n'
     'moshi (w.error == mu) { chant("written"); } sore { chant("write failed"); }\n'
     'kaku r = fs.read_all("fs-roundtrip.txt");\n'
     'moshi (r.error == mu) { chant(len(r.data)); kaku s = string.from_utf8(r.data); moshi (s != mu) { chant(s); } } sore { chant("read failed"); }\n'
     'kaku m = fs.read_all("no-such-file-for-mio.txt"); moshi (m.error != mu) { chant("missing reported"); }\n',
     0, b"written\n11\nhello file\n\nmissing reported\n", b""),
    ("fs_utf8_path_and_large", FS + 'yobu "kiso/array";\n'
     'kaku data: []uint8 = []; kaku i = 0; aida (i < 200000) { array.push(data, uint8(i - (i / 251) * 251)); i = i + 1; }\n'
     'kaku w = fs.write_all("fs-テスト.bin", data); moshi (w.error != mu) { chant("write failed"); }\n'
     'kaku r = fs.read_all("fs-テスト.bin");\n'
     'moshi (r.error != mu) { chant("read failed"); } sore { chant(len(r.data)); chant(r.data[199999]); chant(r.data[250]); }\n',
     0, b"200000\n" + str(199999 % 251).encode() + b"\n250\n", b""),
    ("fs_directories", 'yobu "kiso/fs";\nyobu "kiso/string";\nkaku made = fs.create_dir("sub");\nmoshi (made.error == mu) { chant("mkdir ok"); } sore { chant("mkdir failed"); }\nkaku again = fs.create_dir("sub");\nmoshi (again.error != mu) { chant("mkdir twice reported"); }\nfs.write_all("sub/b.txt", string.to_bytes("bb"));\nfs.write_all("sub/a.txt", string.to_bytes("a"));\nkaku listing = fs.read_dir("sub");\nmoshi (listing.error == mu) {\n    kaku i = 0;\n    aida (i < len(listing.entries)) { chant(listing.entries[i].name); i = i + 1; }\n    chant(len(listing.entries));\n} sore { chant("read_dir failed"); }\nkaku gone = fs.read_dir("nonexistent-dir");\nmoshi (gone.error != mu) { chant("missing dir reported"); }\n',
     0, b"mkdir ok\nmkdir twice reported\na.txt\nb.txt\n2\nmissing dir reported\n", b""),
]
