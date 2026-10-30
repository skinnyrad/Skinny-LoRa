#!/usr/bin/env python3
"""
Run the Skinny-LoRa terminal straight from a checkout:

    python3 skinny-lora.py -p /dev/ttyACM0

After `pip install .` the same app is available as the `skinny-lora` command.
"""
from skinny_lora.cli import main

if __name__ == "__main__":
    main()
