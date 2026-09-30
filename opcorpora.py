"""Russian word forms for splmnbuild.py from OpenCorpora (via pymorphy3-dicts-ru; data CC BY-SA 3.0).

  python -m pip install --user pymorphy3 pymorphy3-dicts-ru
  python -X utf8 opcorpora.py > ru_forms.txt

pymorphy3 keeps forms lowercase: proper nouns (Name Surn Patr Geox Orgn Trad) get a capital,
short abbreviations (Abbr, up to 5 letters) are uppercased. Every form with ё also gets the е spelling.
Forms with digits and readings tagged Erro (typo) are skipped, ’ becomes '.
Colloquial, slang, distorted (Dist) and archaic readings are retained. A valid reading keeps a homonymous form.
"""
import sys

PROPER = {'Name', 'Surn', 'Patr', 'Geox', 'Orgn', 'Trad'}
EXCLUDE = {'Erro'}


def collect(entries):
    forms = set()
    for word, tag, *_ in entries:
        g = tag.grammemes
        if g & EXCLUDE or any(c.isdigit() for c in word):
            continue
        word = word.replace('’', "'")
        if 'Abbr' in g and len(word) <= 5 and '-' not in word:
            word = word.upper()
        elif g & PROPER:
            word = '-'.join(p[:1].upper() + p[1:] for p in word.split('-'))
        forms.add(word)
        if 'ё' in word or 'Ё' in word:
            forms.add(word.replace('ё', 'е').replace('Ё', 'Е'))
    return forms


if __name__ == '__main__':
    import pymorphy3
    forms = collect(pymorphy3.MorphAnalyzer().dictionary.iter_known_words())
    sys.stdout.write('\n'.join(sorted(forms)) + '\n')
