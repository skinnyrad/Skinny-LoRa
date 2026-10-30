"""
Finding the Feather's serial port
"""
from __future__ import annotations

from typing import List, Optional

from serial.tools import list_ports

ADAFRUIT_VID = 0x239A


class PortError(Exception):
    pass


def find_feather_ports() -> List[str]:
    return sorted(p.device for p in list_ports.comports() if p.vid == ADAFRUIT_VID)


def choose_port(requested: Optional[str]) -> str:
    """Use the port the user asked for, otherwise the only Adafruit board plugged in"""
    if requested:
        return requested
    ports = find_feather_ports()
    if not ports:
        raise PortError("No Adafruit Feather found. Plug one in or pass -p PORT.")
    if len(ports) > 1:
        raise PortError("Several Adafruit boards found, pick one with -p: " + ", ".join(ports))
    return ports[0]
