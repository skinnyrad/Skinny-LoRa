import asyncio
import threading
import serial
import argparse
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

cmdToTransmit = ""
def print_counter():
    global cmdToTransmit
    """
    Thread that monitors the serial port
    """
    try:
        while True:
            with serial.Serial(args.port, 19200, timeout=1) as ser:
                while True:
                    if cmdToTransmit != "":
                        msg = "TX:"+cmdToTransmit+" "
                        ser.write(msg.encode())
                        cmdToTransmit = ""
                    else: 
                        line = ser.readline()   # read a '\n' terminated line
                        if line:
                            print(line.decode('utf-8'))
    except:
        print("Could not connect to the device")


async def interactive_shell():
    """
    Skinny-LoRa interactive shell
    """
    # Create Prompt.
    session = PromptSession("SkinnyLoRa> Enter a Command To Transmit: ")
    global cmdToTransmit        # Define our global variable for TX
 
    while True:
        try:
            result = await session.prompt_async()
            cmdToTransmit = result
            print("Transmitting: "+result)
        except (EOFError, KeyboardInterrupt):
            return


async def main():
    with patch_stdout():
        thread = threading.Thread(target=print_counter)
        thread.daemon = True
        thread.start()
        #background_task = asyncio.create_task(print_counter())
        try:
            await interactive_shell()
        finally:
            print("Exiting...")
            exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='SkinnyLoRa Version 0.1', description='Transmits and Receives LoRa Traffic.  Defaults to Receive Mode')
    parser.add_argument('-p', '--port', help='The serial port to attach to', required=True)
    args = parser.parse_args()
    try:
        from asyncio import run
    except ImportError:
        asyncio.run_until_complete(main())
    else:
        asyncio.run(main())