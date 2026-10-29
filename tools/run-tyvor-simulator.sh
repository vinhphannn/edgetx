#!/usr/bin/env bash
# Build the real native SDL simulator; never install packages or flash hardware.
set -euo pipefail

sim_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
sim_build_dir=${TYVOR_SIM_BUILD_DIR:-"$sim_root/build-tyvor-simu"}
[[ "$sim_build_dir" == /* ]] || sim_build_dir="$sim_root/$sim_build_dir"
sim_python=${TYVOR_SIM_PYTHON:-"$sim_build_dir/venv/bin/python"}
sim_cmake=${TYVOR_SIM_CMAKE:-"$sim_build_dir/venv/bin/cmake"}
sim_jobs=${TYVOR_SIM_JOBS:-4}
sim_mode=${1:---run}

if [[ "$sim_mode" == --help || "$sim_mode" == -h ]]; then
  cat <<'HELP'
Usage: bash tools/run-tyvor-simulator.sh [--check|--build|--run]
  --check  Read-only dependency checks. Never installs packages.
  --build  Configure/build native DevEBox 128x64 SDL simulator, without launch.
  --run    Configure/build incrementally and launch a real GUI (default).
Settings and SD content are isolated under build-tyvor-simu/runtime/.
Overrides: TYVOR_SIM_BUILD_DIR, TYVOR_SIM_PYTHON, TYVOR_SIM_CMAKE, TYVOR_SIM_JOBS.
Keys: Enter/hold Enter, Esc, M=Models, S=Radio, T=Telemetry,
      PageUp/PageDown=views, Up/Down=rotary navigation.
HELP
  exit 0
fi
case "$sim_mode" in --check|--build|--run) ;; *) echo "Unknown option: $sim_mode" >&2; exit 2;; esac
[[ "$sim_jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'TYVOR_SIM_JOBS must be positive.' >&2; exit 2; }
command -v "$sim_python" >/dev/null 2>&1 || sim_python=python3
command -v "$sim_cmake" >/dev/null 2>&1 || sim_cmake=cmake
export PYTHONDONTWRITEBYTECODE=1

sim_missing=0
sim_fail() { echo "[FAIL] $*"; sim_missing=$((sim_missing+1)); }
for sim_tool in git g++ ninja flock pkg-config "$sim_python" "$sim_cmake"; do
  if command -v "$sim_tool" >/dev/null 2>&1; then
    echo "[PASS] $sim_tool: $(command -v "$sim_tool")"
  else
    sim_fail "Missing tool: $sim_tool"
  fi
done
if command -v "$sim_cmake" >/dev/null 2>&1 && command -v "$sim_python" >/dev/null 2>&1; then
  if "$sim_cmake" --version | "$sim_python" -c 'import re,sys; text=sys.stdin.read(); m=re.search(r"cmake version (\d+)\.(\d+)",text); print(text.splitlines()[0]); sys.exit(0 if m and tuple(map(int,m.groups())) >= (3,25) else 1)'; then
    echo '[PASS] CMake >= 3.25 (also supports repository preset schema 6)'
  else
    sim_fail 'Select CMake >= 3.25; local build venv is supported.'
  fi
fi
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists sdl2; then
  echo "[PASS] SDL2 development files: $(pkg-config --modversion sdl2)"
else
  sim_fail 'SDL2 development files/pkg-config metadata not available (libsdl2-dev).'
fi
if command -v "$sim_python" >/dev/null 2>&1; then
  if ! "$sim_python" - "$sim_root" <<'PY'
import importlib.util
import sys
from pathlib import Path
required = ['asciitree', 'clang', 'jinja2', 'lz4', 'PIL', 'pydantic', 'elftools', 'typing_extensions']
missing = [name for name in required if importlib.util.find_spec(name) is None]
if sys.version_info < (3, 10):
    print('[FAIL] Build Python must be >= 3.10')
    raise SystemExit(1)
if missing:
    print('[FAIL] Build Python packages missing: ' + ', '.join(missing))
    raise SystemExit(1)
sys.path.insert(0, str(Path(sys.argv[1]) / 'radio/util'))
try:
    import find_clang
    if not find_clang.initLibClang():
        raise RuntimeError('libclang initialization failed')
    args = ['-I' + find_clang.builtin_hdr_path] if find_clang.builtin_hdr_path else []
    if not find_clang.canFindBuiltinHeaders(find_clang.index, args):
        raise RuntimeError('libclang builtin headers unavailable')
except Exception as error:
    print('[FAIL] LLVM/libclang: ' + str(error))
    raise SystemExit(1)
print('[PASS] Python packages and LLVM/libclang builtin headers')
PY
  then
    sim_missing=$((sim_missing+1))
  fi
fi
if [[ ! -s "$sim_root/radio/src/thirdparty/stb/stb_image.h" || ! -s "$sim_root/radio/src/thirdparty/FreeRTOS/include/FreeRTOS.h" ]]; then
  sim_fail 'Recorded source submodules are incomplete; inspect git submodule status.'
fi
if ((sim_missing)); then
  echo "[FAIL] $sim_missing prerequisite checks failed. Nothing installed or built."
  echo "See $sim_root/docs/building/tyvor-simulator.md"
  exit 2
fi
[[ "$sim_mode" == --check ]] && exit 0

if [[ "$sim_mode" == --run && -x "$sim_build_dir/simu" ]]; then
  sim_running_pid=$("$sim_python" - "$sim_build_dir/simu" <<'PY'
import os
import sys
from pathlib import Path
target = os.path.realpath(sys.argv[1])
for process in Path('/proc').iterdir():
    if not process.name.isdigit():
        continue
    try:
        if process.stat().st_uid == os.getuid() and os.readlink(process / 'exe').removesuffix(' (deleted)') == target:
            print(process.name)
            break
    except (OSError, PermissionError):
        pass
PY
  )
  if [[ -n "$sim_running_pid" ]]; then
    echo "[PASS] EdgeTx Simu is already running (PID $sim_running_pid). Use its window; close it before rebuilding."
    exit 0
  fi
fi

mkdir -p -- "$sim_build_dir"
exec 9>"$sim_build_dir/.simulator.lock"
if ! flock -n 9; then
  echo '[PASS] A simulator/build workflow already uses this build folder. Close its window before rebuilding.'
  exit 0
fi
if [[ ! -f "$sim_build_dir/CMakeCache.txt" || ! -f "$sim_build_dir/build.ninja" ]]; then
  "$sim_cmake" -S "$sim_root" -B "$sim_build_dir" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$sim_root/cmake/toolchain/native.cmake" \
  -DEdgeTX_SUPERBUILD=OFF -DNATIVE_BUILD=ON -DDISABLE_COMPANION=ON \
  -DSIMU_TARGET=ON -DPCB=X7 -DPCBREV=SAOLALINK_V1 \
  -DSAOLALINK_HSE_HZ=8000000 -DSAOLALINK_DEVEBOX=ON \
  -DTRANSLATIONS=EN -DALL_LANGUAGES=OFF -DCMAKE_BUILD_TYPE=Debug \
  -DPython3_EXECUTABLE="$sim_python" -DFETCHCONTENT_BASE_DIR="$sim_build_dir/deps"
else
  "$sim_python" - "$sim_build_dir/CMakeCache.txt" "$sim_root" <<'PY'
import re
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
expected = {'PCB': 'X7', 'PCBREV': 'SAOLALINK_V1', 'SAOLALINK_DEVEBOX': 'ON',
            'SAOLALINK_HSE_HZ': '8000000', 'NATIVE_BUILD': 'ON',
            'DISABLE_COMPANION': 'ON', 'CMAKE_HOME_DIRECTORY': sys.argv[2]}
for key, value in expected.items():
    if not re.search(r'^' + key + r':[^=]+=' + re.escape(value) + r'$', text, re.M):
        raise SystemExit('[FAIL] Cached profile mismatch: ' + key + '. Choose a new TYVOR_SIM_BUILD_DIR.')
print('[PASS] Existing native DevEBox cache matches source/profile; using incremental build.')
PY
  # Migrate an older cache once; subsequent starts keep the normal warm build.
  if [[ ! -f "$sim_build_dir/radio/src/bitmaps/128x64/tyvor_wordmark.lbm" ]]; then
    "$sim_cmake" -S "$sim_root" -B "$sim_build_dir" \
      -DPython3_EXECUTABLE="$sim_python" -DFETCHCONTENT_UPDATES_DISCONNECTED=ON
  fi
fi
"$sim_cmake" --build "$sim_build_dir" --target simu --parallel "$sim_jobs"
[[ "$sim_mode" == --build ]] && exit 0

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo '[FAIL] No GUI display session. Run from Ubuntu/WSLg desktop terminal.' >&2
  exit 2
fi
[[ -x "$sim_build_dir/simu" ]] || { echo '[FAIL] Native simu binary not found.' >&2; exit 2; }
mkdir -p -- "$sim_build_dir/runtime/sd" "$sim_build_dir/runtime/settings"
echo '[PASS] Launching real EdgeTX SDL simulator; no mockups or canned radio/model data.'
echo "Runtime data: $sim_build_dir/runtime"
cd -- "$sim_build_dir/runtime"
exec "$sim_build_dir/simu" --storage "$sim_build_dir/runtime/sd" \
  --settings "$sim_build_dir/runtime/settings" --width 960 --height 640
