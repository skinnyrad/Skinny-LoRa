import threading
import time

import serial

from skinny_lora.cli import SerialWorker, build_parser, startup_commands


class FakeSerial:
    """Hands out the given lines, then times out like a real port, or fails when fail_after is reached"""

    def __init__(self, lines, fail_after=None):
        self.lines = list(lines)
        self.written = []
        self.fail_after = fail_after
        self.reads = 0

    def write(self, data):
        self.written.append(data)

    def readline(self):
        self.reads += 1
        if self.fail_after is not None and self.reads > self.fail_after:
            raise serial.SerialException("device disconnected")
        if self.lines:
            return self.lines.pop(0)
        time.sleep(0.01)
        return b""


def wait_for(condition, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_worker_reads_lines_and_writes_commands():
    ser = FakeSerial([b"Welcome\r\n", b"STATUS sf=7\r\n"])
    lines = []
    worker = SerialWorker(ser, lines.append, lambda e: None)
    worker.start()
    worker.send("TX:hello")
    assert wait_for(lambda: len(lines) == 2 and ser.written)
    worker.stop()
    worker.join(1)
    assert lines == ["Welcome", "STATUS sf=7"]
    assert ser.written == [b"TX:hello\n"]


def test_worker_reports_disconnect():
    disconnected = threading.Event()
    worker = SerialWorker(FakeSerial([], fail_after=1), lambda line: None, lambda e: disconnected.set())
    worker.start()
    assert disconnected.wait(2)


def test_worker_quiet_when_stopping():
    disconnected = threading.Event()
    ser = FakeSerial([], fail_after=5)
    worker = SerialWorker(ser, lambda line: None, lambda e: disconnected.set())
    worker.stop()
    worker.start()
    worker.join(1)
    assert not disconnected.is_set()


def test_startup_commands_from_options():
    args = build_parser().parse_args(["--freq", "868.1", "--sf", "9", "--raw", "--no-lbt", "--no-crc"])
    assert startup_commands(args) == ["FREQ:868.1", "SF:9", "RAW:1", "LBT:0", "CRC:0", "STATUS"]


def test_startup_commands_default():
    assert startup_commands(build_parser().parse_args([])) == ["STATUS"]
