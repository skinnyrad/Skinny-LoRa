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

// ################################### Configuration ###################################
#define FREQ 915.0 // Transmission Frequency, generally between 868 and 920 
#define PWR 20 // Power between 2 (weakest) and 20 (strongest)
#define BANDWIDTH 125000 //Bandwidth Options: 7800,10400,15600,20800,31250,41700,62500,125000,250000,500000
#define CR 5 // Setup Coding Rate Options: 5 (4/5), 6 (4/6), 7 (4/7), or 8 (4/8)
#define SF 7 // Spreading Factor: Valid values are 6 through 12
// ################################### Configuration ###################################

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
  if (!rf95.setFrequency(FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }

  Serial.print("Freq set to: "); Serial.println(FREQ);  
  rf95.setTxPower(PWR, false); //
  rf95.setSignalBandwidth(BANDWIDTH);
  rf95.setCodingRate4(CR);
  rf95.setSpreadingFactor(SF);

}


void loop() {

  String input = Serial.readString();
  if(input.substring(0,3) == "TX:"){
    Serial.print("Transmitting ");
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
