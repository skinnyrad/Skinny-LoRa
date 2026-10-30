from types import SimpleNamespace

import pytest

from skinny_lora import ports
from skinny_lora.ports import PortError, choose_port


def fake_comports(monkeypatch, devices):
    monkeypatch.setattr(ports.list_ports, "comports",
                        lambda: [SimpleNamespace(device=d, vid=v) for d, v in devices])


def test_requested_port_wins(monkeypatch):
    fake_comports(monkeypatch, [])
    assert choose_port("/dev/ttyUSB9") == "/dev/ttyUSB9"


def test_picks_the_only_feather(monkeypatch):
    fake_comports(monkeypatch, [("/dev/ttyS0", None), ("/dev/ttyACM0", 0x239A), ("/dev/ttyUSB0", 0x0403)])
    assert choose_port(None) == "/dev/ttyACM0"


def test_no_feather(monkeypatch):
    fake_comports(monkeypatch, [("/dev/ttyS0", None)])
    with pytest.raises(PortError, match="No Adafruit Feather"):
        choose_port(None)


def test_several_feathers(monkeypatch):
    fake_comports(monkeypatch, [("/dev/ttyACM1", 0x239A), ("/dev/ttyACM0", 0x239A)])
    with pytest.raises(PortError, match="/dev/ttyACM0, /dev/ttyACM1"):
        choose_port(None)
