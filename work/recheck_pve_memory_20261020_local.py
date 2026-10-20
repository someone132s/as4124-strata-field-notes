"""Bounded PVE host bandwidth recheck, preserving all VM/service settings."""
import datetime,hashlib,json,os,pathlib,re,resource,statistics,subprocess,time
BASE=pathlib.Path('/root/codex-memory-bench-20261015')
BUNDLE=BASE/'independent/common52';BENCH=BUNDLE/'usr/bin/likwid-bench';STREAM=BASE/'stream-reference-40m-recheck-20261020'
STAMP=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
OUT=pathlib.Path('/root')/('codex-memory-recheck-7282-local-'+STAMP);OUT.mkdir(mode=0o700)
doc={'status':'running','started':datetime.datetime.now().isoformat(),'output':str(OUT),'rows':[],
 'notes':['Existing LIKWID 5.2.2 load_avx and reference STREAM binaries reused.',
 'Each measurement starts its own process. Three repeats per case; median and range reported.',
 'LIKWID: 1024 decimal MB per socket, 16 loops, 16 physical cores per socket; parallel local first touch. Node1 1536MB control.',
 'STREAM: 40 million doubles per array, 3 arrays = 0.96 decimal GB, 10 loops; standard logical byte rates. Node1 80M control.',
 'VMs and services stay running. Only test child CPU/memory affinity is set.',
 'Both-socket LIKWID uses local workgroups; both-socket STREAM uses page interleave(0,1).',
 'Online background load not isolated; this is bandwidth, not stability or whole-RAM validation.', 'Followup: strict membind for LIKWID single-node cases; two-node membind for dual case, placement sampled.']}
def capture(args):return subprocess.check_output(args,text=True,timeout=30)
def save():
 p=OUT/'results.tmp';p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');p.replace(OUT/'results.json')
def available():
 return int(re.search(r'MemAvailable:\s+(\d+)',pathlib.Path('/proc/meminfo').read_text())[1])*1024
def vmstat():
 return {k:int(v) for k,v in (l.split() for l in pathlib.Path('/proc/vmstat').read_text().splitlines()) if k in ['pswpin','pswpout','pgmajfault']}
def placement(pid):
 d={}
 try:
  for l in pathlib.Path(f'/proc/{pid}/numa_maps').read_text().splitlines():
   for n,v in re.findall(r'\bN(\d+)=(\d+)',l):d[n]=d.get(n,0)+int(v)
 except OSError:pass
 return d
def execute(kind,name,args,env,rep,expected):
 assert available()>8*1024**3,'Available memory below 8GiB'
 before=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic();samples=[]
 rawpath=OUT/f'{kind}-{name}-r{rep}.txt'
 with rawpath.open('w') as f:
  p=subprocess.Popen(args,env=env,stdout=f,stderr=subprocess.STDOUT)
  try:
   while p.poll() is None:
    if time.monotonic()-t>120:raise TimeoutError('Benchmark exceeded 120 seconds')
    if rep==1:samples.append({'seconds':time.monotonic()-t,'node_pages':placement(p.pid)})
    time.sleep(.2)
  finally:
   if p.poll() is None:p.kill();p.wait()
 after=resource.getrusage(resource.RUSAGE_CHILDREN);raw=rawpath.read_text()
 assert p.returncode==0,raw[-1500:]
 if kind=='read':
  rate=re.search(r'MByte/s:\s+([\d.]+)',raw);assert rate,raw[-1000:]
  cpus=sorted(int(c) for c in re.findall(r'Global Thread \d+ running on hwthread (\d+)',raw))
  assert cpus==expected,(name,cpus,expected)
  rates={'Read':float(rate[1])/1000}
 else:
  assert 'Solution Validates' in raw,raw[-1000:]
  rates={m.group(1):float(m.group(2))/1000 for m in re.finditer(r'^(Copy|Scale|Add|Triad):\s+([\d.]+)',raw,re.M)}
  assert len(rates)==4
 row={'kind':kind,'case':name,'rep':rep,'command':args,'rates_GB_s':rates,
  'wall_s':time.monotonic()-t,'major_faults':after.ru_majflt-before.ru_majflt,'raw_file':rawpath.name}
 if samples:(OUT/f'{kind}-{name}-r{rep}-placement.json').write_text(json.dumps(samples,indent=2))
 doc['rows'].append(row);save();print('MEASURED',kind,name,rep,json.dumps(rates),flush=True)
def main():
 assert BENCH.is_file() and STREAM.is_file()
 doc.update(cpu_info=capture(['lscpu']),hostname=capture(['hostname']).strip(),topology=capture(['numactl','--hardware']),
  cpu_topology=capture(['lscpu','-e=CPU,NODE,SOCKET,CORE']),vms_before=capture(['qm','list']),
  load_before=pathlib.Path('/proc/loadavg').read_text().strip(),available_before=available(),vmstat_before=vmstat(),
  hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BENCH,STREAM]},
  old_results=json.loads((BASE/'independent/as4124-common52-results.json').read_text()))
 save();env=os.environ.copy();env['LD_LIBRARY_PATH']=str(BUNDLE/'usr/lib/x86_64-linux-gnu')
 env['PATH']=str(BUNDLE/'usr/bin')+':'+str(BUNDLE/'usr/sbin')+':'+env['PATH']
 records=[tuple(map(int,line.split(','))) for line in capture(['lscpu','-p=CPU,NODE,SOCKET,CORE']).splitlines() if not line.startswith('#')]
 physical={}
 for cpu,node,socket,core in records:physical.setdefault((socket,core),(cpu,node))
 socket_cpus={socket:sorted(cpu for (s,c),(cpu,node) in physical.items() if s==socket) for socket in [0,1]}
 assert all(len(v)==16 for v in socket_cpus.values()),socket_cpus
 cases=[('node0_16t',['S0:1024MB:16:1:2'],socket_cpus[0],'0'),
        ('node1_16t',['S1:1024MB:16:1:2'],socket_cpus[1],'1'),
        ('both_32t',['S0:1024MB:16:1:2','S1:1024MB:16:1:2'],sorted(socket_cpus[0]+socket_cpus[1]),'0,1'),
        ('node1_16t_oldsize',['S1:1536MB:16:1:2'],socket_cpus[1],'1')]
 doc.update(physical_cpus=socket_cpus,boot_id_before=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
  sensors_before=capture(['ipmitool','sdr','type','Power Supply']),
  meminfo_nodes_before={str(n):pathlib.Path(f'/sys/devices/system/node/node{n}/meminfo').read_text() for n in [0,1]},
  stream_build_command=['gcc','-O3','-march=znver2','-mtune=znver2','-fopenmp','-static','-DSTREAM_ARRAY_SIZE=40000000','-DNTIMES=10',str(BASE/'stream.c'),'-o',str(STREAM)])
 save()
 for name,groups,cpus,node in cases:
  args=[str(BENCH),'-t','load_avx','-i','16']
  for group in groups:args+=['-W',group]
  policy='--membind='+node
  args=['numactl',policy]+args
  for rep in range(1,4):execute('read',name,args,env,rep,cpus)
 for name,groups,cpus,node in cases:
  cpuarg=','.join(map(str,cpus));e=env.copy()
  e.update(OMP_NUM_THREADS=str(len(cpus)),OMP_PROC_BIND='true',OMP_PLACES=','.join('{'+str(c)+'}' for c in cpus),OMP_DYNAMIC='false',OMP_WAIT_POLICY='PASSIVE',GOMP_SPINCOUNT='0')
  policy='--interleave='+node if name.startswith('both_') else '--membind='+node
  stream_binary=BASE/'stream-reference-80m' if name.endswith('_oldsize') else STREAM
  args=['numactl','--physcpubind='+cpuarg,policy,str(stream_binary)]
  for rep in range(1,4):execute('stream',name,args,e,rep,cpus)
 summary=[]
 for kind in ['read','stream']:
  for name,_,_,_ in cases:
   rows=[r for r in doc['rows'] if r['kind']==kind and r['case']==name]
   rates={k:{'median':statistics.median(r['rates_GB_s'][k] for r in rows),'min':min(r['rates_GB_s'][k] for r in rows),'max':max(r['rates_GB_s'][k] for r in rows)} for k in rows[0]['rates_GB_s']}
   summary.append({'kind':kind,'case':name,'GB_s':rates})
 doc.update(boot_id_after=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),meminfo_nodes_after={str(n):pathlib.Path(f'/sys/devices/system/node/node{n}/meminfo').read_text() for n in [0,1]},sensors_after=capture(['ipmitool','sdr','type','Power Supply']),status='passed',summary=summary,available_after=available(),vmstat_after=vmstat(),
  load_after=pathlib.Path('/proc/loadavg').read_text().strip(),vms_after=capture(['qm','list']),finished=datetime.datetime.now().isoformat())
 save();print('ALL_PASSED',str(OUT),json.dumps(summary),flush=True)
try:main()
except BaseException as e:doc.update(status='failed',error_type=type(e).__name__,error=str(e));save();raise
