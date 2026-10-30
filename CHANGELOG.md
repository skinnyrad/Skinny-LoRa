# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Configuration section in skinny-lora.ino for frequency, power, bandwidth, coding rate and spreading factor
- Firmware commands to change frequency, spreading factor, bandwidth, coding rate and power at runtime (`FREQ:`, `SF:`, `BW:`, `CR:`, `PWR:`) and a `STATUS` command
- Raw mode (`RAW:1`): receive every packet including the 4 RadioHead header bytes, and transmit headers as given
- `HEX:` command to transmit arbitrary bytes
- Listen before talk (`LBT:`), on by default
- `CRC:` setting to accept and send packets without a CRC
- Packet length, SNR and device time on every received packet, and a periodic count of bad packets
- Terminal app commands `/hex`, `/replay`, `/status`, `/freq`, `/sf`, `/bw`, `/cr`, `/power`, `/raw`, `/lbt`, `/crc`, `/help`, `/quit`
- Terminal app options for every radio setting, `--log` to save packets as CSV or JSON Lines, and persistent command history
- The serial port is detected automatically when only one Adafruit board is plugged in
- The app warns when the firmware is too old to answer `STATUS`
- `pip install .` installs a `skinny-lora` command
- Tests, a Makefile and GitHub Actions CI that compiles the firmware for the Feather M0 and 32u4

### Changed
- The sketch moved to firmware/skinny-lora/skinny-lora.ino so the Arduino tools accept it without moving it
- RadioHead is installed from the Arduino Library Manager (1.143.1) instead of the bundled RadioHead.zip (1.121)
- Received bytes are printed as two digit hex, and settings and errors are reported as `STATUS` and `ERR` lines
- The firmware no longer waits forever for a computer at power on, so it also runs from a battery
- String constants are kept in flash, leaving room for the larger buffers on the Feather 32u4
- requirements.txt allows newer versions of prompt_toolkit and pyserial
- New demo GIF and screenshots in the README showing the current app

### Fixed
- Last character of every transmitted message was dropped
- Messages over 255 bytes were silently truncated; messages over 250 bytes are now rejected with an error
- Received packets were decoded past their length, showing leftover bytes; non-printable bytes now show as `.`
- Serial input no longer blocks for 1 second per loop, so commands send immediately and incoming packets are not dropped
- skinny-lora.py now exits with an error when the serial port cannot be opened instead of showing a prompt that transmits nothing
- skinny-lora.py no longer prints a blank line after every line of device output
- skinny-lora.py now uses 115200 baud to match the firmware

## [0.1] - 2023-06-06

### Added
- Source code for the terminal application 
- Source code for the Adafruit Feather M0 RFM9X Radio
- README file