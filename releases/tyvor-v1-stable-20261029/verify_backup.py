#!/usr/bin/env python3
"""Read-only verification of the stable BIN backup; no flashing or Git writes."""
from pathlib import Path
import hashlib,json,struct
p=Path(__file__).resolve().parent
state=json.loads((p/'SOURCE_STATE.json').read_text(encoding='utf-8'))
for line in (p/'RELEASE_FILES.sha256').read_text().splitlines():
    expected,name=line.split('  ',1)
    assert hashlib.sha256((p/name).read_bytes()).hexdigest()==expected,name
print('PASS release metadata/file checksums')
for line in (p/'SHA256SUMS').read_text().splitlines():
    expected,name=line.split('  ',1)
    data=(p/name).read_bytes()
    assert hashlib.sha256(data).hexdigest()==expected,name
    print('PASS SHA256',name,len(data),'bytes')
fw=(p/'firmware.bin').read_bytes();app=(p/'application.bin').read_bytes()
assert len(fw)==512504 and len(app)==479736 and app==fw[32768:]
assert hashlib.sha256(fw[:32768]).hexdigest()==state['boot_region_sha256']
assert hashlib.sha256(fw[:22580]).hexdigest()==state['bootloader_binary_sha256']
assert len(fw)<=524288 and len(app)<=491520
for data in [fw,app]:
    sp,pc=struct.unpack_from('<II',data)
    assert 0x10000000<=sp<=0x10010000 or 0x20000000<=sp<=0x20020000
    assert pc&1 and 0x08000000<pc<0x08080000
print('PASS bootloader 32768 bytes; application split/vector; flash free',524288-len(fw),'bytes')
