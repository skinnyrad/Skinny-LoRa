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

// Largest text payload we can send: the radio's max message length minus the trailing '\0'
#define MAX_PAYLOAD (RH_RF95_MAX_MESSAGE_LEN - 1)
// Serial input is processed once a newline arrives, or after this many ms with no new characters
#define LINE_IDLE_MS 50

char line[MAX_PAYLOAD + 8];
size_t lineLen = 0;
bool lineOverflow = false;
unsigned long lastCharMs = 0;

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


void handleLine() {
  if (lineLen < 3 || strncmp(line, "TX:", 3) != 0) {
    return;
  }

  // Older versions of skinny-lora.py append a space to every command, drop it
  while (lineLen > 3 && line[lineLen - 1] == ' ') line[--lineLen] = '\0';

  const char *payload = line + 3;
  if (lineOverflow) {
    Serial.print("Message too long, max is ");
    Serial.print(MAX_PAYLOAD);
    Serial.println(" bytes. Nothing transmitted.");
    return;
  }

  Serial.print("Transmitting ");
  Serial.println(payload);
  // Send the terminating '\0' too, receivers compare the payload as a C string
  rf95.send((const uint8_t*)payload, strlen(payload) + 1);
  rf95.waitPacketSent();
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    lastCharMs = millis();
    if (c == '\n' || c == '\r') {
      line[lineLen] = '\0';
      handleLine();
      lineLen = 0;
      lineOverflow = false;
    } else if (lineLen < 3 + MAX_PAYLOAD) {
      line[lineLen++] = c;
    } else {
      lineOverflow = true;
    }
  }

  // Input without a line ending (e.g. Serial Monitor set to "No line ending")
  if ((lineLen > 0 || lineOverflow) && millis() - lastCharMs > LINE_IDLE_MS) {
    line[lineLen] = '\0';
    handleLine();
    lineLen = 0;
    lineOverflow = false;
  }
}

void printDecoded(const uint8_t *buf, uint8_t len) {
  // Skip trailing '\0' padding, show other non-printable bytes as '.'
  while (len > 0 && buf[len - 1] == 0) len--;
  for (uint8_t i = 0; i < len; i++) {
    Serial.print(isprint(buf[i]) ? (char)buf[i] : '.');
  }
  Serial.println();
}

void loop() {

  readSerial();

  if(rf95.available()) {
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    if (rf95.recv(buf, &len)) {
      digitalWrite(LED_BUILTIN, HIGH);
      Serial.println("----------------- Start PACKET -----------------");
      RH_RF95::printBuffer("Received: ", buf, len);
      Serial.print("Decoded Value: ");
      printDecoded(buf, len);
      Serial.print("RSSI: ");
      Serial.println(rf95.lastRssi(), DEC);
      Serial.println("----------------- End PACKET -----------------");
    } else {
        Serial.println("Receive failed");
    }
  }
}
