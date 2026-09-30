"""Regression checks for dictionary construction and language selection.

python -X utf8 test_splmn.py [WS_DICT_DIR]
Without WS_DICT_DIR only the builder is checked. With the DICT directory of WordStar 7.0D
(original SPLMN*.DCT and WSSPL*.OVR, see README) also the English round trip, the other
languages and the original 7.51 engine run in an emulator (needs unicorn and keystone-engine).
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys

import opcorpora
import phon1125
import splmnbuild
from splmn import Splmn
from test_splmn_format import metadata

WORDS = ['объединённое', 'съезд', 'кот', 'привет', 'ёлка', 'ехай', 'щас', 'ихний', 'ґава', 'їжак', "п'ять", 'Київ', 'РФ']


def main(dic):
    assert 'Ъ' in {c for page in splmnbuild.alphabet(['абвгдежзийклмнопрстуфхцчшщъ']) for c in page}
    # Small alphabets used to index beyond page 0. Check both actual decoded data and metadata.
    with TemporaryDirectory() as tmp:
        out = Path(tmp) / 'test.dct'
        for cp, parts in [('cp1125', [['кот'], ['обл.']]),
                          ('cp1125', [WORDS, ['обл.']]),
                          ('cp866', [['ёжик', 'съезд'], ['обл.']]),
                          ('ascii', [['a'], ['b']])]:
            data = splmnbuild.build(parts, cp, phon1125 if cp == 'cp1125' else None)
            out.write_bytes(data)
            s = Splmn(out)
            for i, words in enumerate(parts):
                assert set(s.words([i])) == {w.encode(cp).decode('latin1') for w in words}
                desc = s.be(s.be(0x2a) + 2*i)
                expected = 0x7f if cp.startswith('cp') else 1
                assert data[desc+0x12] == data[0x21] == expected
            assert int.from_bytes(data[:3], 'big') == s.be(0x12) + int.from_bytes(data[0x45:0x48], 'big')
            metadata(s)
            assert s.words([]) == []
            assert data[s.be(0x0a) + data[0x2e]] == 0xff
            end = int.from_bytes(data[:3], 'big')
            if cp == 'cp1125':
                tail = data[-0x6a:]
                a,b,c,d = [int.from_bytes(tail[o:o+4], 'little') for o in (0x4a,0x4e,0x52,0x5e)]
                assert end == a < b < c < d == len(data)-0x6a and tail[-2:] == b'##'
            else:
                assert end == len(data)              # no phonetic trailer
        try:
            splmnbuild.build([[], ['x']], 'ascii')
        except ValueError:
            pass
        else:
            raise AssertionError('empty part accepted')

        def entry(word, *tags):
            return word, SimpleNamespace(grammemes=set(tags))
        forms = opcorpora.collect([entry('ошипка', 'Erro'), entry('здрасьте', 'Infr', 'Dist'),
                                  entry('ехай', 'Infr'), entry('щас', 'Slng'), entry('ихний'),
                                  entry('омоним', 'Erro'), entry('омоним'), entry('ёлка'),
                                  entry('ёршов', 'Surn'), entry('123'), entry('мвд', 'Abbr')])
        assert forms == {'здрасьте', 'ехай', 'щас', 'ихний', 'омоним', 'ёлка', 'елка', 'Ёршов', 'Ершов', 'МВД'}
        if not dic:
            print('OK: small alphabets, metadata, Russian filtering (no WordStar files given)')
            return

        # English remains the control: same words, same per-part language IDs.
        en = Splmn(dic / 'SPLMN001.DCT')
        parts = [en.words([i]) for i in range(en.f[0x2f])]
        out.write_bytes(splmnbuild.build(parts, 'latin1'))
        rebuilt = Splmn(out)
        assert all(set(rebuilt.words([i])) == set(words) for i,words in enumerate(parts))

    # The other installed languages share one older engine; IDs live in each DCT.
    import unexepack
    old_images = set()
    for country, language in [('002',15), ('033',3), ('034',4), ('039',6), ('044',2), ('049',5), ('052',17)]:
        path = dic / ('SPLMN'+country+'.DCT')
        if not path.exists():
            continue
        old = Splmn(path)
        assert old.f[0x21] == language
        assert int.from_bytes(old.f[:3], 'big') == len(old.f)
        for i in range(old.f[0x2f]):
            desc = old.be(old.be(0x2a)+2*i)
            assert old.f[desc] == 0x20 and old.f[desc+0x12] == language
        ovr = path.with_name('WSSPL'+country+'.OVR').read_bytes()
        old_images.add(unexepack.unpack(ovr)[0])
    assert len(old_images) <= 1

    # Run the actual overlay, not a Python mirror, for case and English suffix behavior.
    import wsspl
    from emu2 import Ovl, DS, H
    from unicorn.x86_const import UC_X86_REG_IP
    ovr = (dic / 'WSSPL001.OVR').read_bytes()
    data = splmnbuild.build([WORDS, ['обл.']], 'cp1125', phon1125)
    for dct, overlay, language, word, stripped in [
        ((dic / 'SPLMN001.DCT').read_bytes(), ovr, 1, "hello's", 'hello'),
        (data, wsspl.cp1125_overlay(ovr), 0x7f, "привет's", "привет's")]:
        engine = Ovl(overlay, dct)
        engine.call(0x910a, 0)
        assert engine.call(0x4098, H) == 0
        assert int.from_bytes(engine.mu.mem_read(DS*16+0x1e0, 2), 'little') == language
        assert engine.mu.mem_read(DS*16+0x7e0, 1)[0] == 1
        engine.w16(0x26bc, 0x4078)  # no-op cancellation callback (image 4088h, CS starts at 10h)
        engine.mu.mem_write(DS*16+0x6000, word.encode('cp1125')+b'\0')
        engine.call(0x3cea, 0x6000)
        result = engine.call(0x1ffa, 0x6000)
        assert result == (ord('s') if language == 1 else 0)
        assert engine.cstr(0x6000) == stripped
        if language == 0x7f:
            # 7EFAh uses an exclusive bound, unlike 5632h. The last input byte
            # (yo/i-diaeresis in Cyrillic dictionaries) must survive both paths.
            last = data[0x2d] + data[0x2e] - 1
            engine.mu.mem_write(DS*16+0x6000, bytes([last, 0]))
            count = engine.call(0x7efa, 0x6000, DS, 0x6100)
            assert count > 0
            assert engine.mu.mem_read(DS*16+0x6100, 1)[0] != 0xff
            engine.w16(0x98, 0x6100)
            assert engine.call(0x5632, last + 1) == 0
            for word in WORDS + ['ОБЪЕДИНЁННОЕ', 'ЇЖАК', 'СЪЕЗД', 'КОТ', 'ЁЛКА', 'ПРИВЕТ', "П'ЯТЬ", 'ҐАВА']:
                engine.mu.mem_write(DS*16+0x6000, word.encode('cp1125')+b'\0')
                assert engine.call(0x3d5c, 0x6000, 0x1d00) == 1, word
                assert engine.mu.reg_read(UC_X86_REG_IP) == 0xfff0
    print('OK: small alphabets, metadata, full English round trip, Russian filtering, original engine')


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
