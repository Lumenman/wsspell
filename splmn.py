"""Read WordStar SPLMN dictionaries (WSSPL 6.00 and 7.51).

Usage: python splmn.py SPLMN001.DCT > words.txt
Words are emitted in the dictionary's own byte encoding. The default selects lexical
parts (1, 2, 3, 31..36); cyclic transducers (4, 5, 6, 16) are not word lists.
See SPLMN_FORMAT.md for the binary specification.
"""
import sys
from functools import lru_cache
from pathlib import Path

sys.setrecursionlimit(10000)


class Splmn:
    def __init__(s, path):
        f = s.f = Path(path).read_bytes()
        if len(f) < 0x48:
            raise ValueError('truncated SPLMN header')
        s.be = lambda o: f[o] << 8 | f[o + 1]
        s.page, s.t1n, s.lit, s.sym0, s.esc = f[4], f[7], f[8], f[9], f[0x17]
        s.t1, s.t2, s.chars = s.be(0x0C), s.be(0x0E), s.be(0x38) + 1
        s.data = f[s.be(0x12):s.be(0x12) + int.from_bytes(f[0x45:0x48], 'big')]
        s.dense, s.eps = f[0x23], f[0x34]
        s.descs = [s.be(s.be(0x2A) + 2*i) for i in range(f[0x2F])]
        s.types = [f[d+1] for d in s.descs]
        s._edge_cache, s._skip_cache = {}, {}
        s.mincode = 0

    def pointer(s, p):
        d, b = s.data, s.data[p]
        if b < s.t1n:
            return s.be(s.t1 + 2 * b), 1
        if b < s.lit:
            return s.be(s.t2 + 2 * ((b - s.t1n) << 8 | d[p + 1])), 2
        return (b - s.lit) << 16 | d[p + 1] << 8 | d[p + 2], 3

    def text(s, codes, mincode=0):
        out, n = [], 0
        for c in codes:
            if c < mincode:
                n = 0
            elif c == s.esc:
                n += 1
            else:
                out.append(chr(s.f[s.chars + 2 * ((c >> 2) + s.page * n)]))
                n = 0
        return ''.join(out)

    def siblings(s, p, pre, out):
        """Walk the sibling list at p; return the position after it."""
        while True:
            b = s.data[p]
            if b == 0:
                return p + 1
            if b < s.sym0:
                t, n = s.pointer(p)
                s.siblings(t, pre, out)
                return p + n
            p = s.node(p, pre, out)
            if not (b - s.sym0) & 2:
                return p

    def node(s, p, pre, out):
        c = s.data[p] - s.sym0
        if c & 0xFC == s.dense:
            for _, _, _, q in s.edges(p):
                s.node(q, pre, out)
            return s.skip(p + 1)
        w = pre + [c & 0xFC]
        if len(w) > 102:
            raise ValueError('cyclic or overlong lexical path at data %X' % p)
        if c & 1:
            out.append(s.text(w, s.mincode))
        return s.siblings(p + 1, w, out)

    def lexical_parts(s):
        return [i for i, kind in enumerate(s.types) if kind in (1, 2, 3, 31, 32, 33, 34, 35, 36)]

    def start(s, part):
        """First list after the dummy root; last root-index entry points at the dummy."""
        q = s.be(s.be(0x30) + 2*part) + 3*s.page
        return int.from_bytes(s.f[q:q+3], 'big') + 1

    def resolve(s, p):
        b = s.data[p]
        if 0 < b < s.sym0:
            p = s.pointer(p)[0]
        if not 0 <= p < len(s.data) or 0 < s.data[p] < s.sym0:
            raise ValueError('invalid graph pointer at %X' % p)
        return p

    def skip(s, p):
        """Skip an inline list without following references (engine 56B8h)."""
        if p in s._skip_cache:
            return s._skip_cache[p]
        start, depth = p, 1
        while depth:
            b = s.data[p]
            if b >= s.sym0:
                depth += bool(b & 2)
                p += 1
            else:
                p += 1 if b < s.t1n else 2 if b < s.lit else 3
                depth -= 1
        s._skip_cache[start] = p
        return p

    def edges(s, p):
        """Logical arcs: (masked code, terminal bit, child list, physical node).

        Expands the dense 4-byte slot table; preserves graph sharing and cycles.
        A pointer may also replace the remaining siblings, not just all children.
        """
        p = s.resolve(p)
        if p in s._edge_cache:
            return s._edge_cache[p]
        start, out, seen = p, [], set()
        while s.data[p]:
            p = s.resolve(p)
            if p in seen:
                raise ValueError('cycle in sibling list at %X' % p)
            seen.add(p)
            c = s.data[p] - s.sym0
            if c & 0xFC == s.dense:
                base = s.resolve(p + 1)
                for k in range(s.page):
                    q = base + 4*k
                    b = s.data[q] - s.sym0
                    if b >= 0 and b & 0xFC == 4*k and 4*k != s.dense:
                        out.append((b & 0xFC, b & 1, q + 1, q))
            else:
                out.append((c & 0xFC, c & 1, p + 1, p))
            if not c & 2:
                break
            p = s.skip(p + 1)
        s._edge_cache[start] = tuple(out)
        return tuple(out)

    def encode(s, word):
        """Encode raw dictionary bytes; no case folding or language rules."""
        out = []
        for c in word:
            if not s.f[0x2D] <= c < s.f[0x2D] + s.f[0x2E]:
                raise ValueError('character outside input map: %02X' % c)
            b = s.f[s.be(0x0A) + c - s.f[0x2D]]
            if b >= 0xFC:
                raise ValueError('unmapped character: %02X' % c)
            out.extend([s.esc] * (b & 3))
            out.append(b & 0xFC)
        return tuple(out)

    def transduce(s, word, part, *, reverse=False, max_codes=102, max_states=100000):
        """Enumerate a transducer relation for raw bytes. Returns a set of bytes.

        Each arc is stored as two nodes: output, input. Epsilon consumes/emits
        nothing. reverse swaps the lanes. This is the relation, not the engine's
        preferred first path or its surrounding language-specific normalization.
        Limits fail explicitly rather than silently returning a truncated result.
        """
        if s.types[part] not in (4, 5, 6, 16):
            raise ValueError('part is not a transducer')
        inp = s.encode(word)
        stack, seen, out = [(s.start(part), 0, ())], set(), set()
        while stack:
            state, i, pre = stack.pop()
            state = s.resolve(state)
            if (state, i, pre) in seen:
                continue
            seen.add((state, i, pre))
            if len(seen) > max_states:
                raise ValueError('transducer state limit exceeded')
            for a, _, p, _ in s.edges(state):
                for b, terminal, q, _ in s.edges(p):
                    emit, take = (b, a) if reverse else (a, b)
                    if take == s.eps:
                        j = i
                    elif i < len(inp) and take == inp[i]:
                        j = i + 1
                    else:
                        continue
                    w = pre if emit == s.eps else pre + (emit,)
                    if len(w) > max_codes:
                        raise ValueError('transducer output limit exceeded')
                    if terminal and j == len(inp):
                        out.add(s.text(w).encode('latin1'))
                    stack.append((q, j, w))
        return out

    def path_stats(s, part):
        """Count accepting paths and maximum encoded/decoded lengths in a DAG.

        Cyclic transducers deliberately raise ValueError. Counts are per part;
        adding overlapping lexical parts does not count distinct surface words.
        """
        active = set()
        @lru_cache(None)
        def count(p):
            p = s.resolve(p)
            if p in active:
                raise ValueError('cyclic graph; no finite word count')
            active.add(p)
            n = codes = chars = 0
            for c, end, q, _ in s.edges(p):
                m, a, b = count(q)
                n += m + end
                if m or end:
                    codes = max(codes, 1 + a)
                    chars = max(chars, (c not in (s.esc, s.eps)) + b)
            active.remove(p)
            return n, codes, chars
        return count(s.start(part))

    def words(s, parts=None):
        out = []
        for i in s.lexical_parts() if parts is None else parts:
            if s.types[i] not in (1, 2, 3, 31, 32, 33, 34, 35, 36):
                raise ValueError('part %d is type %d, not a word list; use transduce' % (i, s.types[i]))
            v = s.f[s.descs[i] + 0x15]
            s.mincode = v if 0 < v < 0xF8 else (4 if s.eps < 0xF8 else 0)
            q = s.be(s.be(0x30) + 2 * i)
            for k in range(s.page):
                o = s.f[q + 3 * k] << 16 | s.f[q + 3 * k + 1] << 8 | s.f[q + 3 * k + 2]
                if o:
                    s.node(o, [], out)
        return out


if __name__ == '__main__':
    w = Splmn(sys.argv[1]).words()
    print(len(w), 'words', file=sys.stderr)
    sys.stdout.buffer.write('\n'.join(w).encode('latin-1') + b'\n')
