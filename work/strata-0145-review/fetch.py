import urllib.request,json,concurrent.futures,pathlib,urllib.parse
root=pathlib.Path('work/strata-0145-review')
queries={'tree':'https://api.github.com/repos/Niko1221/Strata/git/trees/v0.1.45?recursive=1','compare':'https://api.github.com/repos/Niko1221/Strata/compare/v0.1.43.1...v0.1.45','turing':'https://api.github.com/search/issues?q='+urllib.parse.quote('repo:Niko1221/Strata is:pr Turing')+'&per_page=50','pcie':'https://api.github.com/search/issues?q='+urllib.parse.quote('repo:Niko1221/Strata is:pr PCIE_BALANCE')+'&per_page=20'}
def fetch(item):
 name,url=item
 try:
  r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Codex-Strata-version-review'}),timeout=45);d=json.load(r);(root/(name+'.json')).write_text(json.dumps(d,indent=2),encoding='utf-8')
  if name=='tree':return name,[x['path'] for x in d.get('tree',[]) if x['path'].startswith('docs/') and any(w in x['path'].lower() for w in ['gpu','cuda','cpu','batch'])]
  if name=='compare':return name,[(x['sha'][:9],x['commit']['message'].splitlines()[0]) for x in d.get('commits',[]) if any(w in x['commit']['message'].lower() for w in ['sm75','sm_75','turing','1896','1368','2016','1949','1107','balance'])]
  return name,[(x['number'],x['title'],x['state']) for x in d.get('items',[])]
 except Exception as e:return name,str(e)
for x in concurrent.futures.ThreadPoolExecutor(4).map(fetch,queries.items()):print(json.dumps(x))
