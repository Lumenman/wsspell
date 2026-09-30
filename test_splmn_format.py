"""Checks of the SPLMN specification against original files and both original engines.

python -X utf8 test_splmn_format.py WS_DICT_DIR [--engines] [--report FILE.json]
--engines runs WSSPL033.OVR (6.00) and WSSPL001.OVR (7.51) in an emulator (needs unicorn).
"""
from pathlib import Path
import hashlib
import json
import sys
from splmn import Splmn



def metadata(s):
    f, be = s.f, s.be
    assert int.from_bytes(f[:3], 'big') == be(0x12) + len(s.data)
    assert be(0x28) == 2*f[7] == 2*be(0x3a)
    assert be(0x10) == 2*be(0x3c)
    assert be(0x0e) + be(0x10) == be(0x3e)
    idx = be(0x3e)
    assert f[idx] == max(s.types)
    for i, kind in enumerate(s.types):
        assert f[idx + kind] == i
        d = s.descs[i]
        assert be(d+2) == be(be(0x30)+2*i)
        assert int.from_bytes(f[d+8:d+12], 'big') + 1 == s.start(i)
    rows = []
    for i in s.lexical_parts():
        n, encoded, decoded = s.path_stats(i)
        assert encoded == be(s.descs[i]+12), (i, encoded, be(s.descs[i]+12))
        if f[s.descs[i]] == 0x24:
            assert decoded == be(s.descs[i]+0x1e)
        rows.append(dict(part=i, type=s.types[i], paths=n, max_codes=encoded, max_chars=decoded))
    assert sum(r['paths'] for r in rows) == int.from_bytes(f[0x24:0x28], 'big')
    assert max(r['max_codes'] for r in rows) == f[0x35]
    for i, kind in enumerate(s.types):
        if kind in (4, 5, 6):
            try:
                s.path_stats(i)
            except ValueError as e:
                assert 'cyclic' in str(e)
            else:
                raise AssertionError('expected a cyclic transducer')
    return rows


def engines(s, path, corpus):
    from emu2 import Ovl
    samples = ['a', 'abandon', 'bonjour', 'BonJour', 'hello', 'Hello', 'HELLO',
               'philosophie', 'strasse', 'Straße', 'école', 'ecole', 'qwzx']
    n = 0
    for overlay in ('WSSPL033.OVR', 'WSSPL001.OVR'):
        o = Ovl((corpus/overlay).read_bytes(), s.f, 'cp850')
        assert o.open() == 0, (path.name, overlay)
        base = o.ds*16
        input_at, output_at = (0x5bca, 0x566b) if o.old else (0x1ea2, 0x23e7)
        part_at = 0x61e if o.old else 0x360
        lookup = 0x490c if o.old else 0x58c0
        transform = 0x6f78 if o.old else 0x8086
        for word in samples:
            raw = word.encode('cp850')
            try:
                encoded = s.encode(raw)
            except ValueError:
                continue
            for i in s.lexical_parts():
                # Python lookup walks the graph directly, independent of root-index lookup.
                states = {s.start(i)}
                accepted = False
                for code in encoded:
                    arcs = [e for p in states for e in s.edges(p) if e[0] == code]
                    accepted = any(e[1] for e in arcs)
                    states = {e[2] for e in arcs}
                o.mu.mem_write(base+input_at, bytes(encoded)+b'\xff')
                o.w16(part_at, i)
                assert bool(o.call(lookup)) == accepted, (path.name, overlay, i, word)
                n += 1
            for i, kind in enumerate(s.types):
                if kind not in (4, 6):
                    continue
                expected = s.transduce(raw, i)
                o.mu.mem_write(base+input_at, bytes(encoded)+b'\xff')
                result = o.call(transform, i)
                if result:
                    codebytes = bytes(o.mu.mem_read(base+output_at, 103)).split(b'\xff')[0]
                    actual = s.text(codebytes).encode('latin1')
                    assert actual in expected, (path.name, overlay, i, word, actual, expected)
                else:
                    assert not expected, (path.name, overlay, i, word, expected)
                n += 1
    # Test type 5 with the engine's graph composition, including epsilon arcs.
    # Replace the main lexical graph in an in-memory fixture with one candidate.
    if 5 in s.types:
        lex, rule = s.types.index(1), s.types.index(5)
        raw = b'HELLO'
        expected = s.transduce(raw, rule, reverse=True)
        for candidate in (b'hello', b'Hello', b'qwzx'):
            codes = s.encode(candidate)
            f = bytearray(s.f)
            start = len(s.data)
            extra = bytes([s.sym0]) + bytes(s.sym0+c+(i==len(codes)-1) for i,c in enumerate(codes)) + b'\0'
            f.extend(extra)
            f[0x45:0x48] = (start+len(extra)).to_bytes(3,'big')
            f[:3] = len(f).to_bytes(3,'big')
            q = s.be(s.be(0x30)+2*lex)
            f[q:q+3*s.page] = b'\0'*(3*s.page)
            f[q+3*(codes[0]>>2):q+3*(codes[0]>>2)+3] = (start+1).to_bytes(3,'big')
            f[q+3*s.page:q+3*s.page+3] = start.to_bytes(3,'big')
            d = s.descs[lex]
            f[d+8:d+12] = start.to_bytes(4,'big')
            for overlay in ('WSSPL033.OVR','WSSPL001.OVR'):
                o = Ovl((corpus/overlay).read_bytes(), bytes(f), 'cp850')
                assert o.open() == 0
                base = o.ds*16
                mode, index, table, keybuf, fn = ((0x531a,0x906,0x53a,0x566b,0x7258)
                                                if o.old else (0x1d32,0x642,0x27c,0x23e7,0x83ec))
                o.w16(mode,4);o.w16(index,0)
                o.mu.mem_write(base+table,bytes([lex,255]))
                o.mu.mem_write(base+keybuf,bytes(s.encode(raw))+b'\xff')
                assert bool(o.call(fn,rule)) == (candidate in expected), (path.name,overlay,candidate)
                n += 1
    return n


def main():
    corpus = Path(sys.argv[1])
    report = []
    for p in sorted(corpus.glob('SPLMN*')):
        if p.suffix not in ('.DCT', '.LGL'):
            continue
        s = Splmn(p)
        row = dict(file=p.name, bytes=len(s.f), sha256=hashlib.sha256(s.f).hexdigest(), parts=metadata(s))
        if '--engines' in sys.argv and s.f[0x21] != 0x7F:   # not our own cp1125 builds
            row['engine_checks'] = engines(s, p, corpus)
        report.append(row)
        print('OK',p.name,'paths',sum(r['paths'] for r in row['parts']), 'checks',row.get('engine_checks',0),flush=True)
    if '--report' in sys.argv:
        Path(sys.argv[sys.argv.index('--report')+1]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
