"""
The line based serial protocol spoken by firmware/skinny-lora/skinny-lora.ino
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Optional, Union

PACKET_START = "----------------- Start PACKET -----------------"
PACKET_END = "----------------- End PACKET -----------------"

HEX_LINE = re.compile(r"[0-9A-Fa-f]{2}( [0-9A-Fa-f]{2})*")
PRINTABLE = set(string.printable.encode()) - set(b"\t\n\r\x0b\x0c")

# App command -> firmware setting
SETTINGS = {
    "freq": "FREQ",
    "sf": "SF",
    "bw": "BW",
    "cr": "CR",
    "power": "PWR",
    "raw": "RAW",
    "lbt": "LBT",
    "crc": "CRC",
}
ON_OFF_SETTINGS = {"raw", "lbt", "crc"}

HELP = """Type a message and press Enter to transmit it. App commands:
  /hex DEADBEEF        Transmit raw bytes (spaces and colons are allowed)
  /replay              Transmit the bytes of the last received packet again
  /status              Show the radio settings and packet counters
  /freq 915.0          Frequency in MHz
  /sf 7                Spreading factor, 7 to 12
  /bw 125000           Bandwidth in Hz
  /cr 5                Coding rate 4/5 to 4/8
  /power 20            Transmit power, 2 to 20 dBm
  /raw on|off          Raw mode: show and send the 4 RadioHead header bytes, receive every packet
  /lbt on|off          Listen before talk: wait for a clear channel before transmitting
  /crc on|off          Off accepts (and sends) packets without a CRC
  /help                Show this help
  /quit                Exit
Start a message with // to transmit text that begins with /"""


class CommandError(ValueError):
    """The user typed an app command that can't be sent."""


class _Action:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


SHOW_HELP = _Action("help")
QUIT = _Action("quit")


@dataclass
class Packet:
    data: bytes
    rssi: Optional[int] = None
    snr: Optional[int] = None
    device_ms: Optional[int] = None

    @property
    def text(self) -> str:
        """Payload as text the way the firmware shows it: no trailing NULs, '.' for unprintable bytes"""
        data = self.data.rstrip(b"\x00")
        return "".join(chr(b) if b in PRINTABLE else "." for b in data)

    @property
    def hex(self) -> str:
        return " ".join(f"{b:02X}" for b in self.data)


class PacketParser:
    """
    Turns the firmware's packet blocks back into Packet objects, one line at a time
    """

    def __init__(self) -> None:
        self._in_packet = False
        self._reset()

    def _reset(self) -> None:
        self._data = bytearray()
        self._in_hex = False
        self._rssi: Optional[int] = None
        self._snr: Optional[int] = None
        self._device_ms: Optional[int] = None

    def feed(self, line: str) -> Optional[Packet]:
        line = line.strip()
        if line == PACKET_START:
            self._in_packet = True
            self._reset()
            return None
        if not self._in_packet:
            return None
        if line == PACKET_END:
            self._in_packet = False
            return Packet(bytes(self._data), self._rssi, self._snr, self._device_ms)

        if line.startswith("Received:"):
            self._in_hex = True
            return None
        if self._in_hex and HEX_LINE.fullmatch(line):
            self._data.extend(bytes.fromhex(line))
            return None
        self._in_hex = False

        key, _, value = line.partition(":")
        try:
            if key == "RSSI":
                self._rssi = int(value)
            elif key == "SNR":
                self._snr = int(value)
            elif key == "Time":
                self._device_ms = int(value.split()[0])
        except (ValueError, IndexError):
            pass
        return None


def parse_status(line: str) -> Optional[dict]:
    """Parse a 'STATUS key=value ...' line from the firmware"""
    if not line.startswith("STATUS "):
        return None
    return dict(field.split("=", 1) for field in line.split()[1:] if "=" in field)


def parse_hex(text: str) -> bytes:
    cleaned = text.replace(" ", "").replace(":", "")
    try:
        data = bytes.fromhex(cleaned)
    except ValueError:
        raise CommandError("Hex must be pairs of hex digits, e.g. /hex DE AD BE EF") from None
    if not data:
        raise CommandError("Nothing to transmit, e.g. /hex DE AD BE EF")
    return data


def hex_command(data: bytes) -> str:
    # No separators, so it also fits the smaller line buffer on the Feather 32u4
    return "HEX:" + data.hex().upper()


def setting_command(name: str, value: str) -> str:
    if name in ON_OFF_SETTINGS:
        value = value.lower()
        if value in ("on", "1", "true", "yes"):
            value = "1"
        elif value in ("off", "0", "false", "no"):
            value = "0"
        else:
            raise CommandError(f"Use /{name} on or /{name} off")
    elif not value:
        raise CommandError(f"/{name} needs a value, e.g. /{name} {example_value(name)}")
    return f"{SETTINGS[name]}:{value}"


def example_value(name: str) -> str:
    return {"freq": "915.0", "sf": "7", "bw": "125000", "cr": "5", "power": "20"}.get(name, "on")


def to_serial(text: str, last_packet: Optional[Packet] = None) -> Union[str, _Action, None]:
    """
    Translate what the user typed into a line for the firmware,
    or SHOW_HELP / QUIT, or None when there is nothing to do
    """
    if not text:
        return None
    if text.startswith("//"):
        return "TX:" + text[1:]
    if not text.startswith("/"):
        return "TX:" + text

    name, _, arg = text[1:].partition(" ")
    name = name.lower()
    arg = arg.strip()
    if name in ("help", "?"):
        return SHOW_HELP
    if name in ("quit", "exit"):
        return QUIT
    if name == "status":
        return "STATUS"
    if name == "hex":
        return hex_command(parse_hex(arg))
    if name == "replay":
        if last_packet is None:
            raise CommandError("Nothing has been received yet")
        if not last_packet.data:
            raise CommandError("The last packet was empty")
        return hex_command(last_packet.data)
    if name in SETTINGS:
        return setting_command(name, arg)
    raise CommandError(f"Unknown command /{name}, type /help for the list")
