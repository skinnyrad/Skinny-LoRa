"""
Saving received packets to CSV or JSON Lines
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime

from .protocol import Packet

FIELDS = ["time", "device_ms", "length", "rssi", "snr", "hex", "text"]


class PacketLog:
    """Appends one row per packet. Files ending in .jsonl or .json get JSON Lines, anything else CSV."""

    def __init__(self, path: str):
        self.path = path
        self.json = path.lower().endswith((".jsonl", ".json"))
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        self._file = open(path, "a", newline="", encoding="utf-8")
        if not self.json:
            self._csv = csv.DictWriter(self._file, fieldnames=FIELDS)
            if is_new:
                self._csv.writeheader()

    def write(self, packet: Packet) -> None:
        row = {
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "device_ms": packet.device_ms,
            "length": len(packet.data),
            "rssi": packet.rssi,
            "snr": packet.snr,
            "hex": packet.hex,
            "text": packet.text,
        }
        if self.json:
            self._file.write(json.dumps(row) + "\n")
        else:
            self._csv.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()
