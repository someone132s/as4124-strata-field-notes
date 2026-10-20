import urllib.request,pathlib
p=pathlib.Path('work/strata-0145-review/generate.cpp')
u='https://raw.githubusercontent.com/Niko1221/Strata/v0.1.45/src/program/generate.cpp'
try:
 s=urllib.request.urlopen(u,timeout=40).read().decode();p.write_text(s,encoding='utf8');lines=s.splitlines()
 for i,l in enumerate(lines):
  if 'pcie_balance' in l.lower() or 'STRATA_PCIE_BALANCE' in l:print('\n'.join(lines[max(0,i-3):i+7]))
except Exception as e:print(type(e).__name__,e)
