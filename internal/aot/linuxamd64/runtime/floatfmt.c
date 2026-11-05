/* Freestanding shortest round-trip float formatter (Burger-Dybvig / Dragon4),
 * output identical to Go strconv.FormatFloat(x, 'g', -1, 32|64).
 * Built position-independent with no libc, no relocations, no data section:
 *   see gen.sh. The resulting machine-code blob is embedded in the Linux
 *   x86_64 backend as a runtime routine (System V AMD64 calling convention).
 *
 *   unsigned long mio_fmt_float(unsigned long bits, int is32, char *out)
 *   returns number of bytes written (no trailing newline).
 */
typedef unsigned int u32;
typedef unsigned long u64;
#define L 40 /* 1280-bit bignums */

typedef struct { u32 w[L]; } big;

static inline __attribute__((always_inline)) void b_set(big *a, u64 v) {
	for (int i = 0; i < L; i++) a->w[i] = 0;
	a->w[0] = (u32)v; a->w[1] = (u32)(v >> 32);
}
static inline __attribute__((always_inline)) void b_copy(big *d, const big *s) { for (int i = 0; i < L; i++) d->w[i] = s->w[i]; }
static inline __attribute__((always_inline)) void b_mul_small(big *a, u32 m) {
	u64 c = 0;
	for (int i = 0; i < L; i++) { u64 t = (u64)a->w[i] * m + c; a->w[i] = (u32)t; c = t >> 32; }
}
static inline __attribute__((always_inline)) void b_shl(big *a, int n) {
	int ws = n / 32, bs = n % 32;
	for (int i = L - 1; i >= 0; i--) {
		u32 v = 0;
		if (i - ws >= 0) {
			v = a->w[i - ws] << bs;
			if (bs && i - ws - 1 >= 0) v |= a->w[i - ws - 1] >> (32 - bs);
		}
		a->w[i] = v;
	}
}
static inline __attribute__((always_inline)) void b_add(big *a, const big *b) {
	u64 c = 0;
	for (int i = 0; i < L; i++) { u64 t = (u64)a->w[i] + b->w[i] + c; a->w[i] = (u32)t; c = t >> 32; }
}
static inline __attribute__((always_inline)) void b_sub(big *a, const big *b) { /* a >= b */
	u64 br = 0;
	for (int i = 0; i < L; i++) {
		u64 t = (u64)a->w[i] - b->w[i] - br;
		a->w[i] = (u32)t; br = (t >> 63) & 1;
	}
}
static inline __attribute__((always_inline)) int b_cmp(const big *a, const big *b) {
	for (int i = L - 1; i >= 0; i--) {
		if (a->w[i] != b->w[i]) return a->w[i] > b->w[i] ? 1 : -1;
	}
	return 0;
}

static inline __attribute__((always_inline)) int emit_digits(char *out, int neg, const char *dg, int nd, int dp) {
	char *p = out;
	if (neg) *p++ = '-';
	int exp = dp - 1;
	if (nd == 0) { *p++ = '0'; return (int)(p - out); }
	if (exp < -4 || exp >= 6) { /* %e */
		*p++ = dg[0];
		if (nd > 1) { *p++ = '.'; for (int i = 1; i < nd; i++) *p++ = dg[i]; }
		*p++ = 'e';
		*p++ = exp < 0 ? '-' : '+';
		int x = exp < 0 ? -exp : exp;
		if (x >= 100) { *p++ = '0' + x / 100; x %= 100; *p++ = '0' + x / 10; *p++ = '0' + x % 10; }
		else { *p++ = '0' + x / 10; *p++ = '0' + x % 10; }
		return (int)(p - out);
	}
	if (dp > 0) { for (int i = 0; i < dp; i++) *p++ = i < nd ? dg[i] : '0'; }
	else *p++ = '0';
	if (nd > dp) {
		*p++ = '.';
		for (int i = dp; i < 0; i++) *p++ = '0';
		for (int i = dp > 0 ? dp : 0; i < nd; i++) *p++ = dg[i];
	}
	return (int)(p - out);
}

static inline __attribute__((always_inline)) int put4(char *out, char a, char b, char c, char d) { out[0]=a; out[1]=b; out[2]=c; out[3]=d; return 4; }

u64 mio_fmt_float(u64 bits, int is32, char *out) {
	int neg, mbits, ebias, expmax;
	u64 mant, expo;
	if (is32) { bits &= 0xffffffffUL; neg = (int)(bits >> 31); expo = (bits >> 23) & 0xff; mant = bits & ((1UL << 23) - 1); mbits = 23; ebias = 127; expmax = 255; }
	else { neg = (int)(bits >> 63); expo = (bits >> 52) & 0x7ff; mant = bits & ((1UL << 52) - 1); mbits = 52; ebias = 1023; expmax = 2047; }
	if ((int)expo == expmax) {
		if (mant) { out[0]='N'; out[1]='a'; out[2]='N'; return 3; }
		return put4(out, neg ? '-' : '+', 'I', 'n', 'f');
	}
	if (expo == 0 && mant == 0) {
		char *p = out; if (neg) *p++ = '-'; *p++ = '0'; return (u64)(p - out);
	}
	u64 f; int e;
	int minexp = 1 - ebias - mbits;
	if (expo == 0) { f = mant; e = minexp; }
	else { f = mant | (1UL << mbits); e = (int)expo - ebias - mbits; }
	int even = (f & 1) == 0;
	int lowerClose = (expo > 1 && mant == 0); /* f == 2^mbits and not smallest normal */

	big r, s, mp, mm, t;
	if (e >= 0) {
		b_set(&r, f); b_shl(&r, e + 1 + (lowerClose ? 1 : 0));
		b_set(&s, lowerClose ? 4 : 2);
		b_set(&mp, 1); b_shl(&mp, e + (lowerClose ? 1 : 0));
		b_set(&mm, 1); b_shl(&mm, e);
	} else {
		b_set(&r, f); b_shl(&r, 1 + (lowerClose ? 1 : 0));
		b_set(&s, 1); b_shl(&s, -e + 1 + (lowerClose ? 1 : 0));
		b_set(&mp, lowerClose ? 2 : 1);
		b_set(&mm, 1);
	}
	/* bit length of f */
	int bl = 0; { u64 x = f; while (x) { bl++; x >>= 1; } }
	int p2 = e + bl - 1; /* floor(log2 v) */
	/* underestimate k = floor(log10 v) - 1 ; log10(2) ~ 0.30103 */
	int k = (int)((p2 * 30103L) / 100000L) - (p2 < 0 ? 1 : 0) - 2;
	if (k >= 0) { for (int i = 0; i < k; i++) b_mul_small(&s, 10); }
	else { for (int i = 0; i < -k; i++) { b_mul_small(&r, 10); b_mul_small(&mp, 10); b_mul_small(&mm, 10); } }
	/* raise k until (r + m+) < s  (<= when high bound is inclusive) */
	for (;;) {
		b_copy(&t, &r); b_add(&t, &mp);
		int c = b_cmp(&t, &s);
		if (even ? c < 0 : c <= 0) break;
		b_mul_small(&s, 10); k++;
	}
	char dg[40]; int nd = 0;
	for (;;) {
		b_mul_small(&r, 10); b_mul_small(&mp, 10); b_mul_small(&mm, 10);
		int d = 0;
		while (b_cmp(&r, &s) >= 0) { b_sub(&r, &s); d++; }
		int c1 = b_cmp(&r, &mm); int tc1 = even ? c1 <= 0 : c1 < 0;
		b_copy(&t, &r); b_add(&t, &mp);
		int c2 = b_cmp(&t, &s); int tc2 = even ? c2 >= 0 : c2 > 0;
		if (!tc1 && !tc2) { dg[nd++] = (char)('0' + d); continue; }
		if (tc1 && !tc2) { dg[nd++] = (char)('0' + d); break; }
		if (!tc1 && tc2) { d++; dg[nd++] = (char)('0' + d); break; }
		b_copy(&t, &r); b_shl(&t, 1);
		{ int c = b_cmp(&t, &s); /* exact tie: round half to even digit, as Go does */
		  if (c < 0 || (c == 0 && (d & 1) == 0)) dg[nd++] = (char)('0' + d); else dg[nd++] = (char)('0' + d + 1); }
		break;
	}
	/* a rounded-up digit may have become ':' only if 9+1; propagate */
	for (int i = nd - 1; i > 0 && dg[i] > '9'; i--) { dg[i] = '0'; dg[i - 1]++; }
	if (dg[0] > '9') { for (int i = nd; i > 0; i--) dg[i] = dg[i - 1]; dg[0] = '1'; dg[1] = '0'; k++; /* nd unchanged: trailing digit dropped */ }
	while (nd > 1 && dg[nd - 1] == '0') nd--;
	return (u64)emit_digits(out, neg, dg, nd, k);
}
