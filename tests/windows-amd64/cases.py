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
