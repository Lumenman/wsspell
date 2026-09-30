"""Build a WordStar 7 main spelling dictionary (SPLMNnnn.DCT) from word lists; inverse of splmn.py.

Usage: python splmnbuild.py OUT.DCT MAIN.txt [ABBR.txt] [--cp cp1125]
  MAIN: the main words; ABBR: the second part of the dictionary (abbreviations like 'acct.', 'xvi').
  Word files: UTF-8, one word per line.

No original dictionary is needed: the layout is the 7.51 one (SPLMN_FORMAT.md), fields the
engines do not read keep the values of the English 7.51 sample. Shared tails use backward
pointers and large subtrees use forward pointers. cp1125/cp866 use our literal-word language
ID 7Fh, not English affix rules. The phonetic trailer is built only when phonetic is given;
without it WordStar still checks words, only the sound-alike suggestions are off.
"""
import sys
import codecs
from collections import Counter

sys.setrecursionlimit(20000)
LITERAL_LANGUAGE = 0x7F     # project-defined ID outside the engine's language-specific branches
PAGE, ESC = 26, 25           # symbols per page; index 25 on page 0 escapes to the next page
SYM0, T1MAX, DENSE, EPS = 0x98, 0x90, 0x68, 0xF8   # node bytes start, 1-byte pointer limit, codes
HEADER = 0x5C                # 7.51 header size; the (free-form) copyright string follows it
NOTICE = b'Built by splmnbuild.py'
# Part descriptors (24h bytes): type, search flags (40h suggestions, 20h lookup, rest unknown).
PARTS = ((1, 0xE8), (2, 0x88))


def alphabet(words):
    """Pages of 25 chars: page 0 most frequent, page 1 capitals at their lowercase's index."""
    order = [c for c, _ in Counter(c for w in words for c in w).most_common()]
    # Lookup encodes input before folding case. Include capitals of rare letters too,
    # not just capitals of page 0 (otherwise e.g. Ъ in ОБЪЕДИНЁННОЕ has no input code).
    order += list(dict.fromkeys(c.upper() for c in order
                               if len(c.upper()) == 1 and c.upper() not in order))
    p0, rest = order[:ESC], order[ESC:]
    p0 += [None] * (ESC - len(p0))
    p1 = [c.upper() if c and len(c.upper()) == 1 and c.upper() != c else None for c in p0]
    rest = [c for c in rest if c not in p1]
    pages = [p0, p1] + [[None] * ESC for _ in range(2)]
    for p in pages[1:]:
        for i in range(len(p)):
            if p[i] is None and rest:
                p[i] = rest.pop(0)
    if rest:
        raise ValueError('more than %d distinct characters' % (4 * ESC))
    while pages[-1] == [None] * ESC:
        pages.pop()
    return pages


BIG = 48   # a child list inline-larger than this moves out of line when siblings follow its node


class Emitter:
    """The engine skips a sibling's subtree byte by byte, so big subtrees of nodes that have
    siblings after them are placed later and reached through a 3-byte forward pointer
    (as the English dictionary does for its top levels)."""

    def __init__(s, keys, sym0, est, size1=None, ptr=None, lit=None):
        s.keys, s.sym0, s.est, s.out = keys, sym0, est, bytearray(b'\xF8\x00')  # 0: dummy root
        s.addr, s.size, s.refs = {}, {}, Counter()
        s.size1, s.ptr, s.lit = size1 if size1 is not None else s.size, ptr, lit
        s.later, s.fix = [], []

    def lst(s, sid):
        if sid == 0:
            s.out.append(0)
            return
        if sid in s.addr and s.size1[sid] > 3:
            s.refs[sid] += 1
            s.out += s.ptr(s, sid) if s.ptr else b'\0\0\0'
            return
        a, first = len(s.out), sid not in s.addr
        if first:
            s.addr[sid] = a
        c, end, child, nxt = s.keys[sid]
        s.node(c, end, child, nxt)
        if nxt:
            s.lst(nxt)
        if first:
            s.size[sid] = len(s.out) - a

    def node(s, c, end, child, more):
        s.out.append(s.sym0 + c + (2 if more else 0) + end)
        if more and child not in s.addr and s.est[child] > BIG:
            s.fix.append((len(s.out), child))
            s.later.append(child)
            s.out += b'\0\0\0'
        else:
            s.lst(child)

    def finish(s):
        """Emit the out-of-line lists, then patch their forward pointers."""
        while s.later:
            sid = s.later.pop()
            if sid not in s.addr:
                s.lst(sid)
        if s.lit is not None:
            for p, sid in s.fix:
                a = s.addr[sid]
                s.out[p:p + 3] = bytes([s.lit + (a >> 16), a >> 8 & 255, a & 255])

    def part(s, top):
        """Root node, then the top-level list; returns (start, 26 root offsets)."""
        start, roots = len(s.out), [0] * PAGE
        s.out.append(s.sym0)
        for k, (c, end, child) in enumerate(top):
            roots[c >> 2] = len(s.out)
            s.node(c, end, child, k < len(top) - 1)
        return start, roots


def header(parts, literal):
    """Fixed fields of the 7.51 header, copyright string and input-map descriptor (+14h).
    The rest is computed by build(); unknown fields hold the English sample's values."""
    h = bytearray(HEADER)
    h[0x04], h[0x05], h[0x17], h[0x1D] = PAGE, 2, ESC << 2, 0x0A
    h[0x20], h[0x22], h[0x23], h[0x2F] = HEADER, 0xA0, DENSE, len(parts)
    h[0x33], h[0x34], h[0x37], h[0x41] = HEADER, EPS, 3, 1          # +32: copyright address
    h[0x51], h[0x52], h[0x56] = 0x54, 1, EPS                        # opaque extended header
    h += bytes([len(NOTICE)]) + NOTICE
    if len(h) & 1:
        h += b'\0'
    h[0x14:0x16] = len(h).to_bytes(2, 'big')
    h += b'\x10\x7A' + bytes(14)                   # base, span, map address filled in by build()
    return h


def descriptor(kind, flags, language):
    d = bytearray(0x24)
    d[0], d[1], d[7], d[0x12], d[0x13], d[0x1D] = 0x24, kind, 0x40, language, flags, 0xFF
    return d


def build(parts, cp, phonetic=None):
    """phonetic: module with key(word) and DIGRAPHS (phon1125) -> own sound-alike trailer."""
    if not parts or any(not p or any(not w for w in p) for p in parts):
        raise ValueError('each dictionary part must contain nonempty words')
    if len(parts) != len(PARTS):
        raise ValueError('need %d word lists (main, abbreviations), got %d' % (len(PARTS), len(parts)))
    literal = codecs.lookup(cp).name in ('cp1125', 'cp866')
    pages = alphabet([w for p in parts for w in p])
    code = {c: (i << 2, n) for n, p in enumerate(pages) for i, c in enumerate(p) if c}

    keys, ids = [None], {}

    def intern(node):
        sid = 0
        for c, ch in sorted(node[1].items(), reverse=True):
            k = (c, ch[0], intern(ch), sid)
            if k not in ids:
                ids[k] = len(keys)
                keys.append(k)
            sid = ids[k]
        return sid

    tops, maxlen, maxcodes = [], [], []
    for words in parts:
        root = [0, {}]
        for w in words:
            n = root
            for ch in w:
                i, pg = code[ch]
                for c in [ESC << 2] * pg + [i]:
                    n = n[1].setdefault(c, [0, {}])
            n[0] = 1
        tops.append([(c, ch[0], intern(ch)) for c, ch in sorted(root[1].items())])
        maxlen.append(max(len(w) for w in words))
        maxcodes.append(max(sum(1 + code[c][1] for c in w) for w in words))

    est = [1] * len(keys)                            # inline size without sharing (capped)
    for sid in range(1, len(keys)):                  # children and tails are interned first
        c, end, child, nxt = keys[sid]
        est[sid] = min(1 << 20, 1 + est[child] + (est[nxt] if nxt else 0))

    e1 = Emitter(keys, SYM0, est)                  # pass 1: every pointer 3 bytes
    for top in tops:
        e1.part(top)
    e1.finish()
    lit = SYM0 - ((len(e1.out) - 1 >> 16) + 1)    # literal pointers: (sym0 - lit) * 64 KB
    t1n = min(T1MAX, lit - 5)                        # big trie: fewer 1-byte pointers, 5 pages of 2-byte
    if t1n < 2:
        raise ValueError('dictionary too large')
    near = [sid for sid, _ in e1.refs.most_common() if e1.addr[sid] < 0x10000]
    t1 = {sid: i + 1 for i, sid in enumerate(near[:t1n - 1])}
    t2 = {sid: i for i, sid in enumerate(near[t1n - 1:t1n - 1 + (lit - t1n) * 256])}

    def ptr(e, sid):
        if sid in t1:
            return bytes([t1[sid]])
        if sid in t2:
            j = t2[sid]
            return bytes([t1n + (j >> 8), j & 255])
        a = e.addr[sid]
        return bytes([lit + (a >> 16), a >> 8 & 255, a & 255])

    e = Emitter(keys, SYM0, est, e1.size, ptr, lit)   # pass 2: final sizes, addresses only shrink
    starts = [e.part(top) for top in tops]
    e.finish()
    trie = bytes(e.out).ljust(0x1001, b'\0')        # the engine refuses a trie cache of <= 1000h bytes
    language = LITERAL_LANGUAGE if literal else 1    # 1: US English rules
    pre = header(parts, literal)
    be2 = lambda v: bytes([v >> 8 & 255, v & 255])
    be3 = lambda v: bytes([v >> 16, v >> 8 & 255, v & 255])

    def put(o, b):
        pre[o:o + len(b)] = b

    chars = sorted(ord(c.encode(cp)) for c in code)
    base, last = chars[0], chars[-1]
    tab = bytearray(b'\xFF' * (last - base + 1))
    for c, (i, pg) in code.items():
        tab[c.encode(cp)[0] - base] = i | pg
    put(0x0A, be2(len(pre))); pre[0x2D], pre[0x2E] = base, len(tab)
    pre += tab + b'\xFF'  # sentinel for 5632h's inclusive upper-bound check
    if len(pre) & 1:
        pre += b'\xFF'
    put(0x38, be2(len(pre)))
    for p in pages:
        for i in range(PAGE):
            c = p[i] if i < len(p) and p[i] else ((pages[0][i] or '{') if i < ESC else '{')
            pre += b'\0' + c.encode(cp)
    put(0x0C, be2(len(pre)))
    tabs = [0] * t1n
    for sid, i in t1.items():
        tabs[i] = e.addr[sid]
    pre += b''.join(be2(v) for v in tabs)
    put(0x0E, be2(len(pre)))
    tabs = [0] * len(t2)
    for sid, j in t2.items():
        tabs[j] = e.addr[sid]
    pre += b''.join(be2(v) for v in tabs)
    pre[0x07], pre[0x08], pre[0x09], pre[0x17] = t1n, lit, SYM0, ESC << 2
    pre[0x35] = max(maxcodes)
    pre[0x36] = len(pages) - 1
    put(0x24, sum(len(set(p)) for p in parts).to_bytes(4, 'big'))
    put(0x28, be2(2 * t1n)); put(0x3A, be2(t1n))
    put(0x10, be2(2 * len(t2))); put(0x3C, be2(len(t2)))
    # Redundant input-map descriptor of the 7.51 layout.
    cm = pre[0x14] << 8 | pre[0x15]
    put(cm + 4, be2(base)); put(cm + 6, be2(len(tab))); put(cm + 8, pre[0x0A:0x0C])

    descs = [descriptor(kind, flags, language) for kind, flags in PARTS]
    # Type -> zero-based part index, FF for absent types, even padding.
    kinds = [d[1] for d in descs]
    put(0x3E, be2(len(pre)))
    index = bytearray([max(kinds)] + [0xFF] * max(kinds))
    for i, kind in enumerate(kinds):
        index[kind] = i
    pre += index
    if len(pre) & 1:
        pre += b'\0'
    put(0x2A, be2(len(pre)))
    d0 = len(pre) + 2 * len(descs)
    pre += b''.join(be2(d0 + 0x24 * i) for i in range(len(descs)))
    rl = d0 + 0x24 * len(descs) + 2 * len(descs)     # root lists follow the roots table
    for i, (d, (start, roots)) in enumerate(zip(descs, starts)):
        d[2:4] = be2(rl + (3 * PAGE + 3) * i)
        d[8:12] = b'\0' + be3(start)
        d[0x0C:0x0E] = be2(maxcodes[i])
        d[0x1E:0x20] = be2(maxlen[i])
        pre += d
    put(0x30, be2(len(pre)))
    pre += b''.join(be2(rl + (3 * PAGE + 3) * i) for i in range(len(descs)))
    for start, roots in starts:
        pre += b''.join(be3(r) for r in roots) + be3(start)   # start <= last root: end marker
    if len(pre) & 1:
        pre += b'\0'
    put(0x12, be2(len(pre)))
    put(0x45, be3(len(trie)))
    at = len(pre) + len(trie)
    put(0, be3(at))                              # end of trie, excluding phonetic trailer
    pre[0x21] = language                         # descriptive header language; runtime uses parts
    trailer = phonetic_trailer([w for p in parts for w in p], phonetic, cp, at) if phonetic else b''
    return bytes(pre) + trie + bytes(trailer)


def phonetic_trailer(words, key, cp, at):
    """Sound-alike groups for suggestions (WSSPL routine 92B2h computes the key of a word):
    for each key start (first two key chars, 0-padded) the word starts that have it -
    2 chars, 3 after a digraph (key.DIGRAPHS). Layout, offsets absolute in the file (LE):
    A bigrams (2 bytes each, 00 00 ends), B groups (3-byte entries, 0, even), C group offsets
    from B (LE words), D the last 6Ah bytes (directory at +4Ah: A B C, +5Eh: D; '##' at end)."""
    groups = {}
    for w in words:
        k = key.key(w)
        if k and not w[:1].isupper():                # capitalized starts are left out: the walk
            n = 3 if w[:2] in key.DIGRAPHS else 2    # tries them first and fills the short list
            g = groups.setdefault(k[:2].encode(cp).ljust(2, b'\0'), Counter())   # with names
            g[w[:n]] += 1                            # (typo search still finds names)
    bigrams = sorted(groups)
    data, offs = bytearray(), []
    for bg in bigrams:
        # The engine copies the entries' first letters into a 16-byte buffer right before the key,
        # skipping a repeat - but it compares sign-extended, so every letter >= 80h counts as new:
        # at most 15 entries, most frequent first.
        entries = [p for p, _ in sorted(groups[bg].items(), key=lambda pc: (-pc[1], pc[0]))[:15]]
        offs.append(len(data))
        data += b''.join(p.encode(cp).ljust(3, b'\0') for p in entries) + b'\0'
        if len(data) & 1:
            data += b'\0'
    offs.append(len(data))                           # the 00 00 bigram ends the linear search
    if len(data) > 0xFFFF:
        raise ValueError('phonetic groups over 64 KB')
    a = at
    b = a + 2 * len(offs)
    c = b + len(data)
    d = c + 2 * len(offs)
    tail = bytearray(0x68) + b'##'                  # dates/version text of the sample are not read
    for o, v in ((0x4A, a), (0x4E, b), (0x52, c), (0x5E, d)):
        tail[o:o + 4] = v.to_bytes(4, 'little')
    return (b''.join(bigrams) + b'\0\0' + data + b''.join(o.to_bytes(2, 'little') for o in offs)
            + bytes(tail))


def main(a):
    cp = 'latin-1'
    if '--cp' in a:
        i = a.index('--cp')
        cp = a[i + 1]
        del a[i:i + 2]
    parts = [open(p, encoding='utf-8').read().split() for p in a[1:]]
    if len(parts) == 1:
        parts.append(['xvi'])                        # second part must not be empty
    d = build(parts, cp)
    open(a[0], 'wb').write(d)
    print(len(d), 'bytes', file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
