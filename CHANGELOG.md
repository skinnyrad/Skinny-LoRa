# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Configuration section in skinny-lora.ino for frequency, power, bandwidth, coding rate and spreading factor

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