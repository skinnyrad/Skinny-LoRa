import csv
import json

from skinny_lora.packetlog import PacketLog
from skinny_lora.protocol import Packet

PACKET = Packet(b"hi\x00", rssi=-20, snr=8, device_ms=1234)


def test_csv_log_appends_with_one_header(tmp_path):
    path = str(tmp_path / "packets.csv")
    for _ in range(2):
        log = PacketLog(path)
        log.write(PACKET)
        log.close()

    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["hex"] == "68 69 00"
    assert rows[0]["text"] == "hi"
    assert rows[0]["rssi"] == "-20"
    assert rows[0]["length"] == "3"


def test_jsonl_log(tmp_path):
    path = str(tmp_path / "packets.jsonl")
    log = PacketLog(path)
    log.write(PACKET)
    log.close()

    (row,) = [json.loads(line) for line in open(path)]
    assert row["hex"] == "68 69 00"
    assert row["snr"] == 8
    assert row["device_ms"] == 1234
