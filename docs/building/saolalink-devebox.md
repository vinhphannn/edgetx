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

## Four Hall gimbals and USB ADC logs — 2026-10-19

The DevEBox profile now uses LH=PA3/ADC1_IN3, LV=PA2/ADC1_IN2,
RV=PC1/ADC1_IN11 and RH=PC2/ADC1_IN12. CMake derives a separate ADC JSON
from the SaolaLink baseline and generates both conversion channels and analog
GPIO initialization from it. The non-DevEBox baseline remains unchanged.
PA0 remains the recovery key and PA1 the heartbeat LED. Trims stay disabled,
so PC1/PC2 are not initialized as digital buttons. The previous sections
describe earlier checkpoints; the ADC relocation is now implemented.

`[JOY]` logs start automatically when a CLI connection is available. `joy`
or `joy on` prints all four values and enables reporting; `joy off` disables
only these logs. Values are 12-bit ADC (0..4095), before calibration but
with the baseline LH/RH inversion retained. Changes accumulate against the
last reported value, with a threshold of 16 counts and a minimum polling
interval of 50 ms. This is a reporting filter only; ADC acquisition and mixer
processing are unchanged. Long CLI commands can delay logging. Button and
encoder logging remain independent. The user must verify axis directions,
travel and noise on hardware. Flash the application with the existing USB
bootloader; no bootloader update is required for this change.

Host regression checks (using the build Python environment):
`python -m unittest discover -s radio/util/tests -p test_saolalink_devebox.py -v`.

## External power latch PD0/PD1 — 2026-10-19

The application now asserts PD0 HIGH in pwrInit before LCD/SD initialization.
PD0 drives the external latch's NPN through its base resistor. PD1 is an
active-low input with pull-up, connected only to the isolated 3.3 V button
sense branch. Do not connect the MOSFET gate or battery voltage to a GPIO.
The startup button hold is ignored until a release has been stable for 30 ms;
later presses are debounced for 30 ms. The default shutdown delay is 2 seconds.
Normal EdgeTX shutdown closes logs and unmounts SD, then boardOff waits for
button release before lowering HOLD. Keep the button held until boot/display
startup completes. This development profile still uses volatile defaults:
shutdown does not persist those defaults over existing RADIO/MODELS files.

Automatic `[PWR]` logs show the button and HOLD level. `power` / `power on`
prints a snapshot and enables logging; `power off` only disables logging,
not physical power control. The existing bootloader remains compatible;
upload only the application for this change. The user has confirmed the four
gimbal inputs work. Following the battery/FET power-test instructions, the
user reported successful operation and requested this checkpoint. The USB
log also showed a 2.49-second PD1 press, release, ENTER confirmation and
subsequent USB disconnection. No scope traces or voltage measurements were
provided. Firmware build and all 26 host checks passed for this checkpoint.

The USB stack still starts without PA9 VBUS sensing. For the shutdown USB
confirmation only, use USB configured state instead of the always-present
development fallback. A connected USB host can require ENTER confirmation;
this is not a USB voltage/charger detector. USB 5 V can keep the MCU powered
after HOLD goes LOW. Isolate USB and external buck 5 V before combining
supplies on a board without reverse-current protection. RF remains disabled.

## Internal CRSF enabled — 2026-10-20

This supersedes the earlier RF-disabled checkpoints. Internal RF defaults to
CRSF at 400000 baud, normal 8N1, PB6 TX to module RX, PB7 RX from module TX,
and PC4 active-high power enable. External RF remains disabled. The DevEBox
build keeps only internal CRSF rather than internal MULTI. Settings remain
volatile; reboot returns to internal RF ON. Attach the correct antenna and
supply the original Pocket ELRS module from the switched 5 V rail.

BOOT circuitry has not been verified: PB1 is an input with no pull resistor,
and the bootcmd callback is removed. This avoids clamping a directly connected
ESP32 GPIO0 low. The module must retain its normal-run strap; HI_Z does not
create a missing strap. The installed bootloader can briefly drive PB1 low
before jumping, so hardware must keep RF off until application startup. The
application releases PB1 before starting RF. No bootloader update is needed.

USB CLI `rf` / `rf status` prints diagnostics; `rf on` / `rf off` changes
the model via the normal mixer/module lifecycle, asynchronously. `rf watch
on` / `rf watch off` only changes logging. Logs report changes and periodic
2-second statistics while powered. PC4 is a command/pin state, not a measured
module rail. UART READY means initialized; txq counts UART buffer handoffs,
not acknowledgements or RF emission. RX bytes and CRC-valid frames are counted
separately. CRSF_RX requires a valid frame within 2 seconds; otherwise WAIT_RX,
BAD_RX or STALE explains what was seen. Device Info reports module name and
ELRS version independently of receiver telemetry/binding. No printing occurs
in protocol/ISR paths. Hardware communication still needs user verification.

RF host regression checks: `python -m unittest discover -s radio/util/tests
-p 'test_saolalink*.py' -v` covers parser fragmentation, CRC rejection,
resynchronization, external isolation, UART handoff counts, session reset,
timeouts and tick wrap, alongside the gimbal/power checks.

## RF hardware checkpoint and next wiring — 2026-10-21

The user reports the RF power circuit works after correcting miswired
component pins. The earlier log (87 RX bytes, 7 CRC-valid frames, then STALE)
was captured without module power; it does not verify module identification
or sustained two-way communication. No new Device Info/binding log or rail
measurements have been supplied for this checkpoint. PC4 HIGH enables the
NPN/PMOS power switch; supply the module from switched 5 V, not raw 2S.

The generated DevEBox switch table already initializes these inputs with
internal pull-ups. They retain the Pocket mapping and do not overlap the
currently wired menu keys, encoder, gimbals, SD, OLED or internal RF:

| Input | MCU pin(s) | Wiring |
| --- | --- | --- |
| SA, 2-position | PC13 | Contact between pin and GND |
| SB, 3-position | PA5 and PE15 | ON-OFF-ON common to GND, throws to the two pins |
| SC, 3-position | PD11 and PE0 | ON-OFF-ON common to GND, throws to the two pins |
| SD, 2-position | PE8 | Contact between pin and GND |
| SE, momentary/toggle | PE7 | Contact between pin and GND |
| S1 potentiometer | PB0, ADC1_IN8 | Track ends to 3V3_MCU/GND, wiper to PB0 |

For switches, an external 10 kOhm pull-up per signal to 3V3_MCU is suitable
for the prototype wiring. With a 220 Ohm series resistor, put the pull-up
on the MCU side. A 3-position switch has both inputs HIGH at center and
one LOW at either end. Use an actual center-off switch; determine common
by continuity, not by assuming the middle physical pin. On a 2-position
SPDT switch use common and one throw, leaving the other throw unconnected.
Do not connect a throw directly to 3V3.

S1 is analog: no pull-up or pull-down. A linear 10 kOhm potentiometer is
appropriate; an optional 100 nF capacitor goes from PB0 to GND near the
MCU. Reversing the two track ends reverses direction. The inherited P1
mapping also inverts its ADC reading. Only one potentiometer is currently
defined. CLI automatic logs cover buttons/encoder, four gimbals, power and
RF; switch/S1 change logging has not been added in this checkpoint.
