# SPLMN: the binary format of WordStar spelling dictionaries

A research specification, 2026-10-01. Sources: the `DICT` files of WordStar 7.0D, the
unpacked speller overlays WSSPL **6.00** and **7.51**, running their machine code under
Unicorn, and checks in WordStar itself under DOSBox. This is not a published Microlytics
specification.

## Status and scope

Recovered: the general graph serialization, every part type **that occurs in our sample
set**, the symbol and address tables, dense transitions, cyclic transducers, the
directories, the fields the loaders use, and the 7.51 phonetic extension. The original
Latin-script dictionaries can be read independently, lexical parts extracted and the
transducer relations executed. The builder of this project writes the two-part 7.51
variant without any Microlytics file: fields the engines do not read are written as
constants taken from the English sample. Being able to read the old format does not mean
having a compiler for all of its automata.

Some fields that these engines do not interpret are kept as opaque metadata. What they
meant to the original compiler is unknown. This is **not a complete official
specification of every Microlytics variant**. The tables below separate established
meaning from hypothesis; unknown bits are not declared free.

Scope: `SPLMNnnn.DCT`, and the same container in `SPLMN001.LGL`. `THESR`, `DEFIN`,
`HYPMN`, personal dictionaries and the OVR packing are separate formats. The external
country number (`.la`) and the file name are not fields of the graph serialization.

## 1. Numbers, addresses and overall layout

Multi-byte numbers are **big-endian** unless stated otherwise. `BE16`, `BE24`, `BE32`
denote unsigned numbers of that width. The exception is the 7.51 phonetic trailer, whose
addresses and offsets are little-endian. Characters are bytes of the OEM code page, not
UTF-8.

```text
0                           start of header
...                         metadata, input map, alphabet,
                            short reference tables, directories, descriptors, roots
BE16(header+12h) = DATA      start of the shared graph area
DATA + BE24(header+45h)      end of the graphs = BE24(header+00h) = CORE_END
CORE_END ... EOF            optional extension; in 7.51 the phonetic index
```

Table addresses in the prefix are **absolute file offsets**, usually BE16. Node,
reference and root addresses are **relative to DATA**. Shared tails of different branches
and parts may point into the same area: physical parts need not occupy disjoint ranges.
The end of a part cannot be derived from the start of the next one.

A zero root address means "no root", but a zero graph byte means "end of list". These
are different conventions. The original graphs have an unused empty area at the start;
where the real parts are is given by the directories.

## 2. Header

The common part is 48h bytes, the extended 7.51 header 5Ch. The loaders read the first
**50h** bytes, which in the old variant includes the start of the copyright string. So
"the header is always 50h" is a wrong description of the file structure. Offsets in the
table are hexadecimal.

Legend: **C** confirmed by consumer code; **D** exact match with the data of all relevant
samples; **?** the vendor's meaning is not established.

| Offset | Size | Meaning |
|---|---:|---|
| 00 | 3 | CORE_END, end of the main area of the file. D; a separate file check at 49DAh also reads it. |
| 03 | 1 | 00 in all samples; ?. |
| 04 | 1 | `PAGE`, positions per alphabet page. C. |
| 05 | 1 | 02 in all samples; equals the width of table entries, but its role as a field is not proven. |
| 06 | 1 | 00; ?. |
| 07 | 1 | `T1`, exclusive upper bound of one-byte references. C. |
| 08 | 1 | `LIT`, start of three-byte direct references. C. |
| 09 | 1 | `SYM`, start of the node byte range. C. |
| 0A | 2 | Address of the input map. C. |
| 0C | 2 | Address of the first BE16 reference table. C. |
| 0E | 2 | Address of the second BE16 reference table. C. |
| 10 | 2 | Size of the second reference table in bytes, `2*BE16(+3C)`. D. |
| 12 | 2 | DATA. C. |
| 14 | 2 | E6h in the new sample: address of the additional input-map descriptor. 0 in the old ones. Structure below; loaders use 0A/2D/2E directly. |
| 16 | 1 | 00; ?. |
| 17 | 1 | `ESC`, masked code that moves to the next alphabet page. C. |
| 18 | 4 | Probable build stamp: as BE32 a plausible Unix time of 1990–1993. Hypothesis; not the copyright date and not an integrity check. |
| 1C | 2 | 0005 in the old files, 000A in the new one; ?. Do not treat as a reliable version number. |
| 1E | 2 | In the old files points to the last ordinary alphabet entry before FFFF; 0 in the new one. D, not used by the loaders. |
| 20 | 1 | 48h/5Ch, equals the copyright address and the header size. D. |
| 21 | 1 | Descriptive internal language. The actual switch uses the descriptors' language. |
| 22 | 1 | 80h/A0h. The loaders keep bit 0; they do not interpret the other bits. The vendor's mask is unknown. |
| 23 | 1 | `DENSE`, code of the special dense-transition node. C. |
| 24 | 4 | Number of accepting paths **summed over the lexical parts**. Not the number of unique words. D. |
| 28 | 2 | Size of the first reference table in bytes: `2*T1`. D. |
| 2A | 2 | Address of the array of BE16 descriptor addresses. C. |
| 2C | 1 | 00; ?. |
| 2D | 1 | Low byte of the input range, `BASE_CHAR`. C. |
| 2E | 1 | Number of bytes of the input map, `SPAN`. C for the old loader; see the 7.51 bound quirk below. |
| 2F | 1 | Number of parts. The 7.51 loader allows at most 10. C. |
| 30 | 2 | Address of the array of BE16 root-index addresses. C. |
| 32 | 2 | Address of the copyright string with its length byte. 48h/5Ch in all samples. D. |
| 34 | 1 | `EPS`, the empty-symbol code of transducers; 00 in the old files, F8h in the new one (beyond the used alphabet). C. |
| 35 | 1 | Maximum length of an accepting path of a lexical part **in internal codes**, ESC included. D. |
| 36 | 1 | Highest alphabet page number, from 0. C for 6.00; 7.51 loads it too. |
| 37 | 1 | 03 in all samples, equals the width of a root address; its own role is not proven. |
| 38 | 2 | Address of the symbol table. C. |
| 3A | 2 | Number of entries of the first table (`T1`). D. Special case in 7.51: the **first byte** of +3A is also read as the penalty-character setting; it is 0 in the whole corpus, the setting is off. |
| 3C | 2 | Number of entries of the second table. D. |
| 3E | 2 | Address of the "part type → part number" index. D. |
| 40 | 4 | 00010000 or 00004000. Unknown; not used by these loaders. |
| 44 | 1 | 00; ?. |
| 45 | 3 | Size of the shared graph area. C. |
| 48–5B | 20 | Extended header of the new sample only. Opaque metadata: `0000000000000000 00540100 0000F800 00000000`. Do not relocate values inside it as addresses without further evidence. |

The string at +32: the first byte is the length of the main copyright text, then the
text. CR/LF, a date and NUL may follow; those extra bytes are not necessarily counted in
the length. The new sample has a first length of 72h, the old ones 64h/66h. The next
table must be located by its address in the header, not by searching for the end of the
string.

The additional descriptor at +14 in 7.51 is 16 bytes:
`10 7A 0000 BASE:BE16 SPAN:BE16 MAP_OFFSET:BE16 000000000000`.
The three named values repeat the main header. The meaning of 7Ah and of the zero fields
is not established; the builder writes `10 7A` and zeros and recomputes the three values.

## 3. Alphabet and input encoding

The table at +38 consists of two-byte entries. The DOS engines take the **second byte** of
each entry; this does not make the format Unicode. Ordinary entries have a high byte of
00; the old files also have FF00 for epsilon and FFFF at the end. Part of the last page
may be missing if its positions are never used.

A logical code `c` is a multiple of four; its index on the page is `c >> 2`.
To read text:

```text
page = 0
for each c:
    if c < MIN_CODE: page = 0; emit nothing
    elif c == ESC: page += 1
    else:
        emit low_byte(symbols[page*PAGE + (c >> 2)])
        page = 0
```

Sequences inside the engine's memory end with FFh; the values FCh–FFh are not ordinary
masked codes. This is a buffer convention, not a separate end-of-word byte in the graph
on disk. The end of a word is a node bit.

The table at +0A has `SPAN` bytes for the input values
`BASE_CHAR ... BASE_CHAR+SPAN-1`. A value `v >= FCh` means an invalid character.
Otherwise the input byte is encoded as `(v & 3)` repetitions of ESC followed by `v & FCh`.
So the direct input map addresses up to four pages. Case is also decided by tables and
rules in the OVR; the DCT alone does not define case checking.

**Implementation difference:** routine 5632h (7.51) checks the upper bound with `<=`,
7EFAh with `<`; the old loader copies exactly SPAN bytes. The builder therefore writes
the correct number of entries and an FFh right after them. The project once wrote
`last-first`, and one conversion path could lose the last character. The trailing FF also
prevents the first byte of the alphabet table from being read as the code of a
nonexistent character.

The new Cyrillic dictionaries have three pages of 26 positions; ESC=64h, EPS=F8h.
In the old files PAGE=28–32, usually EPS=0 and DENSE=(PAGE-1)*4, ESC=(PAGE-2)*4.
These numbers come from the file and are not fixed in a general decoder.

## 4. Directories and part descriptors

The index at +3E:

```text
u8 max_type
u8 part_index[max_type]  # entry type-1; FF = no part of this type
[zero padding to an even address]
```

For example, French: `06 02 04 03 00 05 01 00`: type 1 is in part 2, type 4 in part 0.
The new English: `02 00 01 00`. `LGL`: max_type=32, unused positions FF, types 31 and 32
point to parts 2 and 3. The main loader uses the array at +2A, but the index must agree
with it.

Descriptors are at the addresses in the array at +2A, not necessarily contiguous with a
constant stride. Offsets below are relative to the descriptor.

| Offset | Size | Meaning |
|---|---:|---|
| 00 | 1 | Length: 20h in 6.00, 24h in the new sample. |
| 01 | 1 | Part type. |
| 02 | 2 | Absolute address of the root index, duplicates the array at +30. |
| 04–07 | 4 | Properties of the compiled graph: 00000440/498/490 in the old files, 00000040 in the new one. The bits are not decoded. 6.00 copies byte +06 into an array; no further use found. |
| 08 | 4 | Offset of the dummy start node relative to DATA. Equals the last entry of the root index. |
| 0C | 2 | Maximum path length in internal codes, FFFF for cyclic transducers. |
| 0E–11 | 4 | Zero in all samples, unknown. |
| 12 | 1 | Working internal language ID. |
| 13 | 1 | Search participation flags, see below. |
| 14 | 1 | Category of additional vocabulary: 0, 1, 2. 7.51 reports 1/2 to the caller; not a language number. |
| 15 | 1 | MIN_CODE if 01h–F7h. Otherwise 4 is used when EPS<F8h, 0 in other cases. 7.51 keeps it per part; 6.00 applies one global value. |
| 16 | 2 | Address of the optional scoring table for special characters (7.51); 0 in the whole corpus. See the limitations section. |
| 18–1B | 4 | Zero; unknown. |
| 1C | 1 | 00; ?. |
| 1D | 1 | 00 in the old files, FF in the new one; the vendor's meaning is unknown. |
| 1E | 2 | In a 24h descriptor, the maximum length **in output characters**, without ESC. 0000 in the old ones. D. |
| 20–23 | 4 | New descriptor only; zero, ?. |

Types:

| Type | Purpose according to code and content |
|---:|---|
| 1 | Main lexical part. |
| 2 | Additional lexical part. In English mostly abbreviations, but **not universally "abbreviations"**: in Spanish and Italian it holds millions of word forms, in German also names. |
| 3 | Additional lexical list that the engine puts before the main one in some kinds of search; by content, frequent vocabulary. |
| 4 | Phonetic key transducer; used by the older sound-alike search. |
| 5 | Spelling/case variant transducer, including variants with a period; intersected with the lexical graph during recognition. |
| 6 | Case normalization transducer; e.g. `HELLO → hello`, `BonJour → bonjour`. |
| 16 | Additional candidate transformation in the code of both engines. No instance in our corpus; the content for a particular language is not confirmed. |
| 31–36 | Additional vocabulary categories controlled by separate request bits. LGL has 31 and 32. |
| others | Not included in the working lists by the dispatchers examined. This does not prove that other products do not use them. |

Masks at +13: 40h puts the part into the candidate/suggestion list, 20h into the ordinary
lookup list. For 31–36, 80h also enables the extended recognition list. Parts 1/2/3 are
added to the common list by type regardless of 80h. The values E8h/88h/12h/00h cannot be
read as one enumeration: the bits 08h/10h/02h, unused by these consumers, are not decoded.

Practical details: for type 3, 7.51 inserts **the number 3**, not always the current part
number. The ordinary list counter is incremented even when 20h is off, leaving an FF gap.
Descriptors must not be reordered or merged on the assumption that order does not matter.
LGL is useful for checking exactly these differences.

Parts are grouped by consecutive changes of the language at +12. Code 0 terminates the
language list. From the original files: 1 US, 2 UK, 3 French, 4 Spanish, 5 German,
6 Italian, 0Fh French Canadian, 11h Mexican Spanish. The external file numbers are
001, 044, 033, 034, 049, 039, 002, 052 respectively. The project-defined 7Fh for plain
Cyrillic word forms is not an official Russian/Ukrainian code: it switches off the
built-in Western European rules of 7.51.

## 5. Root index

For each part the array at +30 points to `PAGE+1` BE24 entries. The first PAGE are node
addresses by first **internal code** (`code >> 2`), 0 meaning none. The last entry is the
address of the dummy start node, duplicating descriptor+08. Its child list starts at the
next byte. The last entry is **neither the upper bound of the part nor an end marker of
the whole graph**.

A root may lie inside an out-of-line dense table. Root addresses need not increase. The
ESC root represents all words starting with a character of another page.

## 6. Graph serialization

Physically: lists of sibling arcs, written depth first, with shared tails. The graph is
acyclic for vocabulary; transducers may have backward references and real cycles.
Calling the whole file a tree is technically inaccurate.

| First byte b | Size | Meaning |
|---|---:|---|
| 00 | 1 | Empty list / end of branch. This is **not** a reference through table entry 0. |
| 01 ≤ b < T1 | 1 | Address `BE16(table1 + 2*b)`. |
| T1 ≤ b < LIT | 2 | Address `BE16(table2 + 2*(((b-T1)<<8) | next_byte))`. |
| LIT ≤ b < SYM | 3 | Direct address `((b-LIT)<<16) | BE16(next_two_bytes)`. |
| b ≥ SYM | 1 + child list | Arc node; `v=b-SYM`, `code=v & FCh`, `final=v & 1`, `more=v & 2`. |

An ordinary node byte is followed by its child list. If `more != 0`, the next sibling
follows the **physical** child list. If `final != 0`, the path ends a word, but the node
may still have a nonempty continuation.

A reference replaces the rest of the current list, not a single letter. After resolving
it the logical walk continues at the target, but only the length of the reference counts
when computing where the next physical sibling starts. In the files observed the target
of a reference starts with a node, not with a second reference; 5820h resolves one step.

Skipping without following references (56B8h):

```text
depth = 1
while depth != 0:
    if byte >= SYM:
        if byte & 2: depth += 1
        advance 1
    else:
        advance token_length(byte)  # 1, 2 or 3; 00 has length 1
        depth -= 1
```

So a cyclic automaton can be skipped correctly without following the cycle.
The first and second tables have 16-bit targets; addresses >=10000h need direct
references. The range of direct targets is limited to `(SYM-LIT)*65536`. The number of
one-byte references, the size of the second table and the number of high bytes of direct
addresses share one range 00h..SYM-1; a larger dictionary moves the token boundaries.
No fixed "1 MB per DCT" limit follows from the format.

### Dense table

A node with `code == DENSE` does not add a character to the word. Its continuation gives
the table base (possibly through a reference). For a wanted code `c` the slot is at
`base+c`, i.e. `base + 4*(c>>2)`. Each slot is four bytes: the node byte and three bytes
for the continuation. For an existing transition the code of the node byte must equal c.
A different code means no transition; such a slot must not be treated as a normal letter.
The original files contain fillers like `FE 00 00 00`.

Enumeration checks all PAGE slots and skips the DENSE marker itself. The `more` field
inside a slot does not mean the next slot must be read sequentially: exactly the slot of
the wanted code is addressed. This is implemented by 5A32h/205Ah in 7.51.

## 7. Transducers (types 4/5/6)

One logical arc of a string relation is written as **a pair of levels**: first the output
code, then the input code. The child list of the second node is the next state. The final
bit of the second node allows the transduction to end. EPS on the output side outputs
nothing; EPS on the input side consumes nothing in the general relation. ESC is handled
separately on each side: an interleaved sequence must not be decoded as one word and then
split.

The walk state is `(address, input position, output sequence)`. The same graph state is
visited with different input positions, so a cycle by itself does not mean a corrupt DCT.
The number of all paths may be infinite. Enumerating the results for a given string needs
visit control and explicit resource limits. `Splmn.transduce()` raises an exception when
a limit is reached and never silently returns a truncated result.

The original routines are not equivalent to enumerating the whole relation: 8086h (7.51)
and 6F78h (6.00) choose the first matching path, trying output codes in a specific order.
6.00 has a separate branch for EPS in the input node; 7.51 requires an exact match there.
The general composition with the lexical graph is done by 83ECh/7258h respectively and
handles empty transitions separately. In this composition the query key is matched
against the first (output) side and the lexical candidate against the second: checking it
needs `reverse=True`. The set of results of the relation and the result chosen by the
engine must be kept apart.

Examples checked with the machine code and an independent reader:

| File / type | Input | Result |
|---|---|---|
| 033 / 4 | bonjour | bonjur |
| 033 / 4 | école / ecole | ekel |
| 044 / 4 | hello | ele |
| 049 / 4 | strasse | straßa |
| 033 / 6 | BonJour | bonjour |
| 049 / 6 | Straße | straße |

The type 5 relation is wider than a simple case change: in French, for `hello` there are
`Hello`, `HELLO`, `hello.` and other paths. The real search intersects it with the
vocabulary and applies external rules, so this does not promise to accept every such
string unchecked. Dumping type 5 as a "word list" is meaningless.

## 8. The 7.51 phonetic extension

The original English DCT: CORE_END=132120, EOF=135100. The last 6Ah bytes are directory D
at 134994. Loader 9152h looks for it **from the end of the file** and checks the bytes
`23 23` (`##`) at +68. If the trailer is missing or fails to load, ordinary lookup still
works but this phonetic mechanism is off.

| Offset from D | Size | Contents |
|---|---:|---|
| 00–29 | 42 | Zero in the original sample, not read by the loader. |
| 2A–43 | 26 | The text date `1992/03/20 15:00` and NUL padding, not used in search. |
| 44–49 | 6 | The string `01.01` + NUL, not checked by 9152h. |
| 4A | 4 LE | Absolute address of A, the array of two-byte key starts. |
| 4E | 4 LE | Absolute address of B, the groups of word starts. |
| 52 | 4 LE | Absolute address of C, the array of LE16 group offsets relative to B. |
| 56 | 4 | 0 in the original sample; unknown, not read by the loader. |
| 5A | 4 | `DA DA 00 00` in the original sample; unknown, not read by the loader. Not a confirmed checksum. |
| 5E | 4 LE | Address of D, a self-reference. Equals EOF-6Ah; 9152h does not use it to find D. |
| 62–67 | 6 | Zero in the original sample, unknown. |
| 68 | 2 | `##`. |

A holds the pairs of the first two bytes of a phonetic key; a short key is padded with
NUL, the entry `00 00` ends the linear search. The number of entries including the
terminator is `(B-A)/2`; the English file has 152. C has as many LE16 offsets. The last
offset in C points to the end of B, not to an ordinary group.

A group in B: a sequence of three-byte word starts, then a zero byte and padding to an
even boundary. Two-byte starts have a NUL third byte; some digraphs need three. In the
English file A/B/C are 304/2266/304 bytes. The key algorithm lives in the **OVR**, not in
this trailer. Correct trailer addresses with English keys do not make it a Russian
phonetic dictionary.

At 275Ch there is a signed comparison when skipping repeated first letters >=80h. The
first-letter buffer is 16 bytes and is adjacent to the key. The Cyrillic builder limits a
group to fifteen starts; this is a limitation of the 7.51 implementation, not of the
field widths. In our OVRs the key agrees with `phon1125.py`.

## 9. Engine compatibility and limits

- 6.00 copies the tables separately, 7.51 reads the whole DATA prefix into memory.
  The old BE16 addresses limit the size of the prefix regardless of the size of the graphs.
- 7.51 refuses when the available/required graph cache is <=1000h. The builder pads
  small dictionaries' graphs to 1001h. 6.00 has no such threshold in the matching branch.
- 6.00/7.51 use the same token serialization and dense tables. The main difference of our
  samples is the set of parts, epsilon and metadata, not a different byte order or a
  fundamentally different way of compressing the vocabulary.
- +16 of a 7.51 descriptor: with language 8 and a zero address the engine synthesizes
  `01 MIN_CODE FF` inside the descriptor. For a nonzero table 2CB4h reads a count byte and
  compares **only the first** code (the pointer is not advanced). There is no sample of a
  real multi-entry table; the assumed list format must not be presented as confirmed. This
  tunes suggestion scoring and is not part of the main compression scheme.
- First byte of +3A of the header in 7.51: if the low bit is set, the masked code makes
  2CB4h assign score FFh; otherwise the setting is off. The byte is 0 in all files at hand.
  There is no separate stock example.
- The word list and WordStar's behavior are different levels. Normalization of English
  `'s`, compound words, case, the editor's tokenization and the order of suggestions are
  partly defined by the OVR/EXE. A correct word dump does not prove these rules correct.

## 10. Verification and results

Reproducible commands (the DICT directory of WordStar 7.0D, see README):

```sh
python -X utf8 test_splmn.py WS_DICT_DIR
python -X utf8 test_splmn_format.py WS_DICT_DIR --engines --report format_report.json
python splmn.py WS_DICT_DIR/SPLMN033.DCT > french-oem.txt
```

`words()` selects the lexical parts by default. Transducers use
`transduce(raw_bytes, part_number)`; part numbers are zero based, types come from the
descriptors. `words([])` returns an empty list. `words([transducer_number])` is explicitly
rejected. `path_stats()` counts paths in an acyclic graph without expanding millions of
word forms; for a cyclic graph it reports that there is no finite count.

| File | Accepting paths of lexical parts by type | Sum at +24 |
|---|---|---:|
| 001.DCT | 1: 91 308; 2: 840 | 92 148 |
| 001.LGL | 31: 68 173; 32: 26 687; 1: 90 995; 3: 11 016; 2: 594 | 197 465 |
| 002.DCT | 1: 472 234; 3: 25 914; 2: 1 640 | 499 788 |
| 033.DCT | 1: 472 065; 3: 25 910; 2: 1 255 | 499 230 |
| 034.DCT | 1: 677 201; 3: 30 501; 2: 3 581 370 | 4 289 072 |
| 039.DCT | 1: 370 484; 3: 25 357; 2: 2 443 611 | 2 839 452 |
| 044.DCT | 1: 91 323; 3: 6 376; 2: 672 | 98 371 |
| 049.DCT | 1: 347 717; 3: 20 696; 2: 15 109 | 383 522 |
| 052.DCT | 1: 677 427; 3: 30 501; 2: 3 581 476 | 4 289 404 |
| 007.DCT, built here (Russian) | 1: 3 196 185; 2: 1 | 3 196 186 |
| 380.DCT, built here (Ukrainian) | 1: 3 817 098; 2: 1 | 3 817 099 |

Repeats between parts are included in the sums. In 007/380 the second word is `обл.`.
Colloquial Russian forms are kept; source filtering drops only `Erro`.

The builder recomputes the path counts, the code and character maxima, the sizes of both
reference tables, the type index, the input map parameters, the root addresses, CORE_END
and the trailer addresses. No template is needed: the header, the descriptors (types 1/2,
flags E8h/88h) and the +14 descriptor are written as constants. Opaque vendor properties
are taken from the English sample rather than replaced by guesses. Not carried over: the
copyright string (replaced by our own), the build stamp at +18 (0), the dates and
`DA DA` of the phonetic trailer (0). Without a phonetic module no trailer is written:
word checking works, only sound-alike suggestions are off. Checked with the 7.51 engine
in an emulator and with WordStar under DOSBox (English control, Cyrillic, the full 380).

## 11. Addresses and how to reproduce

All routine addresses above are offsets **in the unpacked image**. CS starts at 10h:
IP = image_offset-10h. DS starts at 8060h in 6.00 and at 9E40h in 7.51. A wrong CS when
decompiling breaks the `cs:[...]` tables, produces false overlapping instructions and
turns a normal switch into nonsense.

| Operation | 6.00, image | 7.51, image |
|---|---:|---:|
| Open DCT | 3286 | 4098 |
| Copy header fields | 3822 | inside 4098 |
| Descriptor dispatcher | 38B8 | 447C |
| Codes → text bytes | 45FC | 559E |
| Input byte → codes | 4676 | 5632 |
| Skip a physical subgraph | 46FC | 56B8 |
| Resolve a reference | 4790 | 574C |
| Read a token | 486A | 5820 |
| Direct lookup | 490C | 58C0 |
| Sibling / dense table lookup | 4A6A | 5A32 |
| Transduction by the first matching path | 6F78 | 8086 |

`emu2.Ovl` recognizes 6.00, sets up the segments and heap and runs the chosen engine's
own loader. `open()` opens the DCT; `call()` checks the return, so hitting the
instruction limit is not taken as success. DOS read/seek calls are served from the bytes
of the given file.

For a correct decompilation: drop the first 10h bytes of the unpacked image (`unexepack.py`),
import the rest at `0000:0000` with the processor `x86:LE:16:Real Mode`. Addresses of such
a listing are **IP**; add 10h to get the values in the table above.

### Not yet established

Open questions for a truly complete vendor specification: the meaning of all unread
bits and fields; other values of the extended header; real instances of type 16, types
33–36 and a nonzero +16; multi-encoding descriptors instead of the single 7Ah. They need
further original samples or the original SDK/compiler. These gaps do not prevent reading
our whole corpus or building verified Cyrillic lexical dictionaries.
