/* Mio Linux x86_64 native runtime (EXPERIMENTAL PROTOTYPE, per approved decision 1).
 *
 * Precise, non-moving, stop-the-world mark/sweep over the frozen Mio Object ABI v1
 * (identical layout to the macOS ARM64 runtime):
 *   - object reference = payload address; the 16-byte header sits right before it:
 *       -16 u32 typeID   -12 u32 flags   -8 u64 payloadSize
 *     flags: mark=1 scanned=2 free=4 old=8 age=bits4..7 remembered=256
 *     free block: typeID 0, flags bit2, flags>>3 = 1-based relative link (16-byte units
 *     from the object origin), payloadSize = physical span - 16.
 *   - heap mapping: 64-byte heap header | objects | 3072-byte telemetry | side metadata
 *   - physical span = (payload + 16 + 15) & ~15; spans >= LOS threshold (128 KiB) live in
 *     their own mapping with a 32-byte prefix {all-next, mapping length, young-next,
 *     remembered-next}; header at +32, payload at +48.
 * Roots: the Shadow Frame chain published by generated code (never conservative).
 * Freestanding, position independent, no libc, no relocations (see gen_rt.sh).
 * Status: this is the interim runtime. The committed ../rt_blob.go is the .text of this file
 * compiled by gen_rt.sh (gcc 14.2.0, x86-64; flags are listed in gen_rt.sh) and is what the
 * Linux backend embeds in every image that uses the managed heap. Building Mio does not need gcc.
 * TestRuntimeBlobsMatchSources re-runs the script and compares the result with the committed
 * blob (skipped, with a reason, unless the local gcc version is the one recorded in that test).
 *
 * The "pure-Mio Runtime IR collector bridge" below (descriptor flag 4, mio_* entry points)
 * is dormant here: the backend writes zero into those descriptor words and never sets flag 4,
 * so those paths are never taken. They are kept (not deleted) because they are interleaved with
 * the allocation and collection code and the descriptor layout depends on them; no test in this
 * change exercises them.
 */
typedef unsigned long u64;
typedef long i64;
typedef unsigned char u8;
typedef unsigned int u32;
typedef int i32;

#define RT_STATE 0x10000000UL
#define ALWAYS_INLINE static inline __attribute__((always_inline))

/* ---- Object ABI v1 constants (from darwinarm64/heap.go, m12/m13_*.go, gc/layout.mio) ---- */
#define HEAP_HEADER 64
#define OBJ_HEADER 16
#define OBJ_ALIGN 16
#define TELEMETRY_BYTES 3072
#define LOS_PREFIX 32
#define LOS_THRESHOLD 131072
#define PAGE_BYTES 4096
enum { T_STRUCT = 100, T_ARRAY = 101, T_STORAGE = 102, T_CLOSURE = 103, T_ENV = 104, T_CELL = 105, T_BOX = 106, T_ENUM = 107 };
enum { KIND_STRUCT = 1, KIND_ARRAY = 2, KIND_STORAGE = 3, KIND_CLOSURE = 4, KIND_ENV = 5, KIND_CELL = 6, KIND_NULLABLE = 7, KIND_ENUM = 8 };
#define F_MARK 1u
#define F_SCANNED 2u
#define F_FREE 4u
#define F_OLD 8u
#define F_REMEMBERED 256u
#define PAYLOAD_BASE 32 /* m12PayloadBase: bitmap / element data start */
/* telemetry word indexes / byte offsets (m8Tel*, layout.mio) */
#define TEL_ALLOC_OBJECTS 0
#define TEL_ALLOC_BYTES 1
#define TEL_GC_COUNT 2
#define TEL_OCCUPIED 18
#define TEL_LOS_HEAD 320
#define TEL_LOS_BYTES 321
#define TEL_LOS_RECLAIMED 322
#define TEL_LOS_COUNT 323
#define TEL_LOS_THRESHOLD 324

enum {
	OP_INIT = 0, OP_ARRAY_LIT, OP_ARRAY_MAKE, OP_ARRAY_WITHCAP, OP_PUSH, OP_RESERVE,
	OP_CLONE, OP_TRUNCATE, OP_APPEND_ALL, OP_STRUCT_NEW, OP_FAIL, OP_COLLECT, OP_STATS,
	OP_BOX_NEW, OP_ENUM_NEW, OP_DUMP, OP_CELL_NEW, OP_ENV_NEW, OP_CLOSURE_NEW, OP_BYTES_FROM, OP_STRING_FROM
};
enum { M_ALLOC = 0, M_INDEX, M_CAPACITY, M_LENGTH, M_NIL, M_TRUNC, M_ROOT, M_COUNT };

typedef struct { u32 type, flags; u64 payload; } Hdr;
#define HDR(p) ((Hdr *)((u64)(p) - OBJ_HEADER))
#define W(p) ((u64 *)(p))

typedef struct {
	u64 heap_capacity, flags;
	u64 globals_addr, globals_count, globals_bitmap;
	u64 map_table, map_count;
	u64 msgs;      /* {u32 offset, u32 len}[] then text */
	u64 dump_path; /* NUL-terminated path or 0 */
	u64 mio_lib_init, mio_init, mio_alloc, mio_collect, mio_major, mio_remember; /* pure-Mio Runtime IR collector entries (flags&4) */
} Desc;

#define NSMALL 33
typedef struct {
	u64 base, origin, end, bump;
	u64 freelist[NSMALL + 1]; /* [1..32] exact 16-byte classes, [33] large; heads are header addresses */
	u64 stack, top, stack_cap;
	u64 g_ra, g_rbp;
	Desc *desc;
	u64 collections, live_bytes, peak_live;
	u64 tmp[4];
	u64 g_shadow;
	u64 tel;       /* telemetry base (== end) */
	u64 occupied;  /* physical bytes held by ordinary + LOS objects */
} State;
#define ST ((State *)RT_STATE)
#define TEL(i) (((u64 *)ST->tel)[i])

/* ---- pure-Mio Runtime IR collector bridge (formal collector, flags&4) ----
 * ctx (384 bytes at RT_STATE+512): 0 base 8 origin 16 end 24 bump 32 occupied 40 mark stack 48 depth
 * 56 capacity 64 shadow chain head 72 stress 80 collections 88 first error. IR ABI == System V for <= 6 args. */
#define MIO_CTX ((u64 *)(RT_STATE + 512))
#define MIO_TABLE (RT_STATE + 1024)
typedef u64 (*mio_fn1)(u64);
typedef u64 (*mio_fn3)(u64, u64, u64);
typedef u64 (*mio_fn5)(u64, u64, u64, u64, u64);
typedef u64 (*mio_fn0)(void);

ALWAYS_INLINE long sys3(long n, long a, long b, long c) {
	long r;
	__asm__ volatile("syscall" : "=a"(r) : "a"(n), "D"(a), "S"(b), "d"(c) : "rcx", "r11", "memory");
	return r;
}
ALWAYS_INLINE long sys_mmap(u64 len, int noreserve) {
	register long r10 __asm__("r10") = 0x2 | 0x20 | (noreserve ? 0x4000 : 0); /* PRIVATE|ANON|NORESERVE */
	register long r8 __asm__("r8") = -1;
	register long r9 __asm__("r9") = 0;
	long r;
	__asm__ volatile("syscall" : "=a"(r) : "a"(9L), "D"(0L), "S"(len), "d"(3L), "r"(r10), "r"(r8), "r"(r9) : "rcx", "r11", "memory");
	return r;
}
ALWAYS_INLINE void zero(void *p, u64 bytes) {
	u64 n = bytes >> 3;
	__asm__ volatile("rep stosq" : "+D"(p), "+c"(n) : "a"(0UL) : "memory");
}
ALWAYS_INLINE void copy(void *d, const void *s, u64 bytes) {
	__asm__ volatile("rep movsb" : "+D"(d), "+S"(s), "+c"(bytes) : : "memory");
}
static __attribute__((noinline)) void fail(int id) {
	Desc *d = ST->desc;
	u32 *ent = (u32 *)(d->msgs + 8UL * id);
	sys3(1, 2, (long)(d->msgs + ent[0]), ent[1]);
	sys3(231, 1, 0, 0);
	for (;;) {}
}

/* ---------------- physical layout helpers ---------------- */
ALWAYS_INLINE u64 span_of(u64 payload) { return (payload + OBJ_HEADER + OBJ_ALIGN - 1) & ~(u64)(OBJ_ALIGN - 1); }

/* free-list links are 1-based relative indexes (16-byte units from the object origin) in flags>>3 */
ALWAYS_INLINE u64 link_of(u64 hdr_addr) { return ((hdr_addr - ST->origin) >> 4) + 1; }
ALWAYS_INLINE u64 addr_of(u64 link) { return ST->origin + ((link - 1) << 4); }

ALWAYS_INLINE void list_insert(u64 hdr_addr, u64 span) {
	Hdr *h = (Hdr *)hdr_addr;
	u64 cls = span >> 4;
	if (cls > 32) cls = 33;
	h->type = 0;
	h->payload = span - OBJ_HEADER;
	u64 head = ST->freelist[cls];
	h->flags = F_FREE | (u32)((head ? link_of(head) : 0) << 3);
	ST->freelist[cls] = hdr_addr;
}
ALWAYS_INLINE u64 list_next(Hdr *h) { u64 l = h->flags >> 3; return l ? addr_of(l) : 0; }

ALWAYS_INLINE u64 carve(u64 hdr_addr, u64 have, u64 span) {
	if (have - span >= OBJ_ALIGN) list_insert(hdr_addr + span, have - span);
	else span = have;
	return span;
}

ALWAYS_INLINE void set_next(Hdr *h, u64 next) { h->flags = F_FREE | (u32)((next ? link_of(next) : 0) << 3); }

/* Returns the header address of a block of exactly `got` bytes recorded in ->payload+16. */
static u64 try_alloc(u64 span) {
	State *s = ST;
	u64 cls = span >> 4;
	if (cls <= 32) {
		for (u64 c = cls; c <= 32; c++) {
			if (s->freelist[c]) {
				u64 a = s->freelist[c];
				s->freelist[c] = list_next((Hdr *)a);
				u64 got = carve(a, c << 4, span);
				((Hdr *)a)->payload = got - OBJ_HEADER;
				return a;
			}
		}
	}
	u64 prev = 0, a = s->freelist[33];
	while (a) {
		Hdr *h = (Hdr *)a;
		u64 have = h->payload + OBJ_HEADER, nxt = list_next(h);
		if (have >= span) {
			if (prev) set_next((Hdr *)prev, nxt); else s->freelist[33] = nxt;
			u64 got = carve(a, have, span);
			h->payload = got - OBJ_HEADER;
			return a;
		}
		prev = a;
		a = nxt;
	}
	if (s->end - s->bump >= span) {
		a = s->bump;
		s->bump += span;
		((Hdr *)a)->payload = span - OBJ_HEADER;
		return a;
	}
	return 0;
}

/* ---------------- pointer classification ---------------- */
/* Returns the header of the live object whose payload starts exactly at v, or 0.
 * Ordinary heap: 16-byte aligned payload inside [origin+16, bump). LOS: exact payload start
 * of a registered mapping node. Never loads outside those two areas. */
static Hdr *classify(u64 v) {
	State *s = ST;
	if (v >= s->origin + OBJ_HEADER && v < s->bump && !(v & (OBJ_ALIGN - 1))) {
		Hdr *h = HDR(v);
		return h->type ? h : 0;
	}
	for (u64 node = TEL(TEL_LOS_HEAD); node; node = W(node)[0]) {
		if (v == node + LOS_PREFIX + OBJ_HEADER) {
			Hdr *h = (Hdr *)(node + LOS_PREFIX);
			return h->type ? h : 0;
		}
	}
	return 0;
}

/* ---------------- marking ---------------- */
ALWAYS_INLINE void push_mark(u64 v) {
	State *s = ST;
	if (!v || (v & 1)) return;
	Hdr *h = classify(v);
	if (!h) fail(M_ROOT); /* an exact reference must name a live object */
	if (h->flags & F_MARK) return;
	h->flags |= F_MARK;
	((u64 *)s->stack)[s->top++] = v;
}

static void scan_bitmap_fields(u64 *w, u64 count, u64 words) {
	for (u64 i = 0; i < count; i++)
		if ((w[4 + (i >> 6)] >> (i & 63)) & 1) push_mark(w[4 + words + i]);
}

static void drain(void) {
	State *s = ST;
	while (s->top) {
		u64 *w = (u64 *)((u64 *)s->stack)[--s->top];
		Hdr *h = HDR(w);
		switch (h->type) {
		case T_ARRAY: push_mark(w[5]); break;
		case T_STORAGE:
			if ((w[0] >> 16) & 1) { /* reference elements */
				u64 n = w[1];
				for (u64 i = 0; i < n; i++) push_mark(w[4 + i]);
			}
			break;
		case T_STRUCT: scan_bitmap_fields(w, w[1], w[3]); break;
		case T_ENUM: scan_bitmap_fields(w, w[2], w[3]); break;
		case T_BOX: break;
		case T_CLOSURE: push_mark(w[5]); break;                              /* environment */
		case T_ENV: for (u64 i = 0; i < w[1]; i++) push_mark(w[2 + i]); break; /* shared cells */
		case T_CELL: if ((w[0] >> 8) & 1) push_mark(w[1]); break;           /* reference cell */
		default: fail(M_ROOT); /* unknown layout: closures etc. are not implemented here */
		}
	}
}

static __attribute__((noinline)) void hex_diag(char tag, u64 v) {
	char b[24]; int n = 0;
	b[n++] = tag; b[n++] = '=';
	for (int i = 60; i >= 0; i -= 4) { int d = (int)((v >> i) & 15); b[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10); }
	b[n++] = '\n';
	sys3(1, 2, (long)b, n);
}
static __attribute__((noinline)) void bad_root(u64 v, u64 where, i64 off) {
	hex_diag('v', v); hex_diag('r', where); hex_diag('o', (u64)off);
	fail(M_ROOT);
}
/* Exactness check (GC stress): every named root slot is nil, a static string id, or a live object. */
ALWAYS_INLINE void check_root(u64 v, u64 where, i64 off) {
	if (!v || (v & 1)) return;
	if (!classify(v)) bad_root(v, where, off);
}
ALWAYS_INLINE void push_root(u64 v, u64 where, i64 off) {
	if (ST->desc->flags & 1) check_root(v, where, off);
	push_mark(v);
}

#define MAX_SHADOW_FRAMES 1100
#define MAX_ROOTS_PER_FRAME (1UL << 21)
/* Shadow Frame contract (identical to AArch64): record = {previous, count | indirect << 32, values...}.
 * The first `indirect` values are ADDRESSES of root slots (dereferenced here, at GC time);
 * the rest are root values copied by the compiler at the safepoint. Never conservative. */
static void mark_shadow_chain(void) {
	State *s = ST;
	u64 frames = 0;
	for (u64 *rec = (u64 *)s->g_shadow; rec; rec = (u64 *)rec[0]) {
		if (++frames > MAX_SHADOW_FRAMES) fail(M_ROOT);
		u64 count = rec[1] & 0xffffffffUL, indirect = rec[1] >> 32;
		if (count > MAX_ROOTS_PER_FRAME || indirect > count) fail(M_ROOT);
		for (u64 i = 0; i < count; i++) {
			u64 v = rec[2 + i];
			if (i < indirect) v = *(u64 *)v;
			push_root(v, (u64)rec, (i64)i);
		}
		drain();
	}
}
static void mark_roots(void) {
	State *s = ST;
	Desc *d = s->desc;
	for (int i = 0; i < 4; i++) push_mark(s->tmp[i]);
	if (d->flags & 2) { /* shadow-frame mode (formal contract) */
		mark_shadow_chain();
		drain();
		return;
	}
	/* legacy return-address stack-map mode: comparison baseline only */
	u64 *g = (u64 *)d->globals_addr;
	u64 *bm = (u64 *)d->globals_bitmap;
	for (u64 i = 0; i < d->globals_count; i++)
		if ((bm[i >> 6] >> (i & 63)) & 1) push_root(g[i], 0, (i64)i);
	u64 ra = s->g_ra, rbp = s->g_rbp;
	u32 *tab = (u32 *)d->map_table;
	for (;;) {
		i64 lo = 0, hi = (i64)d->map_count - 1, hit = -1;
		while (lo <= hi) {
			i64 mid = (lo + hi) >> 1;
			u32 key = tab[mid * 2];
			if (key == (u32)ra) { hit = mid; break; }
			if (key < (u32)ra) lo = mid + 1; else hi = mid - 1;
		}
		if (hit >= 0) {
			i32 *m = (i32 *)((u64)tab + tab[hit * 2 + 1]);
			for (i32 i = 0; i < m[0]; i++) push_root(*(u64 *)(rbp + (i64)m[1 + i]), ra, m[1 + i]);
			drain();
		}
		u64 next = *(u64 *)rbp;
		if (!next) break;
		ra = *(u64 *)(rbp + 8);
		rbp = next;
	}
	drain();
}

/* ---------------- sweep ---------------- */
static void sweep(void) {
	State *s = ST;
	for (int i = 0; i <= NSMALL; i++) s->freelist[i] = 0;
	u64 p = s->origin, run = 0, runstart = 0, live = 0;
	while (p < s->bump) {
		Hdr *h = (Hdr *)p;
		u64 span = span_of(h->payload);
		if (h->type && (h->flags & F_MARK)) {
			h->flags &= ~F_MARK;
			live += span;
			if (run) { list_insert(runstart, run); run = 0; }
		} else {
			if (!run) runstart = p;
			run += span;
			s->occupied -= h->type ? span : 0;
		}
		p += span;
	}
	if (run) s->bump = runstart; /* trailing free run returns to the bump region */
	/* large objects: free the unmarked mappings */
	u64 *link = &TEL(TEL_LOS_HEAD);
	u64 node = *link;
	while (node) {
		u64 next = W(node)[0];
		Hdr *h = (Hdr *)(node + LOS_PREFIX);
		u64 sp = span_of(h->payload);
		if (h->flags & F_MARK) {
			h->flags &= ~F_MARK;
			live += sp;
			link = &W(node)[0];
		} else {
			*link = next;
			s->occupied -= sp;
			TEL(TEL_LOS_BYTES) -= sp;
			TEL(TEL_LOS_COUNT) -= 1;
			TEL(TEL_LOS_RECLAIMED) += sp;
			sys3(11, (long)node, (long)W(node)[1], 0); /* munmap(node, mapping length) */
		}
		node = next;
	}
	s->live_bytes = live;
	if (live > s->peak_live) s->peak_live = live;
	TEL(TEL_OCCUPIED) = s->occupied;
}

/* Old->Young write barrier (generational formal collector only). owner = object whose payload slots changed. */
static void barrier(u64 owner) {
	State *s = ST;
	if ((s->desc->flags & 4) && !(s->desc->flags & 8)) ((mio_fn3)s->desc->mio_remember)((u64)MIO_CTX, owner, 0);
}
static void mio_sync(void) {
	State *s = ST;
	u64 *c = MIO_CTX;
	s->bump = c[3];
	s->occupied = c[4];
	s->collections = c[10];
}
/* Publish the chain plus the runtime's own temporaries (as a one-frame shadow record on this C stack). */
static u64 mio_roots(u64 *rec) {
	State *s = ST;
	u64 n = 0;
	for (int i = 0; i < 4; i++) if (s->tmp[i]) rec[2 + n++] = s->tmp[i];
	if (!n) return s->g_shadow;
	rec[0] = s->g_shadow;
	rec[1] = n;
	return (u64)rec;
}

static void collect(void) {
	State *s = ST;
	if (s->desc->flags & 4) {
		u64 rec[6];
		u64 *c = MIO_CTX;
		c[8] = mio_roots(rec);
		u64 rc = ((mio_fn1)s->desc->mio_collect)((u64)c);
		c[8] = 0;
		mio_sync();
		if (rc) fail(M_ROOT);
		return;
	}
	ST->collections++;
	TEL(TEL_GC_COUNT) = ST->collections;
	mark_roots();
	sweep();
}

static u64 los_alloc(u64 span) {
	State *s = ST;
	u64 length = (LOS_PREFIX + span + PAGE_BYTES - 1) & ~(u64)(PAGE_BYTES - 1);
	long r = sys_mmap(length, 0);
	if (r < 0 && r > -4096) return 0;
	u64 node = (u64)r;
	W(node)[0] = TEL(TEL_LOS_HEAD);
	W(node)[1] = length;
	TEL(TEL_LOS_HEAD) = node;
	TEL(TEL_LOS_BYTES) += span;
	TEL(TEL_LOS_COUNT) += 1;
	((Hdr *)(node + LOS_PREFIX))->payload = span - OBJ_HEADER;
	return node + LOS_PREFIX;
}

/* Returns the payload address of a zeroed object, or fails with the common OOM exit. */
static u64 gc_alloc(u32 type, u64 payload) {
	State *s = ST;
	if (s->desc->flags & 4) {
		u64 rec[6];
		u64 *c = MIO_CTX;
		c[8] = mio_roots(rec);
		u64 r = ((mio_fn3)s->desc->mio_alloc)((u64)c, type, payload);
		c[8] = 0;
		mio_sync();
		if (!r) fail(c[11] ? M_ROOT : M_ALLOC);
		return r;
	}
	u64 cap = s->end - s->origin;
	if (payload > cap) fail(M_ALLOC);
	u64 span = span_of(payload);
	u64 hdr = 0;
	u64 threshold = TEL(TEL_LOS_THRESHOLD);
	if (!threshold) threshold = LOS_THRESHOLD;
	int large = span >= threshold;
	if (s->desc->flags & 1) collect();
	for (int attempt = 0; attempt < 2 && !hdr; attempt++) {
		if (s->occupied + span <= cap) hdr = large ? los_alloc(span) : try_alloc(span);
		if (!hdr && !attempt) collect();
	}
	if (!hdr) fail(M_ALLOC);
	Hdr *h = (Hdr *)hdr;
	u64 real = span_of(h->payload);
	if (!large) {
		/* free-list reuse may hand back a slightly larger block: keep the physical span */
		real = h->payload + OBJ_HEADER;
	}
	zero((u8 *)h + OBJ_HEADER, real - OBJ_HEADER);
	h->type = type;
	h->flags = 0;
	h->payload = payload; /* allocated objects record the requested payload size */
	s->occupied += real;
	TEL(TEL_OCCUPIED) = s->occupied;
	TEL(TEL_ALLOC_OBJECTS) += 1;
	TEL(TEL_ALLOC_BYTES) += real;
	return hdr + OBJ_HEADER;
}

/* UTF-8 validity, the same acceptance as Go's utf8.Valid: shortest form only, no surrogates, <= U+10FFFF. */
static int utf8_valid(const u8 *p, u64 n) {
	u64 i = 0;
	while (i < n) {
		u8 c = p[i];
		if (c < 0x80) { i++; continue; }
		if (c >= 0xC2 && c <= 0xDF) {
			if (i + 1 >= n || (p[i + 1] & 0xC0) != 0x80) return 0;
			i += 2; continue;
		}
		if (c >= 0xE0 && c <= 0xEF) {
			if (i + 2 >= n) return 0;
			u8 c1 = p[i + 1], c2 = p[i + 2];
			if ((c1 & 0xC0) != 0x80 || (c2 & 0xC0) != 0x80) return 0;
			if (c == 0xE0 && c1 < 0xA0) return 0;
			if (c == 0xED && c1 >= 0xA0) return 0;
			i += 3; continue;
		}
		if (c >= 0xF0 && c <= 0xF4) {
			if (i + 3 >= n) return 0;
			u8 c1 = p[i + 1], c2 = p[i + 2], c3 = p[i + 3];
			if ((c1 & 0xC0) != 0x80 || (c2 & 0xC0) != 0x80 || (c3 & 0xC0) != 0x80) return 0;
			if (c == 0xF0 && c1 < 0x90) return 0;
			if (c == 0xF4 && c1 >= 0x90) return 0;
			i += 4; continue;
		}
		return 0;
	}
	return 1;
}

/* ---------------- arrays (descriptor + separate storage, as in M12) ---------------- */
/* descriptor payload (48 bytes): w0=KIND_ARRAY|width<<8  w1=length  w2=capacity  w3=1  w4=1  w5=storage
 * storage payload (32 + cap*width): w0=KIND_STORAGE|width<<8|ref<<16  w1=capacity  w2=1  w3=ref; data at +32 */
#define A_WIDTH(a) ((W(a)[0] >> 8) & 0xff)
#define A_LEN(a) (W(a)[1])
#define A_CAP(a) (W(a)[2])
#define A_STO(a) (W(a)[5])
#define S_DATA(s) ((u8 *)(s) + PAYLOAD_BASE)

static u64 new_storage(u64 cap, u64 width, u64 ref) {
	if (cap > (1UL << 40)) fail(M_CAPACITY);
	u64 st = gc_alloc(T_STORAGE, PAYLOAD_BASE + cap * width);
	W(st)[0] = KIND_STORAGE | (width << 8) | (ref << 16);
	W(st)[1] = cap;
	W(st)[2] = 1;
	W(st)[3] = ref;
	return st;
}
static u64 new_array(u64 len, u64 cap, u64 width, u64 ref) {
	u64 st = new_storage(cap, width, ref);
	ST->tmp[0] = st; /* keep the storage alive across the descriptor allocation */
	u64 a = gc_alloc(T_ARRAY, 48);
	ST->tmp[0] = 0;
	W(a)[0] = KIND_ARRAY | (width << 8);
	W(a)[1] = len;
	W(a)[2] = cap;
	W(a)[3] = 1;
	W(a)[4] = 1;
	W(a)[5] = st;
	return a;
}
ALWAYS_INLINE void elem_store(u64 sto, u64 i, u64 width, u64 v) {
	if (width == 1) S_DATA(sto)[i] = (u8)v; else ((u64 *)S_DATA(sto))[i] = v;
}
static u64 grown(u64 cur, u64 required) {
	u64 c = cur < 4 ? 4 : cur;
	while (c < required) {
		if (c < 1024) c *= 2; else c += c / 2;
	}
	return c;
}
static void ensure_room(u64 a, u64 extra) {
	u64 required = A_LEN(a) + extra;
	if (required < extra) fail(M_CAPACITY);
	if (A_CAP(a) >= required) return;
	u64 nc = grown(A_CAP(a), required);
	u64 ns = new_storage(nc, A_WIDTH(a), (W(A_STO(a))[0] >> 16) & 1);
	copy(S_DATA(ns), S_DATA(A_STO(a)), A_LEN(a) * A_WIDTH(a));
	A_STO(a) = ns;
	A_CAP(a) = nc;
	barrier(a); /* the descriptor now references a fresh Young storage */
}

static void dump_heap(void) {
	State *s = ST;
	const char *path = (const char *)s->desc->dump_path;
	if (!path) return;
	long fd = sys3(2, (long)path, 0x241 /* O_WRONLY|O_CREAT|O_TRUNC */, 0644);
	if (fd < 0) return;
	u64 n;
	/* directory: heap header | object bytes | telemetry | LOS node count */
	u64 sizes[4] = { HEAP_HEADER, s->bump - s->origin, TELEMETRY_BYTES, 0 };
	for (u64 node = TEL(TEL_LOS_HEAD); node; node = W(node)[0]) sizes[3]++;
	sys3(1, fd, (long)sizes, sizeof sizes);
	sys3(1, fd, (long)s->base, HEAP_HEADER);
	n = s->bump - s->origin;
	if (n) sys3(1, fd, (long)s->origin, (long)n);
	sys3(1, fd, (long)s->tel, TELEMETRY_BYTES);
	for (u64 node = TEL(TEL_LOS_HEAD); node; node = W(node)[0])
		sys3(1, fd, (long)node, LOS_PREFIX + OBJ_HEADER + 64); /* prefix + header + first payload words */
	sys3(3, fd, 0, 0);
}

u64 mio_rt(u64 op, u64 a, u64 b, u64 c, u64 d) {
	State *s = ST;
	switch (op) {
	case OP_INIT: {
		Desc *ds = (Desc *)a;
		s->desc = ds;
		u64 cap = (ds->heap_capacity + 4095) & ~4095UL;
		/* heap header + objects + telemetry + side metadata (16 bytes per possible header) */
		long base = sys_mmap(HEAP_HEADER + cap + TELEMETRY_BYTES + cap + 4096, 1);
		long stk = sys_mmap(cap / 2 + 4096, 1);
		if (base < 0 || stk < 0) { sys3(231, 1, 0, 0); }
		s->base = (u64)base;
		s->origin = s->bump = (u64)base + HEAP_HEADER;
		s->end = s->origin + cap;
		s->tel = s->end;
		s->stack = (u64)stk;
		s->stack_cap = cap / 16;
		W(base)[0] = 0x38504145484F494DUL; /* "MIOHEAP8" */
		W(base)[1] = s->bump;              /* allocation cursor */
		W(base)[2] = s->tel;               /* end of objects == telemetry base */
		W(base)[3] = cap;                  /* object capacity */
		W(base)[6] = s->origin;            /* first object header */
		TEL(TEL_LOS_THRESHOLD) = LOS_THRESHOLD;
		if (ds->flags & 4) { /* the Mio collector owns the heap from here on */
			((mio_fn0)ds->mio_lib_init)();
			u64 *c = MIO_CTX;
			((mio_fn5)ds->mio_init)((u64)c, (u64)base, cap, (u64)stk, cap / 16);
			c[9] = ds->flags & 1;
			mio_sync();
		}
		return 0;
	}
	case OP_ARRAY_LIT: { /* a=width b=ref c=n d=ptr to pushed slots (first element deepest) */
		u64 h = new_array(c, c, a, b);
		u64 *slots = (u64 *)d;
		for (u64 i = 0; i < c; i++) elem_store(A_STO(h), i, a, slots[c - 1 - i]);
		return h;
	}
	case OP_ARRAY_MAKE: { /* a=width b=ref c=len d=init */
		if ((i64)c < 0) fail(M_LENGTH);
		u64 h = new_array(c, c, a, b);
		for (u64 i = 0; i < c; i++) elem_store(A_STO(h), i, a, d);
		return h;
	}
	case OP_ARRAY_WITHCAP: { /* a=width b=ref c=cap */
		if ((i64)c < 0 || c > (0x7fffffffffffffffUL / a)) fail(M_CAPACITY);
		return new_array(0, c, a, b);
	}
	case OP_PUSH: { /* a=array b=value */
		ensure_room(a, 1);
		elem_store(A_STO(a), A_LEN(a), A_WIDTH(a), b);
		if ((W(A_STO(a))[0] >> 16) & 1) barrier(A_STO(a));
		A_LEN(a)++;
		return 0;
	}
	case OP_RESERVE: { /* a=array b=additional */
		if ((i64)b < 0) fail(M_CAPACITY);
		if (b > 0x7fffffffffffffffUL - A_LEN(a)) fail(M_CAPACITY);
		ensure_room(a, b);
		return 0;
	}
	case OP_CLONE: { /* a=array */
		u64 n = new_array(A_LEN(a), A_LEN(a), A_WIDTH(a), (W(A_STO(a))[0] >> 16) & 1);
		copy(S_DATA(A_STO(n)), S_DATA(A_STO(a)), A_LEN(a) * A_WIDTH(a));
		return n;
	}
	case OP_TRUNCATE: { /* a=array b=new length */
		if ((i64)b < 0 || b > A_LEN(a)) fail(M_TRUNC);
		u64 width = A_WIDTH(a);
		u8 *p = S_DATA(A_STO(a));
		for (u64 i = b * width; i < A_LEN(a) * width; i++) p[i] = 0;
		A_LEN(a) = b;
		return 0;
	}
	case OP_APPEND_ALL: { /* a=dst b=src (the source prefix as it was before the operation) */
		u64 n = A_LEN(b);
		if (!n) return 0;
		ensure_room(a, n);
		copy(S_DATA(A_STO(a)) + A_LEN(a) * A_WIDTH(a), S_DATA(A_STO(b)), n * A_WIDTH(a));
		if ((W(A_STO(a))[0] >> 16) & 1) barrier(A_STO(a));
		A_LEN(a) += n;
		return 0;
	}
	case OP_STRUCT_NEW: { /* a=count b=bitmap ptr c=ptr to pushed slots */
		u64 words = (a + 63) >> 6;
		u64 o = gc_alloc(T_STRUCT, PAYLOAD_BASE + 8 * words + 8 * a);
		u64 *w = W(o);
		w[0] = KIND_STRUCT; w[1] = a; w[2] = a; w[3] = words;
		for (u64 i = 0; i < words; i++) w[4 + i] = ((u64 *)b)[i];
		u64 *slots = (u64 *)c;
		for (u64 i = 0; i < a; i++) w[4 + words + i] = slots[a - 1 - i];
		return o;
	}
	case OP_ENUM_NEW: { /* a=payload count b=bitmap ptr c=ptr to pushed slots d=tag */
		u64 words = (a + 63) >> 6;
		u64 o = gc_alloc(T_ENUM, PAYLOAD_BASE + 8 * words + 8 * a);
		u64 *w = W(o);
		w[0] = KIND_ENUM; w[1] = d; w[2] = a; w[3] = words;
		for (u64 i = 0; i < words; i++) w[4 + i] = ((u64 *)b)[i];
		u64 *slots = (u64 *)c;
		for (u64 i = 0; i < a; i++) w[4 + words + i] = slots[a - 1 - i];
		return o;
	}
	case OP_BOX_NEW: {
		u64 o = gc_alloc(T_BOX, 16);
		W(o)[0] = KIND_NULLABLE;
		W(o)[1] = a;
		return o;
	}
	case OP_BYTES_FROM: { /* a=source address b=length: a fresh compact byte array (string -> bytes) */
		u64 n = new_array(b, b, 1, 0);
		copy(S_DATA(A_STO(n)), (const u8 *)a, b);
		return n;
	}
	case OP_STRING_FROM: { /* a=byte array: its dynamic-string clone, or 0 (nil) when not valid UTF-8 */
		if (!utf8_valid(S_DATA(A_STO(a)), A_LEN(a))) return 0;
		u64 n = new_array(A_LEN(a), A_LEN(a), 1, 0);
		copy(S_DATA(A_STO(n)), S_DATA(A_STO(a)), A_LEN(a));
		return n;
	}
	case OP_CELL_NEW: { /* a=value b=1 when the value is a reference */
		u64 o = gc_alloc(T_CELL, 16);
		W(o)[0] = KIND_CELL | (b << 8);
		W(o)[1] = a;
		return o;
	}
	case OP_ENV_NEW: { /* a=cell count b=ptr to pushed cells (first cell deepest) */
		u64 o = gc_alloc(T_ENV, 16 + 8 * a);
		u64 *w = W(o);
		w[0] = KIND_ENV; w[1] = a;
		u64 *slots = (u64 *)b;
		for (u64 i = 0; i < a; i++) w[2 + i] = slots[a - 1 - i];
		return o;
	}
	case OP_CLOSURE_NEW: { /* a=function id b=parameters|returns<<16 c=code address d=environment (0 when none) */
		u64 o = gc_alloc(T_CLOSURE, 48);
		u64 *w = W(o);
		w[0] = KIND_CLOSURE; w[1] = a; w[2] = b & 0xffff; w[3] = b >> 16; w[4] = c; w[5] = d;
		return o;
	}
	case OP_FAIL: fail((int)a); return 0;
	case OP_COLLECT: collect(); return 0;
	case OP_DUMP: dump_heap(); return 0;
	case OP_STATS: /* a: 0 collections, 1 live bytes, 2 peak, 3 allocated objects, 4 heap capacity, 5 bump used, 6 occupied */
		switch (a) {
		case 0: return s->collections;
		case 1: return s->live_bytes;
		case 2: return s->peak_live;
		case 3: return TEL(TEL_ALLOC_OBJECTS);
		case 4: return s->end - s->origin;
		case 5: return s->bump - s->origin;
		default: return s->occupied;
		}
	}
	return 0;
}
