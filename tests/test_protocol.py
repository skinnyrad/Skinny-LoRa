import pytest

from skinny_lora.protocol import (
    PACKET_END,
    PACKET_START,
    QUIT,
    SHOW_HELP,
    CommandError,
    Packet,
    PacketParser,
    parse_status,
    to_serial,
)

# Captured from the firmware on a Feather M0
HELLO_BLOCK = """----------------- Start PACKET -----------------
Received:
68 65 6C 6C 6F 00
Decoded Value: hello
Length: 6
RSSI: -18
SNR: 9
Time: 10345 ms
----------------- End PACKET -----------------"""


def feed_all(parser, text):
    packets = []
    for line in text.splitlines():
        packet = parser.feed(line)
        if packet is not None:
            packets.append(packet)
    return packets


def test_parses_packet_block():
    (packet,) = feed_all(PacketParser(), HELLO_BLOCK)
    assert packet.data == b"hello\x00"
    assert packet.rssi == -18
    assert packet.snr == 9
    assert packet.device_ms == 10345
    assert packet.text == "hello"
    assert packet.hex == "68 65 6C 6C 6F 00"


def test_parses_multi_line_hex_and_ignores_other_output():
    data = bytes(range(40))
    hex_lines = [" ".join(f"{b:02X}" for b in data[i:i + 16]) for i in range(0, len(data), 16)]
    text = "\n".join(
        ["Transmitting hi", "STATUS freq=915.00", PACKET_START, "Received: ", *hex_lines,
         "Decoded Value: ........", "Length: 40", "RSSI: -40", "SNR: -3", "Time: 5 ms", PACKET_END,
         "Bad packets: 1 new, 1 total"]
    )
    (packet,) = feed_all(PacketParser(), text)
    assert packet.data == data
    assert packet.snr == -3


def test_empty_packet():
    text = "\n".join([PACKET_START, "Received: ", "Decoded Value: ", "Length: 0", "RSSI: -20", PACKET_END])
    (packet,) = feed_all(PacketParser(), text)
    assert packet.data == b""
    assert packet.text == ""


def test_hex_looking_decoded_value_is_not_data():
    text = "\n".join([PACKET_START, "Received: ", "41 42", "Decoded Value: AB", "Length: 2", PACKET_END])
    (packet,) = feed_all(PacketParser(), text)
    assert packet.data == b"AB"


def test_packet_text_matches_firmware_decoding():
    assert Packet(b"\x01ab\x7fc\x00\x00").text == ".ab.c"


def test_parse_status():
    status = parse_status("STATUS freq=915.00 sf=7 bw=125000 raw=0 version=0.2.0")
    assert status == {"freq": "915.00", "sf": "7", "bw": "125000", "raw": "0", "version": "0.2.0"}
    assert parse_status("Transmitting STATUS") is None


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("hello world", "TX:hello world"),
        ("//etc/passwd", "TX:/etc/passwd"),
        ("/status", "STATUS"),
        ("/hex de ad:BE ef", "HEX:DEADBEEF"),
        ("/freq 868.1", "FREQ:868.1"),
        ("/sf 12", "SF:12"),
        ("/bw 250000", "BW:250000"),
        ("/cr 8", "CR:8"),
        ("/power 10", "PWR:10"),
        ("/raw on", "RAW:1"),
        ("/RAW OFF", "RAW:0"),
        ("/lbt off", "LBT:0"),
        ("/crc 0", "CRC:0"),
        ("/help", SHOW_HELP),
        ("/quit", QUIT),
        ("", None),
    ],
)
def test_to_serial(typed, expected):
    assert to_serial(typed) == expected


@pytest.mark.parametrize("typed", ["/hex", "/hex ABC", "/hex zz", "/raw maybe", "/sf", "/nope"])
def test_to_serial_rejects_bad_commands(typed):
    with pytest.raises(CommandError):
        to_serial(typed)


def test_replay_resends_last_packet_bytes():
    with pytest.raises(CommandError):
        to_serial("/replay", None)
    assert to_serial("/replay", Packet(b"\xff\xff\x00\x00hi\x00")) == "HEX:FFFF0000686900"
