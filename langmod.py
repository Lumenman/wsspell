"""Install a cp1125 spelling module (e.g. Ukrainian 380, Russian 007) next to the English one.

  python -X utf8 langmod.py EXE [EXE ...] --forms uk_forms.txt --code 380 --name Ukraine
  python -X utf8 langmod.py EXE [EXE ...] --forms ru_forms.txt --code 007 --name Russia
  options: --dict DIR (default: DICT next to the first EXE), --default (make it the default language)

- DICT\\SPLMNccc.DCT: main dictionary built from the forms (vesum.py, opcorpora.py), cp1125;
- DICT\\WSSPLccc.OVR: the speller overlay with cp1125 case tables (wsspl.py, made from DICT\\WSSPL001.OVR);
- each EXE (a cp1125 WordStar build) gets a language table entry 'name ccc'
  (PATCH.TXT lngtbl, 20-byte entries, free ones are 16 spaces, 00h, '000'); --default sets lngcod.
In a document `.la ccc` switches the spelling language, `.la 001` back to English.
The first run keeps the EXE as .BAK; re-running changes nothing.
"""
from pathlib import Path
import sys
import phon1125
import splmnbuild
import wsspl

FREE = b' ' * 16 + b'\x00000'


def patch_exe(exe, code, name, default):
    entry = name.encode('ascii').ljust(16)[:16] + b'\x1f' + code.encode('ascii')
    d = bytearray(exe.read_bytes())
    first = d.find(b'United States   \x1f001')
    assert first > 0 and d.count(b'United States   \x1f001') == 1, exe
    n = d[first - 1]                                  # lngtbl count byte precedes the entries
    codes = [bytes(d[first + 20 * i + 17:first + 20 * i + 20]) for i in range(n)]
    if entry[17:] not in codes:
        free = first + 20 * n
        assert d[free:free + 20] == FREE, 'no free lngtbl slot in %s' % exe
        d[free:free + 20] = entry
        d[first - 1] = n + 1
    if default:
        d[first - 3:first - 1] = int(code).to_bytes(2, 'little')   # dw lngcod before the count
    if d != exe.read_bytes():
        backup = exe.with_suffix('.BAK')
        if not backup.exists():
            backup.write_bytes(exe.read_bytes())
        exe.write_bytes(d)
        print('patched', exe, '(backup', backup.name + ')')


def install(dic, forms, code):
    words = open(forms, encoding='utf-8').read().split()
    dct = splmnbuild.build([words, ['обл.']], 'cp1125', phon1125)
    (dic / ('SPLMN%s.DCT' % code)).write_bytes(dct)
    (dic / ('WSSPL%s.OVR' % code)).write_bytes(wsspl.cp1125_overlay((dic / 'WSSPL001.OVR').read_bytes()))
    print('wrote', dic / ('SPLMN%s.DCT' % code), dic / ('WSSPL%s.OVR' % code))


def main(a):
    opt = {}
    for k in ('--forms', '--code', '--name', '--dict'):
        if k in a:
            i = a.index(k)
            opt[k] = a[i + 1]
            del a[i:i + 2]
    default = '--default' in a
    exes = [Path(x) for x in a if x != '--default']
    code = opt['--code']
    assert len(code) == 3 and code.isdigit(), code
    install(Path(opt.get('--dict') or exes[0].parent / 'DICT'), opt['--forms'], code)
    for exe in exes:
        patch_exe(exe, code, opt['--name'], default)


if __name__ == '__main__':
    main(sys.argv[1:])
