import struct,sys
def unpack(d):
    hdr=d.rfind(b'RB',0)-16          # EXEPACK header: ip cs mem size sp ss dest_len skip 'RB'
    ip,cs,_,_,_,_,dlen,_=struct.unpack('<8H',d[hdr:hdr+16])
    buf=bytearray(d[:hdr]); i=len(buf)
    while buf[i-1]==0xff: i-=1
    out=bytearray(dlen*16); j=len(out)
    while True:
        cmd=buf[i-1]; n=buf[i-3]|buf[i-2]<<8; i-=3
        if cmd&0xfe==0xb0: v=buf[i-1]; i-=1; out[j-n:j]=bytes([v])*n
        elif cmd&0xfe==0xb2: out[j-n:j]=buf[i-n:i]; i-=n
        else: raise ValueError(hex(cmd))
        j-=n
        if cmd&1: break
    out[:i]=buf[:i]
    return bytes(out),cs,ip,i
def repack(d,img,run=6):
    """Pack a patched image back into OVR file d with the same length (stub stays in place):
    raw prefix as in d, the rest as fills (runs >= run) and literals, padded with FFh."""
    hdr=d.rfind(b'RB',0)-16
    p=unpack(d)[3]
    segs=[]; k=p; lit=p
    while k<len(img):
        e=k
        while e<len(img) and e-k<0xffff and img[e]==img[k]: e+=1
        if e-k>=run:
            if lit<k: segs.append((0xb2,img[lit:k]))
            segs.append((0xb0,bytes([img[k]]),e-k)); lit=e
        k=e if e-k>=run else k+1
    if lit<len(img): segs.append((0xb2,img[lit:]))
    out=bytearray(img[:p])
    for n,s in enumerate(segs):
        last=1 if n==0 else 0
        if s[0]==0xb0: out+=s[1]+struct.pack('<HB',s[2],0xb0|last)
        else: out+=s[1]+struct.pack('<HB',len(s[1]),0xb2|last)
    if len(out)>hdr: raise ValueError('packed %d > %d bytes'%(len(out),hdr))
    j=len(img); i=len(out)                   # for the in-place check below
    while hdr-len(out)>15: out+=b'\0\0\xb2'   # the stub skips at most 15 FFh: pad with empty literals
    new=bytes(out)+b'\xff'*(hdr-len(out))+d[hdr:]
    assert unpack(new)[0][:len(img)]==img
    assert j>=len(out)                       # the stub unpacks in place: never overtake the input
    for s in segs[::-1]:
        i-=3+len(s[1]); j-=s[2] if s[0]==0xb0 else len(s[1])
        assert j>=i,'in-place unpack would overwrite packed data'
    return new
if __name__=='__main__':
    o,cs,ip,_=unpack(open(sys.argv[1],'rb').read()); open(sys.argv[2],'wb').write(o); print(len(o),hex(cs),hex(ip))
