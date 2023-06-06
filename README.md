# Skinny-LoRa

Skinny-LoRa is a terminal application for transmitting and receiving LoRa traffic using a single Adafruit Feather M0 with RFM95 LoRa Radio.

![skinny-lora](./img/skinny-lora.gif)

# Setup

### 1. Install the necessary libraries for the Adafruit Feather M0 with RFM95 LoRa Radio:

* https://learn.adafruit.com/adafruit-feather-m0-radio-with-lora-radio-module/setup
* https://learn.adafruit.com/adafruit-feather-m0-radio-with-lora-radio-module/using-with-arduino-ide

### 2. Flash the Adafruit Feather M0:

* Open the skinny-lora.ino file in Arduino IDE
* Select Tools -> Board -> Adafruit SAMD Boards -> Adafruit Feather M0 (SAMD21)
* Select Tools -> Port -> [Your Adafruit Feather M0]
* Select Sketch -> Include Library -> Add .Zip Library -> Select the RadioHead.zip file from this repository
* Click the Upload Button


### 3. Install the python3 requirements from this repository:

```
$ pip install -r requirements.txt
```

# Running the Application

```
$ python3 skinny-lora.py -h

usage: SkinnyLoRa Version 0.1 [-h] -p PORT

Transmits and Receives LoRa Traffic. Defaults to Receive Mode

options:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  The serial port to attach to
```

The only required option is the serial port to attach to.  This should be the serial port of the Adafruit Feather M0 on your machine.  By default the application will run in receive mode and stream packets in the background until you enter data to transmit.  Once the application transmits the packet, it will immediately return to streaming LoRa packets:

```
$ python3 skinny-lora.py -p /dev/ttyACM0


----------------- Start PACKET -----------------

Received:

50 61 72 6B 69 6E 67 20 54 69 74 61 6E 20 56 65

72 73 69 6F 6E 20 33 2E 38 2E 37 20 2D 20 4D 65

74 65 72 2D 31 0

Decoded Value: Parking Titan Version 3.8.7 - Meter-1

RSSI: -30

----------------- End PACKET -----------------

SkinnyLoRa> Enter a Command To Transmit: Meter-1 get-status
Transmitting: Meter-1 get-status
Meter-1 get-status

----------------- Start PACKET -----------------

Received:

4D 65 74 65 72 2D 31 20 53 74 61 74 75 73 3A 20

41 63 74 69 76 65 20 69 6E 20 42 72 6F 61 64 63

61 73 74 20 4D 6F 64 65 0

Decoded Value: Meter-1 Status: Active in Broadcast Mode

RSSI: -30

----------------- End PACKET -----------------
```