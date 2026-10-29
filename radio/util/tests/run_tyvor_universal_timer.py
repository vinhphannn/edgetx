from pathlib import Path
import json,shlex,subprocess,shutil,os
r=Path(__file__).resolve().parents[3];o=Path(os.environ['TYVOR_UNIVERSAL_TIMER_TEST_OUTPUT']);o.mkdir(parents=True,exist_ok=True);b=Path(os.environ['TYVOR_NATIVE_BUILD'])
source=Path(__file__).resolve().parent/'fixtures/tyvor_universal_timer.cpp'
cc=next(x for x in json.loads((b/'compile_commands.json').read_text()) if x['file'].endswith('/gui/128x64/view_main.cpp'))
args=shlex.split(cc['command']);args[args.index('-o')+1]=str(o/'probe.o');args[args.index('-c')+1]=str(source)
subprocess.run(args,cwd=b,check=True)
original=b/'radio/src/CMakeFiles/radiolib_native.dir/gui/128x64/view_main.cpp.o';copy=o/'view_main.test-only.o';shutil.copy2(original,copy)
subprocess.run(['objcopy','--globalize-symbol=_ZL23readTyvorHomeFlightDatav','--globalize-symbol=_ZL13drawTyvorHomev','--globalize-symbol=_ZL18drawTyvorHomeTimerPKcb',str(copy)],check=True)
commands=subprocess.check_output(['ninja','-t','commands','simu'],cwd=b,text=True).splitlines()
link=next(x for x in reversed(commands) if ' -o simu ' in x)
# Ninja uses an outer ':' shell command; take the actual compiler invocation.
start=link.index('/usr/bin/c++');link=link[start:];link=link.split(' && ')[0]
args=shlex.split(link);args[args.index('-o')+1]=str(o/'universal-timer-test')
args=[str(copy) if x=='radio/src/CMakeFiles/radiolib_native.dir/gui/128x64/view_main.cpp.o' else x for x in args]
args.extend([str(o/'probe.o'),'-Wl,--wrap=main'])
(o/'probe-link-command.json').write_text(json.dumps(args,indent=2));subprocess.run(args,cwd=b,check=True)
result=subprocess.run([str(o/'universal-timer-test')],env=dict(os.environ,TYVOR_UNIVERSAL_TIMER_TEST_OUTPUT=str(o)),cwd=o)
raise SystemExit(result.returncode)
