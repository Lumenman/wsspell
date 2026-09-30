"""Cyrillic (cp1125) phonetic key for WSSPL001.OVR: replaces the English rules of routine 92B2h.

The prologue (word copied to `out`, lowercased) up to 92E1h is kept; from 92E1h:
  digraphs сч/шч/зч -> щ, тс/тьс -> ц; each char -> class letter via CLASS (0 = skip: ь ъ ' -),
  repeats merged. Vowels stay (а/о and е/и are the usual unstressed confusions), voiced and
  voiceless consonants share a class. Class letters are ASCII with empty rows in the engine's
  English key-equivalence table (DS:723h + 5*c, used by 9A66h), so no foreign equivalences apply.
key() is the Python mirror used to build the dictionary trailer; test_splmn.py runs the patched overlay.
"""
from keystone import Ks, KS_ARCH_X86, KS_MODE_16

START, END = 0x92E1, 0x9A66          # rewritten part of 92B2h (its old epilogue ends at 9A65h)
CS0 = 0x10                           # the code segment starts 10h into the image: IP = offset - 10h
                                     # (far calls lcall 0:2D70 reach 2D80h), so cs:[x] is image x+10h
GROUPS = {'a': 'аояё', 'e': 'еиіыэєїй', 'u': 'ую', 'b': 'бп', 'v': 'вф', 'g': 'гґкх', 'd': 'дт',
          'z': 'жшщ', 'q': 'зс', 'c': 'ц', 'w': 'ч', 'l': 'л', 'p': 'м', 'o': 'н', 'r': 'р'}
CLASS = {c: k for k, g in GROUPS.items() for c in g}
DIGRAPHS = {'сч', 'шч', 'зч', 'тс'}  # word starts spelled with 3 letters in the trailer groups


def key(word):
    w, out, i = word.lower(), [], 0
    while i < len(w):
        c = w[i]
        if w[i:i + 2] in ('сч', 'шч', 'зч'):
            c, i = 'щ', i + 1
        elif w[i:i + 2] == 'тс':
            c, i = 'ц', i + 1
        elif w[i:i + 3] == 'тьс':
            c, i = 'ц', i + 2
        i += 1
        k = CLASS.get(c)
        if k and (not out or out[-1] != k):
            out.append(k)
    return ''.join(out)


def b(c):
    return c.encode('cp1125')[0]


ASM = '''
    mov si, [bp+8]
    mov di, si
    xor dl, dl
next:
    lodsb
    or al, al
    jz done
    mov ah, [si]
    cmp ah, {ch}
    jne notch
    cmp al, {s}
    je shch
    cmp al, {sh}
    je shch
    cmp al, {z}
    jne classify
shch:
    mov al, {shch}
    inc si
    jmp classify
notch:
    cmp al, {t}
    jne classify
    cmp ah, {s}
    je ts
    cmp ah, {soft}
    jne classify
    cmp byte ptr [si+1], {s}
    jne classify
    inc si
ts:
    mov al, {ts}
    inc si
classify:
    mov bl, al
    xor bh, bh
    mov al, byte ptr cs:[bx+{table}]
    or al, al
    jz next
    cmp al, dl
    je next
    mov [di], al
    inc di
    mov dl, al
    jmp next
done:
    mov byte ptr [di], 0
    pop si
    pop di
    mov sp, bp
    pop bp
    ret
'''


def patch(img):
    """Return the image with the Cyrillic key routine and its class table."""
    ks = Ks(KS_ARCH_X86, KS_MODE_16)
    table = START + 0x100                     # well past the code, inside the old routine
    src = ASM.format(ch=b('ч'), s=b('с'), sh=b('ш'), z=b('з'), shch=b('щ'), t=b('т'), ts=b('ц'),
                     soft=b('ь'), table=table - CS0)
    code = bytes(ks.asm(src, START)[0])
    assert code.endswith(b'\x66\xc3') and code.count(0x66) == 1   # keystone: 16-bit ret as 66 C3
    code = code[:-2] + b'\xc3'
    assert START + len(code) <= table and table + 256 <= END, len(code)
    tab = bytearray(256)
    for c, k in CLASS.items():
        tab[b(c)] = ord(k)
    img = bytearray(img)
    img[START:END] = bytes(END - START)
    img[START:START + len(code)] = code
    img[table:table + 256] = tab
    return bytes(img)


if __name__ == '__main__':
    for w in ['малако', 'молоко', 'щастье', 'счастье', 'тсапля', 'цапля', 'учиться', 'учится',
              'Миллиях', 'сдесь', 'здесь']:
        print(w, key(w))
