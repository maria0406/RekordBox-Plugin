# Phrase Countdown Light firmware

Firmware for a Seeed Studio XIAO ESP32C3 that drives a 16-LED WS2812B ring.
The ring counts down the last 8 bars before each cue Set Prep Copilot placed.
All timing happens on the laptop. The board draws whatever the last serial line said.

## Build and flash

You need [PlatformIO](https://platformio.org/) (`pip install platformio`, or the VS Code extension).

```bash
cd hardware/countdown-light/firmware
pio run                      # build
pio run -t upload            # flash over USB-C
pio device monitor           # type ? and Enter; expect: HELLO pcl 1
```

If the upload can't find the board, hold BOOT, tap RESET, then release BOOT
to put the XIAO into download mode, and upload again.

## Wiring

| XIAO pin | GPIO | Goes to |
| --- | --- | --- |
| D10 | GPIO10 | SN74AHCT125 pin 2 (1A). Pin 3 (1Y) goes through 330 Ω to the ring's DIN. |
| D1 | GPIO3 | SW1 to GND (uses the internal pull-up) |
| 5V | USB VBUS | Ring 5V, SN74AHCT125 pin 14 |
| GND | — | Ring GND, SN74AHCT125 pins 1 and 7 |

GPIO2, 8 and 9 are boot strapping pins on the ESP32-C3, so they aren't used.

If 12 o'clock or the direction looks wrong after mounting, change `RING_TOP`
and `RING_CLOCKWISE` in `src/main.cpp`.

## Serial protocol

The protocol is USB CDC, one ASCII line per message, ending in `\n`. The baud rate is ignored.

| Direction | Line | Meaning |
| --- | --- | --- |
| board → laptop | `HELLO pcl 1` | On boot and in reply to `?`. `1` is the protocol version. |
| laptop → board | `?` | Who are you? |
| laptop → board | `C <ms_to_cue> <ms_per_beat> <rrggbb>` | Next cue: ms away (negative after it passes), beat length, color. `C 15000 469 00FF00` = MIX IN in 8 bars at 128 BPM. |
| laptop → board | `I` | Idle: nothing to count down |
| laptop → board | `B <0-255>` | Brightness for the countdown, saved to flash |
| board → laptop | `K <0-255>` | SW1 changed the brightness |
| board → laptop | `ERR <line>` | The board didn't understand the line and ignored it |

`ms_per_beat` must be 100 to 2000 (30 to 600 BPM). The laptop should send a
line about 10 times a second. If no line arrives for 2 s, the ring breathes
dim white to show the link is lost.

## What the ring shows

| Time to cue | Ring |
| --- | --- |
| More than 8 bars, or `I` | One dim white LED at 12 o'clock |
| 8 bars to 1 bar | The cue's color, one LED going out every 2 beats, clockwise from 12 o'clock |
| Last bar | The last 2 LEDs, plus the whole ring pulsing on each beat |
| The cue (1 beat) | Full ring at full brightness, with the current cap applied |
| The bar after the cue | Fades out |
| No line for 2 s | Slow dim white breathing |

**Self-test:** hold SW1 while plugging in. One LED walks round the ring in red,
then green, then blue, and the whole ring lights after each color.

**Brightness:** press SW1 to step through 10, 20, 40, 60, 80 and 100%.

## Power-up

USB 2.0 allows only 100 mA until the host configures the device, so the ring
stays dark until then, self-test included. The ESP32-C3's USB Serial/JTAG is
fixed hardware and doesn't tell the firmware when it has been configured. The
board treats USB as ready after 1 s of host SOF frames
(`HWCDC::isPlugged()`), or as soon as serial data moves. While dark, the board
draws about 46 mA: 28 mA for the ESP32-C3, about 1.5 mA for the AHCT125 and
about 16 mA for the idle LEDs.

## Power cap

Before each frame, the firmware estimates the ring's current as
Σ (R+G+B)/255 × 20 mA. If that is over 300 mA, it scales the frame down, so the
LEDs stay inside a 500 mA USB port. Worldsemi's datasheet lists 16 mA per
channel, so 20 mA errs on the safe side. Check the real draw with a USB meter.

## Bench test

```bash
pip install pyserial
python ../tools/bench_countdown.py --bpm 128
python ../tools/bench_countdown.py --silent-after 20   # link-loss test
```
