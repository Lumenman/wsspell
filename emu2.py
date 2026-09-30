"""Emulate WSSPL001.OVR with a real dictionary: open it (4098h), then the sound-alike search.

  python emu2.py OVR DCT word          prints the candidates whose keys routine 9A66h compares

Ovl.open() also supports the original 6.00 engine (DS offset 8060h); this CLI is 7.51 only.
Memory as in WordStar: image at linear 10000h, code segment 1001h (IP = image offset - 10h),
DS = SS = 1000h + 9E4h; the three `lcall 0:x` get the code segment. DOS lseek/read (int 21h)
go to the DCT file; the overlay's heap is set up by hand. Addresses below are image offsets.
"""
import sys
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.x86_const import *
import unexepack

BASE, CS, DS = 0x1000, 0x1001, 0x1000 + 0x9E4
RET, H, STACK = 0xFFF0, 5, 0xF000


class Ovl:
    def __init__(s, ovr, dct, cp='cp1125'):
        s.dct, s.pos, s.cp = dct, 0, cp
        img = bytearray(unexepack.unpack(ovr)[0])
        s.old = img[10:14] == b'6.00'
        ds_offset = 0x806 if s.old else 0x9E4
        s.ds = BASE + ds_offset
        far_calls = (0x5A, 0x5E67, 0x7FBC) if s.old else (0x5A, 0x6D31, 0x9D94)
        for o in far_calls:  # lcall 0:x -> code segment
            assert img[o] == 0x9A and img[o + 3:o + 5] == b'\0\0'
            img[o + 3:o + 5] = CS.to_bytes(2, 'little')
        for o in range(ds_offset * 16):  # mov reg, relative data-segment constant
            if 0xB8 <= img[o] <= 0xBF and img[o + 1:o + 3] == ds_offset.to_bytes(2, 'little'):
                img[o + 1:o + 3] = s.ds.to_bytes(2, 'little')
        s.mu = mu = Uc(UC_ARCH_X86, UC_MODE_16)
        mu.mem_map(0, 0x100000)
        mu.mem_write(BASE * 16, bytes(img))
        if s.old:
            s.w16(0xB96, 1)
            for a, v in ((0x531E, 0), (0x5320, 0x3000), (0x5322, 0), (0x5324, 0xF000),
                         (0x82, 0), (0x84, 8)):
                s.w16(a, v)
        else:
            s.w16(0x7D6, 1)
            for a, v in ((0x1D6C, 0), (0x1D6E, 0x3000), (0x1D70, 0), (0x1D72, 0x9000),
                         (0x8C, 0), (0x8E, 4)):
                s.w16(a, v)
        mu.hook_add(UC_HOOK_INTR, s.intr)
        mu.hook_add(UC_HOOK_CODE, s.code)
        s.hooks = {}

    def open(s):
        """Run the original dictionary loader for the detected engine version."""
        if not s.old:
            s.call(0x910A, 0)
            return s.call(0x4098, H)
        for a, v in ((0xC001, 0xC100), (0xC003, s.ds), (0xC100, H),
                     (0xC00D, 0xC200), (0xC00F, s.ds)):
            s.w16(a, v)
        return s.call(0x3286, 0xC000, s.ds)

    def w16(s, a, v):
        s.mu.mem_write(s.ds * 16 + a, v.to_bytes(2, 'little'))

    def cstr(s, off, seg=None):
        seg = s.ds if seg is None else seg
        b = bytes(s.mu.mem_read(seg * 16 + off, 64))
        return b[:b.index(0)].decode(s.cp, 'replace') if 0 in b else '?'

    def intr(s, mu, n, _):
        ah, al = mu.reg_read(UC_X86_REG_AH), mu.reg_read(UC_X86_REG_AL)
        if n == 1:
            return
        if n != 0x21:
            raise RuntimeError('int %x' % n)
        if ah == 0x42:
            off = mu.reg_read(UC_X86_REG_CX) << 16 | mu.reg_read(UC_X86_REG_DX)
            s.pos = [off, s.pos + off, len(s.dct) + off][al] & 0xFFFFFFFF
            mu.reg_write(UC_X86_REG_AX, s.pos & 0xFFFF)
            mu.reg_write(UC_X86_REG_DX, s.pos >> 16)
        elif ah == 0x3F:
            data = s.dct[s.pos:s.pos + mu.reg_read(UC_X86_REG_CX)]
            mu.mem_write(mu.reg_read(UC_X86_REG_DS) * 16 + mu.reg_read(UC_X86_REG_DX), data)
            s.pos += len(data)
            mu.reg_write(UC_X86_REG_AX, len(data))
        elif ah == 0x40:
            mu.reg_write(UC_X86_REG_AX, mu.reg_read(UC_X86_REG_CX))
        else:
            raise RuntimeError('int 21h ah=%x' % ah)
        mu.reg_write(UC_X86_REG_EFLAGS, mu.reg_read(UC_X86_REG_EFLAGS) & ~1)

    def code(s, mu, addr, size, _):
        off = addr - BASE * 16
        if addr == CS * 16 + RET:
            mu.emu_stop()
        elif off in s.hooks:
            s.hooks[off](s)

    def arg(s, k):
        sp = s.mu.reg_read(UC_X86_REG_SP)
        return int.from_bytes(s.mu.mem_read(s.ds * 16 + sp + 2 * k, 2), 'little')

    def call(s, fn, *args):
        sp = STACK
        for a in reversed(args):
            sp -= 2
            s.mu.mem_write(s.ds * 16 + sp, a.to_bytes(2, 'little'))
        sp -= 2
        s.mu.mem_write(s.ds * 16 + sp, RET.to_bytes(2, 'little'))
        for r in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
            s.mu.reg_write(r, s.ds)
        s.mu.reg_write(UC_X86_REG_SP, sp)
        s.mu.reg_write(UC_X86_REG_CS, CS)
        s.mu.emu_start(BASE * 16 + fn, CS * 16 + RET + 1, count=50_000_000)
        if s.mu.reg_read(UC_X86_REG_IP) != RET:
            raise RuntimeError('overlay instruction limit at %04X' % s.mu.reg_read(UC_X86_REG_IP))
        return s.mu.reg_read(UC_X86_REG_AX)


if __name__ == '__main__':
    ovr, dct, word = open(sys.argv[1], 'rb').read(), open(sys.argv[2], 'rb').read(), sys.argv[3]
    o = Ovl(ovr, dct)
    if o.old:
        raise SystemExit("CLI sound-alike probe requires 7.51; use Ovl.open() for 6.00")
    o.call(0x910A, 0)  # heap mark, restored by the open
    print('open', o.call(0x4098, H), 'phonetic loaded', o.mu.mem_read(o.ds * 16 + 0x7E0, 1)[0])
    o.hooks[0x9A66] = lambda s: print('9A66', s.cstr(0x13C2), '|', s.cstr(s.arg(1)), '|', s.cstr(s.arg(2)))
    o.mu.mem_write(DS * 16 + 0x6000, word.encode('cp1125') + b'\0')
    r = o.call(0x221A, 0x6000, DS, 0x100, 1)
    print('221A ->', hex(r), 'key', o.cstr(0xD40), 'firsts', o.cstr(0xD30))
