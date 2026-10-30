"""
Skinny-LoRa interactive terminal
"""
from __future__ import annotations

import argparse
import asyncio
import os
import queue
import sys
import threading
from typing import Callable, List, Optional

import serial
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

from . import __version__
from .packetlog import PacketLog
from .ports import PortError, choose_port
from .protocol import HELP, QUIT, SHOW_HELP, CommandError, PacketParser, parse_status, setting_command, to_serial

BAUD_RATE = 115200  # Must match Serial.begin() in skinny-lora.ino
READ_TIMEOUT = 0.05  # Short so queued commands are written promptly
STATUS_WAIT = 3.0  # Seconds to wait for the firmware to answer STATUS
DEFAULT_HISTORY = os.path.join(os.path.expanduser("~"), ".skinny_lora_history")


class SerialWorker(threading.Thread):
    """
    Thread that monitors the serial port and sends queued commands
    """

    def __init__(self, ser, on_line: Callable[[str], None], on_disconnect: Callable[[Exception], None]):
        super().__init__(daemon=True)
        self.ser = ser
        self.on_line = on_line
        self.on_disconnect = on_disconnect
        self.tx_queue: "queue.Queue[str]" = queue.Queue()
        self.stopping = threading.Event()

    def send(self, line: str) -> None:
        self.tx_queue.put(line)

    def stop(self) -> None:
        self.stopping.set()

    def run(self) -> None:
        try:
            while not self.stopping.is_set():
                try:
                    cmd = self.tx_queue.get_nowait()
                    self.ser.write((cmd + "\n").encode())
                except queue.Empty:
                    line = self.ser.readline()   # read a '\n' terminated line
                    if line:
                        self.on_line(line.decode("utf-8", errors="replace").rstrip("\r\n"))
        except (serial.SerialException, OSError) as e:
            if not self.stopping.is_set():   # Port was closed because we are exiting
                self.on_disconnect(e)


class App:
    def __init__(self, ser, log: Optional[PacketLog], history: Optional[str]):
        self.parser = PacketParser()
        self.last_packet = None
        self.log = log
        self.status_seen = threading.Event()
        self.disconnected = threading.Event()
        self.session = PromptSession("SkinnyLoRa> ", history=FileHistory(history) if history else None)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.worker = SerialWorker(ser, self.on_line, self.on_disconnect)

    def on_line(self, line: str) -> None:
        print(line)
        if parse_status(line) is not None:
            self.status_seen.set()
        packet = self.parser.feed(line)
        if packet is not None:
            self.last_packet = packet
            if self.log:
                self.log.write(packet)

    def on_disconnect(self, e: Exception) -> None:
        print("Lost connection to the device: " + str(e))
        self.disconnected.set()
        if self.loop:
            self.loop.call_soon_threadsafe(self.exit_prompt)

    def exit_prompt(self) -> None:
        if self.session.app.is_running:
            self.session.app.exit(exception=EOFError())

    async def check_firmware(self) -> None:
        await asyncio.sleep(STATUS_WAIT)
        if not self.status_seen.is_set() and not self.disconnected.is_set():
            print("Warning: the device did not answer STATUS. Settings, /hex, /replay and logging need "
                  "firmware 0.2.0 or newer, flash firmware/skinny-lora/skinny-lora.ino.")

    async def shell(self) -> None:
        while not self.disconnected.is_set():
            try:
                text = await self.session.prompt_async()
            except (EOFError, KeyboardInterrupt):
                return
            try:
                cmd = to_serial(text.strip(), self.last_packet)
            except CommandError as e:
                print(e)
                continue
            if cmd is SHOW_HELP:
                print(HELP)
            elif cmd is QUIT:
                return
            elif cmd:
                self.worker.send(cmd)

    async def run(self, startup: List[str]) -> None:
        self.loop = asyncio.get_running_loop()
        with patch_stdout():
            print("Connected. Type a message to transmit it, or /help for commands.")
            self.worker.start()
            for cmd in startup:
                self.worker.send(cmd)
            checker = asyncio.ensure_future(self.check_firmware())
            try:
                await self.shell()
            finally:
                checker.cancel()
                self.worker.stop()
                print("Exiting...")


def startup_commands(args: argparse.Namespace) -> List[str]:
    """Settings given on the command line, applied in this order, then a STATUS check"""
    cmds = []
    for name in ("freq", "sf", "bw", "cr", "power"):
        value = getattr(args, name)
        if value is not None:
            cmds.append(setting_command(name, str(value)))
    if args.raw:
        cmds.append(setting_command("raw", "on"))
    if args.no_lbt:
        cmds.append(setting_command("lbt", "off"))
    if args.no_crc:
        cmds.append(setting_command("crc", "off"))
    cmds.append("STATUS")
    return cmds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skinny-lora",
        description="Transmits and Receives LoRa Traffic.  Defaults to Receive Mode",
    )
    parser.add_argument("-p", "--port", help="The serial port to attach to (default: the only Adafruit board plugged in)")
    parser.add_argument("--freq", type=float, help="Frequency in MHz, e.g. 915.0")
    parser.add_argument("--sf", type=int, help="Spreading factor, 7 to 12")
    parser.add_argument("--bw", type=int, help="Bandwidth in Hz, e.g. 125000")
    parser.add_argument("--cr", type=int, help="Coding rate denominator, 5 to 8")
    parser.add_argument("--power", type=int, help="Transmit power, 2 to 20 dBm")
    parser.add_argument("--raw", action="store_true", help="Raw mode: receive every packet including the 4 RadioHead header bytes")
    parser.add_argument("--no-lbt", action="store_true", help="Transmit without waiting for a clear channel")
    parser.add_argument("--no-crc", action="store_true", help="Accept and send packets without a CRC")
    parser.add_argument("--log", metavar="FILE", help="Append received packets to FILE (.csv, or .jsonl for JSON Lines)")
    parser.add_argument("--history", metavar="FILE", default=DEFAULT_HISTORY,
                        help="Command history file (default: ~/.skinny_lora_history), pass '' to disable")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        port = choose_port(args.port)
        ser = serial.Serial(port, BAUD_RATE, timeout=READ_TIMEOUT)
    except (PortError, serial.SerialException) as e:
        print("Could not connect to the device: " + str(e))
        sys.exit(1)

    log = PacketLog(args.log) if args.log else None
    print(f"skinny-lora {__version__} on {port}" + (f", logging to {args.log}" if log else ""))
    app = App(ser, log, args.history or None)
    try:
        with ser:
            asyncio.run(app.run(startup_commands(args)))
    finally:
        if log:
            log.close()
    sys.exit(1 if app.disconnected.is_set() else 0)


if __name__ == "__main__":
    main()
