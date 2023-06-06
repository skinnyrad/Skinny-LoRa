#include <SPI.h>
#include <RH_RF95.h>


// Check for the various typs of devices

#if defined (__AVR_ATmega32U4__)  // Feather 32u4 w/Radio
  #define RFM95_CS    8
  #define RFM95_INT   7
  #define RFM95_RST   4

#elif defined(ADAFRUIT_FEATHER_M0) || defined(ADAFRUIT_FEATHER_M0_EXPRESS) || defined(ARDUINO_SAMD_FEATHER_M0)  // Feather M0 w/Radio
  #define RFM95_CS    8
  #define RFM95_INT   3
  #define RFM95_RST   4
  
#endif

String readString;

// Frequency for transmit/receive.
#define RF95_FREQ 433.0

// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);

void setup() {

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  Serial.begin(115200);
  while (!Serial) delay(1);
  delay(100);
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  while (!rf95.init()) {
    Serial.println("LoRa radio init failed");
    while (1);
  }

  Serial.println("Welcome to the skinny-lora transceiver");
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(RF95_FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }

  Serial.print("Freq set to: "); Serial.println(RF95_FREQ);  // Default is 433.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
  rf95.setTxPower(23, false);

}


void loop() {

  String input = Serial.readString();
  if(input.substring(0,3) == "TX:"){

    String command = input.substring(3);
    Serial.println(command);
    char char_array[command.length()] = {'\0'};
    command.toCharArray(char_array, sizeof(char_array));
    rf95.send((uint8_t*)char_array, sizeof(char_array));
    rf95.waitPacketSent();
    delay(200);
  }

  if(rf95.available()) {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    if (rf95.recv(buf, &len)) {
      digitalWrite(LED_BUILTIN, HIGH);
      Serial.println("----------------- Start PACKET -----------------");
      RH_RF95::printBuffer("Received: ", buf, len);
      Serial.print("Decoded Value: ");
      Serial.println((char*)buf);
      Serial.print("RSSI: ");
      Serial.println(rf95.lastRssi(), DEC);
      Serial.println("----------------- End PACKET -----------------");
    } else {
        Serial.println("Receive failed");
    }
  }
}
