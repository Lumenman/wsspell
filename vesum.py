"""Ukrainian word forms for splmnbuild.py from brown-uk/dict_uk (VESUM; data CC BY-NC-SA 4.0).

  gh release download v6.8.6 -R brown-uk/dict_uk -p dict_corp_vis.txt.bz2
  python -X utf8 vesum.py dict_corp_vis.txt.bz2 > uk_forms.txt
  python splmnbuild.py SPLMN001.DCT uk_forms.txt --cp cp1125

Every form except those tagged only :bad (non-standard spelling); ’ becomes '.
"""
import bz2
import sys

forms = set()
for line in bz2.open(sys.argv[1], 'rt', encoding='utf-8'):
    p = line.split('#')[0].split()
    if len(p) > 1 and ':bad' not in p[1]:
        forms.add(p[0].replace('’', "'"))
sys.stdout.write('\n'.join(sorted(forms)) + '\n')
