import urllib.request,pathlib,concurrent.futures
r=pathlib.Path('work/strata-0145-review')
def get(name):
 try:
  u='https://raw.githubusercontent.com/Niko1221/Strata/v0.1.45/'+name
  s=urllib.request.urlopen(u,timeout=40).read().decode();(r/name.replace('/','_')).write_text(s,encoding='utf8')
  lines=s.splitlines();terms=['SM75_PERF','PCIE_BALANCE','1896','2069','2146','2222','SM75_TABLE','PA_V2T','SLOT_CKPT_MOVE','1368','2016','1949','1107']
  out=[]
  for i,l in enumerate(lines):
   if any(t in l for t in terms):out.append('\n'.join(lines[max(0,i-1):min(len(lines),i+4)]))
  return name,out
 except Exception as e:return name,str(e)
for x in concurrent.futures.ThreadPoolExecutor(4).map(get,['docs/DETAILS.md','docs/OLDER_GPUS.md','docs/MULTI_GPU.md','docs/BATCHING.md','docs/NVIDIA_CUDA.md']):print(x)
