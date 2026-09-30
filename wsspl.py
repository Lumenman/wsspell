"""Adapt the WordStar 7 speller overlay WSSPL001.OVR (engine 7.51) to cp1125 Cyrillic.

  python wsspl.py WSSPL001.OVR OUT.OVR [--no-phonetic]

The EXEPACKed image is unpacked, patched and repacked to the original length. Only the
original overlay is accepted (SHA-256 below); it is not distributed with this project.
"""
import hashlib
import sys
import phon1125
import unexepack

ORIGINAL = 'ba9ed78b01f003130b981f43ad8a3e0e01cad37bf3075337bd7b83a1fdbb3e82'   # WSSPL001.OVR, 7.51


def check(ovr):
    if hashlib.sha256(ovr).hexdigest() != ORIGINAL:
        raise ValueError('not the original WSSPL001.OVR of WordStar 7.0D (SHA-256 mismatch)')


def cp1125_image(ovr):
    """The unpacked overlay image with the cp1125 table patches:
    - Punctuation: the American module treats A8/AD/AE as opening, A9/AF as closing
      punctuation; in cp1125 those are и/н/о/й/п, blanked (table sizes unchanged).
    - Case for bytes >= 80h (cp850 in the original), DS offsets: tolower 5C4h+c,
      toupper 644h+c (0 = unchanged), isupper/islower bitmaps 744h/764h, letter folding 53Eh+c.
      The repacked stream must fit the original length, so the margin is small."""
    check(ovr)
    img = bytearray(unexepack.unpack(ovr)[0])
    for before, after in [
        (b'-\' "#(*[{}\xa8\xad\xae\xb8', b'-\' "#(*[{}   \xb8'),
        (b'-\'. !"%&)*+,/:;<=>?@\\]_\x60{|}\xa9\xaf',
         b'-\'. !"%&)*+,/:;<=>?@\\]_\x60{|}  '),
    ]:
        assert len(before) == len(after) and img.count(before) == 1
        img = img.replace(before, after)
    ds = 0x9E40
    for c in range(0x80, 0x100):
        ch = bytes([c]).decode('cp1125')
        lo, up = ch.lower().encode('cp1125')[0], ch.upper().encode('cp1125')[0]
        img[ds + 0x5C4 + c] = lo if lo != c else 0
        img[ds + 0x644 + c] = up if up != c else 0
        img[ds + 0x53E + c] = lo if ch.isalpha() else 0x20
        for bitmap, yes in ((0x744, ch.isupper()), (0x764, ch.islower())):
            o = ds + bitmap + (c >> 3)
            img[o] = img[o] | 1 << (c & 7) if yes else img[o] & ~(1 << (c & 7))
    return bytes(img)


def cp1125_overlay(ovr, phonetic=True):
    """ovr: bytes of the original WSSPL001.OVR; phonetic: Cyrillic sound-alike key (phon1125.py)
    instead of the English one."""
    img = cp1125_image(ovr)
    if phonetic:
        img = phon1125.patch(img)
    return unexepack.repack(ovr, img)


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    with open(a[0], 'rb') as f:
        out = cp1125_overlay(f.read(), '--no-phonetic' not in a)
    with open(a[1], 'wb') as f:
        f.write(out)
