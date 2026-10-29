import asyncio
import queue
import sys
import threading
import serial
import argparse
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

BAUD_RATE = 115200  # Must match Serial.begin() in skinny-lora.ino

txQueue = queue.Queue()
disconnected = threading.Event()
shuttingDown = threading.Event()


def serial_monitor(ser, loop, session):
    """
    Thread that monitors the serial port and sends queued commands
    """
    try:
        while True:
            try:
                cmd = txQueue.get_nowait()
                ser.write(("TX:" + cmd + "\n").encode())
            except queue.Empty:
                line = ser.readline()   # read a '\n' terminated line
                if line:
                    print(line.decode('utf-8', errors='replace').rstrip('\r\n'))
    except (serial.SerialException, OSError) as e:
        if shuttingDown.is_set():   # Port was closed because we are exiting
            return
        print("Lost connection to the device: " + str(e))
        disconnected.set()
        loop.call_soon_threadsafe(exit_prompt, session)


def exit_prompt(session):
    if session.app.is_running:
        session.app.exit(exception=EOFError())


async def interactive_shell(session):
    """
    Skinny-LoRa interactive shell
    """
    while not disconnected.is_set():
        try:
            result = await session.prompt_async()
        except (EOFError, KeyboardInterrupt):
            return
        if result:
            txQueue.put(result)
            print("Transmitting: " + result)


async def main(ser):
    session = PromptSession("SkinnyLoRa> Enter a Command To Transmit: ")
    with patch_stdout():
        thread = threading.Thread(target=serial_monitor, args=(ser, asyncio.get_running_loop(), session))
        thread.daemon = True
        thread.start()
        try:
            await interactive_shell(session)
        finally:
            shuttingDown.set()
            print("Exiting...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='SkinnyLoRa Version 0.1', description='Transmits and Receives LoRa Traffic.  Defaults to Receive Mode')
    parser.add_argument('-p', '--port', help='The serial port to attach to', required=True)
    args = parser.parse_args()
    try:
        ser = serial.Serial(args.port, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print("Could not connect to the device: " + str(e))
        sys.exit(1)
    with ser:
        asyncio.run(main(ser))
    sys.exit(1 if disconnected.is_set() else 0)
