# SaolaLink V1 and DevEBox development target

SaolaLink V1 starts from the RadioMaster Pocket hardware definition, with a
separate identity and HAL overrides. The standard target uses a 12 MHz HSE.
The DevEBox configuration uses an STM32F407VET6 with an 8 MHz HSE, 512 KiB
flash and a 32 KiB bootloader region.

## Build

Use the toolchain and Python dependencies required by this EdgeTX checkout
(Arm GNU 14.2.rel1). From the repository root:

```sh
cmake -S . -B build/saolalink-devebox \
  -DPCB=X7 -DPCBREV=SAOLALINK_V1 \
  -DSAOLALINK_HSE_HZ=8000000 -DSAOLALINK_DEVEBOX=ON \
  -DCMAKE_BUILD_TYPE=Debug -DDEFAULT_MODE=2 -DTRANSLATIONS=EN \
  -DUSE_FW_LTO=ON -DBOOTLOADER=ON \
  -DFIRMWARE_STRIP_BOOTLOADER=OFF -DFIRMWARE_FORMAT_UF2=OFF
cmake --build build/saolalink-devebox --target firmware --parallel 4
```

For the 12 MHz Pocket-compatible SaolaLink baseline, use
`SAOLALINK_HSE_HZ=12000000` and `SAOLALINK_DEVEBOX=OFF` in a separate build
directory. SaolaLink Studio lives outside this firmware repository and is
not included here.

## USB update workflow

- Install `arm-none-eabi/bootloader.bin` once using STM32 ROM DFU at
  `0x08000000` (BOOT0 high).
- Set BOOT0 low. Hold the active-high PA0 key while resetting to enter the
  SaolaLink USB DFU bootloader. Release the key after reset.
- The loader exposes `@SaolaLink App /0x08008000/02*016Kg,01*064Kg,03*128Kg`.
  Its callbacks permit accesses only to the application region, excluding
  boot sectors. This is software protection, not option-byte protection.
- Application updates start at `0x08008000` and must exclude the first
  32768 bytes of the full bootloader-inclusive `firmware.bin`. Studio
  generates this application-only file and validates its manifest/hash.
  Never send the full image to the application address.
- Reset manually after upload. Without PA0 held, a plausible application
  vector table causes the loader to jump into EdgeTX. A blank/invalid vector
  table keeps it in DFU; this check is not a complete image-integrity check.
- The running application exposes USB CDC CLI (`0483:5740`). Send `devboard`
  with LF ending for identity and SD mount status; `ls /` lists the SD root.
  Both ROM and software DFU use `0483:df11`, distinguished by media name.

## External hardware

| Peripheral | Wiring |
| --- | --- |
| MicroSD SPI, 3.3 V | CS PB12, CLK PB13, MISO PB14, MOSI PB15, common GND |
| SSD1309 OLED 128x64 SPI | SCK PC10, MOSI/SDA PC12, RES PD12, DC PC11, CS PA15 |
| DevEBox status LED | PA1 toggles from the EdgeTX main task |
| Recovery key | PA0, active high |

The six-pin SD module has no card detect, so PD9 detection is disabled.
Keep the onboard SDIO socket empty. The selected OLED module requires 5 V
module power; verify that the actual module accepts 3.3 V SPI logic. OLED
SPI runs at 2.625 MHz and both scan axes are reversed for a 180-degree
rotation relative to the initial mounting. No external backlight is needed.

## Development limits and observed results (2026-10-16)

The user confirmed USB DFU application upload, a responding USB CDC CLI,
SD FAT32 directory listing and OLED display output. The rotated image still
requires user confirmation. Host-side Studio tests cover DFU media bounds,
descriptor encoding and build/flash artifact validation; those tests reside
with Studio outside this repository.

The development profile uses volatile model/radio defaults, skips startup
calibration and fatal SD dialogs, and sets internal/external RF modules to
NONE. Six active-low menu keys are enabled through a DevEBox-specific driver:
RTN PC5, PAGE< PD3, PAGE> PD7, TELE PD2, SYS PE10 (not Pocket PB4), MDL PE11.
Enter, trims and rotary remain disabled to preserve SWD and avoid unwired
inputs. The ADC/gimbal pin relocation to PC1/PC2 is not implemented yet.
USB CLI logs debounced physical key transitions automatically. `buttons`
or `buttons on` prints all six states and enables change logs; `buttons off`
disables logs. Each key must be stable for 30 ms; physical-key sampling is
performed in the CLI task with a 10 ms receive timeout. Long CLI commands
can delay sampling. Log output is not retained for later terminal connections.
Normal EdgeTX key processing remains separate from the CLI log filter.
Power-button handling is bypassed; this configuration does not implement the
discussed external latch shutdown workflow. USB presence is assumed because
the board lacks the Pocket PA9 VBUS-sense connection. BOR option bytes are
not automatically modified. USB-powered and externally powered 5 V rails
must be isolated before combining supplies on the DevEBox board.

## Checkpoint: physical navigation keys verified (2026-10-17)

The user supplied USB CDC logs showing PRESSED GPIO=0 and RELEASED GPIO=1
for all six wired keys: RTN PC5, PAGE> PD7, PAGE< PD3, TELE PD2, SYS PE10,
and MDL PE11. This confirms the physical inputs and CLI transition reporting;
the host test suite also checks GPIO mapping, independent debounce, simultaneous
transitions and timer wrap. Holding a key does not repeatedly print changes.

Next wiring plan, **not enabled by this checkpoint**:

| Input | DevEBox pin |
| --- | --- |
| Rotary contact A | PE9 |
| Rotary contact B | PE14 |
| Rotary common C | GND |
| Separate Enter switch | PD14 to GND, pull-up to 3.3 V |

Do not use PE10 for rotary B: SYS now occupies that pin. Do not use PA13
for Enter: retain SWDIO. The planned rotary B relocation needs matching
GPIO, position-bit extraction and EXTI configuration changes before enabling
the encoder. Enter also needs a driver update. A bare mechanical encoder
requires no VCC connection; verify A/B/common and any independent switch
with its datasheet or a continuity meter before soldering. Two mounting tabs
are not automatically electrical common contacts.

## Encoder and Enter enabled

After the six-key checkpoint, enable Enter PD14 and rotary PE9/PE14.
Override rotary B's GPIO, EXTI line, SYSCFG line and packed position bits;
PE10 remains SYS. Reuse the EdgeTX EXTI/timer decoder with granularity 2,
including its suppression of rotary increments while Enter is held.
Keep trims disabled and preserve PA13/PA14 SWD. The planned gimbal ADC
relocation remains unimplemented.

`buttons`/`buttons on` now snapshots seven keys plus the encoder. Automatic
`[ENC]` logs show sampled A/B electrical levels, signed count delta and the
decoded counter. `encoder` requests an immediate snapshot; `buttons off`
stops automatic key and encoder logs. A/B log sampling occurs in the CLI
task (10 ms receive timeout), so it may skip intermediate states during fast
rotation or long CLI commands. Interrupt-based decoding remains independent
of this log sampling. Key logs retain 30 ms filtering; A/B do not use that
filter. Update the application only using the existing software DFU loader.

### Hardware checkpoint — 2026-10-17

The user confirmed rotary operation after the first change of encoder wiring.
The initial assumption that the middle terminal was common was incorrect;
the original logs showed only AB=11/10/00 and a count alternating between
0 and 1 while turning in one direction. Keep MCU A=PE9 and B=PE14, with
the actual encoder common connected to GND and separate pull-ups to 3.3 V.
The exact physical terminal order has not been recorded; do not infer it
from the encoder housing. Direction, counts per detent and Enter hardware
validation should be recorded separately when confirmed.
