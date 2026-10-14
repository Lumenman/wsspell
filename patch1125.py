"""Patch WordStar 7 WS.EXE codepage tables (User Area, see PATCH.TXT of WordStar) from cp437 to cp1125 (or cp866).

Usage: python patch1125.py [--cp 866] EXE [EXE ...]   (the first run keeps a copy NAME.437)
       python patch1125.py --listing EXE    (writes PATCH1125.TXT/.LST in the style of PATCH.TXT)

The cp437 tables are read from NAME.437 if it exists, otherwise from the EXE itself.

Tables are located by their cp437 contents (in WS.EXE: PATCH.TXT address + E00h) and must occur
exactly once; an already patched file is recognised and left unchanged. codepg (437) is not touched.
  lglchr  bit table: letter within a word (word count, spelling, hyphenation, ^T)
  movchr  bit table: characters ^A/^F skip as part of a word
  upcase / lowcase   case maps (^K" ^K' ^K.)
  colate  sort weights (^KZ block sort, directory sort, merge compares), case-insensitive
"""
import os
import shutil
import sys

REF_OFS = {'lglchr': (0x28A3, 36), 'movchr': (0x28C7, 36), 'upcase': (0x28EB, 256),
           'lowcase': (0x29EB, 256), 'colate': (0x2AEB, 256)}

# alphabet per code page: capital codes and sort order; lower = +20h (А-П) / +50h (Р-Я) / +1 (F0h-F9h)
ALPHABETS = {'cp1125': ([0xF0, 0xF2, 0xF4, 0xF6, 0xF8], 'АБВГҐДЕЁЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'),   # Ukrainian + Russian
             'cp866': ([0xF0, 0xF2, 0xF4, 0xF6], 'АБВГДЕЁЄЖЗИЇЙКЛМНОПРСТУЎФХЦЧШЩЪЫЬЭЮЯ')}       # Russian + Є Ї Ў
CP = 'cp1125'


def alphabet():
    upper = list(range(0x80, 0xA0)) + ALPHABETS[CP][0]
    return {u: (u + 0x20 if u < 0x90 else u + 0x50) if u < 0xA0 else u + 1 for u in upper}, ALPHABETS[CP][1]


def bits(codes):
    b = bytearray(32)
    for c in codes:
        b[c >> 3] |= 0x80 >> (c & 7)
    return b


def cp1125_tables(ref):
    t = {}
    LOWER, ORDER = alphabet()
    letters = set(LOWER) | set(LOWER.values())
    lgl = bytearray(ref['lglchr'])
    lgl[16:32] = bits(letters)[16:32]                     # 80h-FFh; 00h-7Fh and extended codes as is
    t['lglchr'] = bytes(lgl)
    mov = bytearray(ref['movchr'])
    mov[16:32] = bits([c for c in range(0x80, 0x100) if c != 0xFF])[16:32]   # all but nbsp
    t['movchr'] = bytes(mov)
    up, low = bytearray(ref['upcase'][:128] + bytes(range(128, 256))), bytearray(ref['lowcase'][:128] + bytes(range(128, 256)))
    for u, l in LOWER.items():
        up[l], low[u] = u, l
    t['upcase'], t['lowcase'] = bytes(up), bytes(low)
    # sort keys on the cp437 weight scale, then renumbered densely (ties stay ties)
    w = ref['colate']
    key = {c: w[c] for c in range(0x80)}
    key.update({c: w[c] for c in range(0xB0, 0xE0)})      # box drawing is the same as in cp437
    for i, ch in enumerate(ORDER):
        u = ch.encode(CP)[0]
        key[u] = key[LOWER[u]] = w[ord('Z')] + (i + 1) / 100   # after Z, before Greek/controls
    key.update({0xF8: w[0xF8], 0xF9: w[0xF9]} if CP == 'cp866' else {})   # ° ∙ as in cp437
    key.update({0xFA: w[0xFA], 0xFB: w[0xFB], 0xFC: w[ord('#')] + .5, 0xFD: w[ord('$')] + .5,
                0xFE: w[0xFE], 0xFF: w[ord(' ')]})        # · √ № ¤ ■ nbsp
    rank = {k: n for n, k in enumerate(sorted(set(key.values())))}
    t['colate'] = bytes(rank[key[c]] for c in range(256))
    return t


def patch(path, ref, new):
    data = bytearray(open(path, 'rb').read())
    changed = False
    for name in REF_OFS:
        old, nw = ref[name], new[name]
        n_old, n_new = data.count(old), data.count(nw)
        if n_old == 1 and n_new == 0:
            i = data.find(old)
            data[i:i + len(old)] = nw
            changed = True
            print('  %-7s %05Xh patched' % (name, i))
        elif n_old == 0 and n_new == 1:
            print('  %-7s %05Xh already %s' % (name, data.find(nw), CP))
        else:
            sys.exit('%s: %s found %d times (cp437), %d times (%s) -- not patched' % (path, name, n_old, n_new, CP))
    if changed:
        if not os.path.exists(path[:-4] + '.437'):
            shutil.copy2(path, path[:-4] + '.437')
        open(path, 'wb').write(data)


def selftest(ref, t):
    enc = lambda s: s.encode(CP)
    up, low = t['upcase'], t['lowcase']
    s = alphabet()[1].lower()
    assert enc(s).translate(up) == enc(s.upper()) and enc(s.upper()).translate(low) == enc(s)
    assert b'Az09 \xb0\xff'.translate(up) == b'AZ09 \xb0\xff' and b'Az'.translate(low) == b'az'
    is_bit = lambda tb, c: tb[c >> 3] & (0x80 >> (c & 7))
    for c in range(256):
        letter = chr(c).isalpha() if c < 128 else enc(s + s.upper()).count(bytes([c])) > 0
        assert bool(is_bit(t['lglchr'], c)) == letter, hex(c)
        assert bool(is_bit(t['movchr'], c)) == bool(is_bit(ref['movchr'], c)) or c >= 128
    col = t['colate']
    k = lambda w: [col[b] for b in enc(w)]
    assert sorted(s, key=k) == list(s) and col[0xF0] == col[0xF1]
    if CP != 'cp1125':
        return
    words = ['Азія', 'баба', 'Бджола', 'ґава', 'Гуска', 'єнот', 'Ельф', 'ёж', 'їжак', 'Ірпінь', 'йод', 'Иван', 'ящик', 'Zebra', 'apple']
    assert sorted(words, key=k) == ['apple', 'Zebra', 'Азія', 'баба', 'Бджола', 'Гуска', 'ґава', 'Ельф',
                                    'ёж', 'єнот', 'Иван', 'Ірпінь', 'їжак', 'йод', 'ящик'], sorted(words, key=k)
    assert col[0x41] == col[0x61] and col[0x80] == col[0xA0] and col[0xF4] == col[0xF5]
    assert all(col[a] < col[b] for a, b in [(0x20, 0x30), (0x39, 0x41), (0x5A, 0x80), (0x9F, 0xB0), (0xB0, 0xDF)])


def main():
    global CP
    if sys.argv[1:2] == ['--cp']:
        CP = 'cp' + sys.argv[2]
        del sys.argv[1:3]
    listing_only = sys.argv[1:2] == ['--listing']
    paths = sys.argv[1 + listing_only:]
    if not paths:
        sys.exit(__doc__)
    for path in paths:
        backup = path[:-4] + '.437'
        r = open(backup if os.path.exists(backup) else path, 'rb').read()
        ref = {n: r[o:o + l] for n, (o, l) in REF_OFS.items()}
        if ref['upcase'][0x81] != 0x9A:
            sys.exit('%s: no cp437 tables (patched already, and no .437 copy?)' % path)
        new = cp1125_tables(ref)
        selftest(ref, new)
        if listing_only:
            for ext in ('TXT', 'LST'):
                out = 'PATCH1125.' + ext
                open(out, 'wb').write(listing(new).replace('\n', '\r\n').encode('cp1125') + b'\x1a')
                print(out)
            return
        print(path)
        patch(path, ref, new)


HEADER = '''         WordStar cp1125 (Ukrainian/Russian) Code Page Tables

Look at this file in WordStar's nondocument mode. It is written in
code page 1125 and follows WS\\PATCH.TXT: the same labels and User
Area addresses, with an "if CDPG eq 1125" block in place of the
"if CDPG eq 437" one. Only these five tables change; codepg stays 437.

  lglchr  letters within a word (^T, word count, spelling, hyphenation)
  movchr  characters ^A/^F treat as part of a word
  upcase  uppercasing (^K" and ^K.)
  locase  lowercasing (^K')
  colate  sort order for ^KZ, directory sort and merge compares:
          Latin, then А Б В Г Ґ Д Е Ё Є Ж З И І Ї Й К ... Щ Ъ Ы Ь Э Ю Я,
          upper and lower case equal; № sorts next to #, nbsp as space.

Make a backup copy of WS.EXE first (WS.437), then either

  - WSCHANGE menu E (Patching), then = (Enter User Area address):
    type a label (e.g. "upcase") or its address and enter the bytes
    below, or
  - python patch1125.py WS.EXE  -- writes all five tables, checks
    the old cp437 bytes, keeps WS.437; a second run changes nothing
    (https://github.com/Lumenman/ws7spell).

In the WS.EXE file each table lies at its User Area address + E00h
(lglchr 28A3h, movchr 28C7h, upcase 28EBh, locase 29EBh, colate 2AEBh).
Checked in WordStar 7.0D under DOSBox: ^K' ^K" ^K. ^T ^F ^KZ on
Ukrainian and Russian text. A cp1125 keyboard driver and screen font
are needed separately.

'''


def listing(t):
    out = [HEADER]

    def bitrows(name, addr):
        out.append(' %04X\t\t\t\t%s\tlabel\tbyte\n\t\t\t\t\n\t\t\t\tif CDPG eq 1125\n'
                   '\t\t\t\t\t; For Code Page 1125\n\t\t\t\t\n\t\t\t\t\t;\t01234567  89ABCDEF\n' % (addr, name))
        for i in range(0, 36, 2):
            a, b = t[name][i], t[name][i + 1]
            rng = ('Codes %02XH to %02XH' % (i * 8, i * 8 + 15) if i < 32 else
                   'Extended codes %02XH to %02XH' % ((i - 32) * 8, (i - 32) * 8 + 15))
            out.append(' %04X  %02X %02X\t\t\t\tdb\t%sb,%sb\t; %s\n' % (addr + i, a, b, format(a, '08b'), format(b, '08b'), rng))
        out.append('\t\t\t\tendif\n\n\n\n')

    def bytetable(name, label, addr, title):
        out.append(' %04X\t\t\t\t%s\tlabel\tbyte\n\t\t\t\t\n\t\t\t\tif CDPG eq 1125\n'
                   '\t\t\t\t\t; %s for Code Page 1125\n\t\t\t\t\n'
                   '\t\t\t\t\t;\t  0    1    2    3    4    5    6    7\n' % (addr, label, title))
        d = t[name]
        for i in range(0, 256, 8):
            row = d[i:i + 8]
            chars = ''.join(bytes([c]).decode('cp1125') if 0x20 <= c < 0xFF and c != 0x7F else '.' for c in range(i, i + 8))
            out.append(' %04X  %s\t\tdb\t%s\t; %2X .. %2X  %s\n       %s\t\t\t\n' % (
                addr + i, ' '.join('%02X' % c for c in row[:6]), ','.join('0%02Xh' % c for c in row),
                i, i + 7, chars, ' '.join('%02X' % c for c in row[6:])))
        out.append('\t\t\t\tendif\n\n\n\n')

    ua = lambda name: REF_OFS[name][0] - 0xE00
    bitrows('lglchr', ua('lglchr'))
    bitrows('movchr', ua('movchr'))
    bytetable('upcase', 'upcase', ua('upcase'), 'Uppercasing table')
    bytetable('lowcase', 'locase', ua('lowcase'), 'Lowercasing table')
    bytetable('colate', 'colate', ua('colate'), 'Collating table')
    return ''.join(out)


if __name__ == '__main__':
    main()
