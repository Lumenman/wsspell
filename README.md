# ws7spell

Tools for the spelling dictionaries of WordStar 7.0 for DOS: a reader and a compiler for
the Microlytics `SPLMNnnn.DCT` format, a cp1125 patch for `WS.EXE`, and an installer
that adds Ukrainian and Russian (cp1125) spelling modules next to the English one.

For WordStar 4.0 see [ws4spell](https://github.com/Lumenman/ws4spell).

- `SPLMN_FORMAT.md` — the binary format, reverse engineered from the dictionaries and the
  speller overlays (engines 6.00 and 7.51). Fields not yet understood are listed there.
- `splmn.py` — reads any SPLMN dictionary of WordStar 7.0D: word lists, transducers, statistics.
- `splmnbuild.py` — compiles word lists into a 7.51 dictionary. It needs no original
  dictionary file.
- `phon1125.py` — Cyrillic sound-alike key for suggestions (the overlay routine and the
  matching dictionary trailer).
- `wsspl.py` — patches the original `WSSPL001.OVR` for cp1125 (case tables, punctuation,
  phonetic key).
- `patch1125.py` — switches the code page tables of `WS.EXE` (letters, case, sort order)
  from cp437 to cp1125 or cp866, so WordStar treats Cyrillic letters as letters.
- `langmod.py` — builds `SPLMNccc.DCT` and `WSSPLccc.OVR` and adds the language to the
  language table of `WS.EXE`.
- `vesum.py`, `opcorpora.py` — extract word forms from the Ukrainian and Russian sources.
- `emu2.py`, `unexepack.py` — run the original speller overlay under Unicorn (tests,
  research); unpack/repack EXEPACK.

No WordStar files and no compiled dictionaries are included. You build them yourself
from the sources below.

## Requirements

- Python 3.10+
- `keystone-engine` (assembling the phonetic routine for the overlay)
- `unicorn` (only for the engine tests)
- `pymorphy3-dicts-ru` (only for the Russian word list)
- WordStar 7.0 for DOS (Rev. D). Its `DICT\WSSPL001.OVR` is the input of `wsspl.py`.
- A cp1125 keyboard driver and screen font for DOS (not part of this project).

## Building and installing

```sh
# WS.EXE: cp1125 letter, case and sort tables (keeps WS.437)
python patch1125.py C:/WS/WS.EXE

# Ukrainian: VESUM (brown-uk/dict_uk) v6.8.6
gh release download v6.8.6 -R brown-uk/dict_uk -p dict_corp_vis.txt.bz2
python -X utf8 vesum.py dict_corp_vis.txt.bz2 > uk_forms.txt
python -X utf8 langmod.py C:/WS/WS.EXE --forms uk_forms.txt --code 380 --name Ukraine

# Russian: OpenCorpora via pymorphy3-dicts-ru
python -m pip install pymorphy3 pymorphy3-dicts-ru
python -X utf8 opcorpora.py > ru_forms.txt
python -X utf8 langmod.py C:/WS/WS.EXE --forms ru_forms.txt --code 007 --name Russia
```

In a document, `.la 380` or `.la 007` switches the spelling language and `.la 001`
switches back to English. `--default` makes the new language the default one. The first
run keeps the original EXE as `WS.BAK`.

`python patch1125.py --listing WS.EXE` writes `PATCH1125.TXT`, the same tables in the
style of WordStar's `PATCH.TXT`, for entering them by hand with WSCHANGE.

A plain word list can also be compiled directly:
`python splmnbuild.py OUT.DCT MAIN.txt [ABBR.txt] [--cp cp1125]` (UTF-8, one word per line).

## Sources

**WordStar 7.0D.** The WordStar 7 archive of Robert J. Sawyer,
<https://sfwriter.com/ws7.htm> (download
`sawyer-wordstar-7-archive-release-1.5.zip`). The work here was done on these files from
its `WS\DICT` (SHA-256):

| File | Bytes | SHA-256 |
|---|---:|---|
| SPLMN001.DCT | 135100 | `e799c8edbb3e2a04dd55475af331184530d267498ceb0145e274530fa865f3ec` |
| SPLMN001.LGL | 438121 | `190993b57cca237e465165555b23337efa1fb59012d0717ef816f4b2437e05db` |
| SPLMN002.DCT | 184876 | `e9bf755bb6656908d17d0fc6d1e56978acab16c54604621d80ff35b9c35a4963` |
| SPLMN033.DCT | 180014 | `6ca10e54cb4d810f7616315d44aa5743cd2ccf8ccbb3bfc33ba6ed7a97aa875b` |
| SPLMN034.DCT | 305614 | `b60dad8f67242c44fbc22529f71fa61fb095c6788850f1b9a6db775590e48886` |
| SPLMN039.DCT | 275061 | `d14901b7c29616141503c16222e526bbb4dcedf04731f79a48e99271c251b333` |
| SPLMN044.DCT | 186765 | `71452e831e116fc35f0cfe199c70aed7fa8a620167c125d07848c5fd41063536` |
| SPLMN049.DCT | 475097 | `7e95b421da29cfef9da4be5b6e842edaf82bc2c11dfd2d24542194e54d722b46` |
| SPLMN052.DCT | 316410 | `97d7fb361768abedf30f316af858cf5fd78e9b8840ba31b051ee7d8f03bbf14e` |
| WSSPL001.OVR (7.51) | 42525 | `ba9ed78b01f003130b981f43ad8a3e0e01cad37bf3075337bd7b83a1fdbb3e82` |
| WSSPL002/033/034/039/044/049/052.OVR (6.00, identical) | 34571 | `9a535d263ff5127ae7958b414c6dacc3e39e00b3a795f532ded3c4b5a7daba79` |

`SPLMN001.DCT` and `WSSPL001.OVR` are identical to those on the original 5.25" install
disks of WordStar 7.0D.

**Ukrainian.** VESUM, <https://github.com/brown-uk/dict_uk>, release v6.8.6,
`dict_corp_vis.txt.bz2`, SHA-256
`e33803783ac138e6f3af2cf0e9428ba146c0ecfda7f5c41fe83ae00c7af24be9`: 3 817 098 forms.
Dictionary data: CC BY-NC-SA 4.0.

**Russian.** OpenCorpora, <https://opencorpora.org>, through `pymorphy3-dicts-ru`
2.4.417150.4580142 (OpenCorpora revision 417150): about 3.2 million forms. Dictionary data:
CC BY-SA 3.0.

A dictionary compiled from these sources is a derivative of their data, so the data
license applies if you distribute it (for Ukrainian: non-commercial, share-alike).

## Tests

```sh
python -X utf8 test_splmn.py                    # builder only, no WordStar files needed
python -X utf8 test_splmn.py C:/WS/DICT         # + English round trip, original 7.51 engine
python -X utf8 test_splmn_format.py C:/WS/DICT --engines   # format checks on all dictionaries
```

The dictionaries were also checked in WordStar 7.0D itself under DOSBox: the English
dictionary rebuilt by `splmnbuild.py` answers like the original, and samples of the full
Ukrainian and Russian dictionaries are accepted and typos are flagged.

## License

GPL v3, see `LICENSE`. WordStar is a trademark of its owners; this project is not
affiliated with them. It contains no WordStar files; the few constants needed for
compatibility (header values, table patterns) are documented in `SPLMN_FORMAT.md`.
