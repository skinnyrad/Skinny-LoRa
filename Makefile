FQBN ?= adafruit:samd:adafruit_feather_m0
PORT ?=
RADIOHEAD_VERSION ?= 1.143.1
ADAFRUIT_INDEX = https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
SKETCH = firmware/skinny-lora

.PHONY: deps compile upload install test

# Board support for the Feather M0 and 32u4, and the RadioHead library
deps:
	arduino-cli core update-index --additional-urls $(ADAFRUIT_INDEX)
# The Adafruit cores build on top of Arduino's, which arduino-cli does not pull in by itself
	arduino-cli core install arduino:avr arduino:samd adafruit:avr adafruit:samd --additional-urls $(ADAFRUIT_INDEX)
	arduino-cli lib install RadioHead@$(RADIOHEAD_VERSION)

compile:
	arduino-cli compile --fqbn $(FQBN) --warnings all $(SKETCH)

# make upload PORT=/dev/ttyACM0
upload:
	@test -n "$(PORT)" || (echo "Set PORT, e.g. make upload PORT=/dev/ttyACM0 (arduino-cli board list shows it)"; exit 1)
	arduino-cli compile --upload --fqbn $(FQBN) -p $(PORT) $(SKETCH)

install:
	python3 -m pip install -e '.[dev]'

test:
	python3 -m pytest
