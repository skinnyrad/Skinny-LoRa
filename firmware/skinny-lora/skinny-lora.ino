#include <SPI.h>
#include <RH_RF95.h>

#define FW_VERSION "0.2.0"

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

// ################################### Configuration ###################################
// Defaults at power on. All of these can be changed at runtime over serial, see README.md
#define FREQ 915.0 // Transmission Frequency in MHz, must match the module (433, 868 or 915)
#define PWR 20 // Power between 2 (weakest) and 20 (strongest)
#define BANDWIDTH 125000 //Bandwidth Options: 7800,10400,15600,20800,31250,41700,62500,125000,250000,500000
#define CR 5 // Setup Coding Rate Options: 5 (4/5), 6 (4/6), 7 (4/7), or 8 (4/8)
#define SF 7 // Spreading Factor: Valid values are 7 through 12
#define LBT_TIMEOUT_MS 1000 // Listen before talk: how long to wait for a clear channel before giving up
#define SERIAL_WAIT_MS 3000 // How long to wait for a computer at boot before running without one
// ################################### Configuration ###################################

// Largest text payload we can send: the radio's max message length minus the trailing '\0'
#define MAX_PAYLOAD (RH_RF95_MAX_MESSAGE_LEN - 1)
// Largest raw packet: the payload plus the 4 RadioHead header bytes
#define MAX_RAW_PACKET (RH_RF95_MAX_MESSAGE_LEN + RH_RF95_HEADER_LEN)
// Serial input is processed once a newline arrives, or after this many ms with no new characters
#define LINE_IDLE_MS 50
// Minimum time between "Bad packets" reports
#define BAD_REPORT_MS 5000

#if defined(__AVR__)
// The 32u4 has 2.5 KB of RAM: long enough for "HEX:" plus a full raw packet as hex digits
char line[4 + MAX_RAW_PACKET * 2 + 1];
#else
// Long enough for "HEX:" plus a full raw packet as hex with spaces between bytes
char line[4 + MAX_RAW_PACKET * 3 + 1];
#endif
size_t lineLen = 0;
bool lineOverflow = false;
unsigned long lastCharMs = 0;

const long BANDWIDTHS[] = {7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000, 500000};

struct Settings {
  float freq;
  int sf;
  long bw;
  int cr;
  int power;
  bool raw;
  bool lbt;
  bool crc;
} settings = {FREQ, SF, BANDWIDTH, CR, PWR, false, true, true};

uint16_t lastRxBad = 0;
unsigned long lastRxBadReportMs = 0;

// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);

void printStatus() {
  Serial.print(F("STATUS freq=")); Serial.print(settings.freq, 2);
  Serial.print(F(" sf=")); Serial.print(settings.sf);
  Serial.print(F(" bw=")); Serial.print(settings.bw);
  Serial.print(F(" cr=")); Serial.print(settings.cr);
  Serial.print(F(" power=")); Serial.print(settings.power);
  Serial.print(F(" raw=")); Serial.print(settings.raw ? 1 : 0);
  Serial.print(F(" lbt=")); Serial.print(settings.lbt ? 1 : 0);
  Serial.print(F(" crc=")); Serial.print(settings.crc ? 1 : 0);
  Serial.print(F(" rx_good=")); Serial.print(rf95.rxGood());
  Serial.print(F(" rx_bad=")); Serial.print(rf95.rxBad());
  Serial.print(F(" tx_good=")); Serial.print(rf95.txGood());
  Serial.print(F(" version=")); Serial.println(FW_VERSION);
}

void err(const __FlashStringHelper *msg) {
  Serial.print(F("ERR ")); Serial.println(msg);
}

void printHex(const uint8_t *buf, size_t len) {
  for (size_t i = 0; i < len; i++) {
    if (buf[i] < 0x10) Serial.print('0');
    Serial.print(buf[i], HEX);
    Serial.print((i % 16 == 15 || i == len - 1) ? "\n" : " ");
  }
}

// Parse a whole number, rejecting empty strings and trailing junk
bool parseLong(const char *s, long *out) {
  char *end;
  if (*s == '\0') return false;
  *out = strtol(s, &end, 10);
  return *end == '\0';
}

bool parseOnOff(const char *s, bool *out) {
  if (strcmp(s, "1") == 0 || strcasecmp(s, "on") == 0) { *out = true; return true; }
  if (strcmp(s, "0") == 0 || strcasecmp(s, "off") == 0) { *out = false; return true; }
  return false;
}

int hexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

// Decode "DEADBEEF", "de ad be ef" or "DE:AD:BE:EF" into bytes, returns the length or -1
int parseHex(const char *s, uint8_t *out, size_t maxLen) {
  size_t len = 0;
  while (*s) {
    if (*s == ' ' || *s == ':') { s++; continue; }
    int hi = hexValue(s[0]);
    int lo = hexValue(s[1]);
    if (hi < 0 || lo < 0 || len >= maxLen) return -1;
    out[len++] = (hi << 4) | lo;
    s += 2;
  }
  return len;
}

// Send bytes exactly as given. In raw mode the first 4 bytes become the RadioHead header,
// so what goes over the air is precisely `data`. `text` is echoed back, or the bytes as hex if NULL.
void transmit(const uint8_t *data, size_t len, const char *text) {
  if (settings.raw && len < RH_RF95_HEADER_LEN) {
    err(F("Raw packets must be at least 4 bytes. Nothing transmitted."));
    return;
  }

  if (text) {
    Serial.print(F("Transmitting "));
    Serial.println(text);
  } else {
    Serial.print(F("Transmitting hex: "));
    printHex(data, len);
  }

  bool sent;
  if (settings.raw) {
    rf95.setHeaderTo(data[0]);
    rf95.setHeaderFrom(data[1]);
    rf95.setHeaderId(data[2]);
    rf95.setHeaderFlags(data[3], 0xFF);
    sent = rf95.send(data + RH_RF95_HEADER_LEN, len - RH_RF95_HEADER_LEN);
    // Back to the RadioHead defaults for normal mode
    rf95.setHeaderTo(RH_BROADCAST_ADDRESS);
    rf95.setHeaderFrom(RH_BROADCAST_ADDRESS);
    rf95.setHeaderId(0);
    rf95.setHeaderFlags(0, 0xFF);
  } else {
    sent = rf95.send(data, len);
  }

  if (!sent) {
    if (settings.lbt) {
      err(F("Channel busy, nothing transmitted. Send LBT:0 to transmit anyway."));
    } else {
      err(F("Transmit failed"));
    }
    return;
  }
  rf95.waitPacketSent();
}

void applyRadioSettings() {
  rf95.setTxPower(settings.power, false);
  rf95.setSignalBandwidth(settings.bw);
  rf95.setCodingRate4(settings.cr);
  rf95.setSpreadingFactor(settings.sf);
  rf95.setPromiscuous(settings.raw);
  rf95.setCADTimeout(settings.lbt ? LBT_TIMEOUT_MS : 0);
  // With CRC off, packets are sent without a CRC and packets without one are accepted
  rf95.setPayloadCRC(settings.crc);
}

void handleSetting(const char *name, const char *value) {
  long n;
  if (strcmp(name, "FREQ") == 0) {
    float f = atof(value);
    // The RFM95 chip covers 137-1020 MHz, but the module is only matched for its own band
    if (f < 137.0 || f > 1020.0 || !rf95.setFrequency(f)) {
      err(F("Frequency must be between 137 and 1020 MHz"));
      return;
    }
    settings.freq = f;
  } else if (strcmp(name, "SF") == 0) {
    // SF6 needs implicit header mode, which RadioHead does not support
    if (!parseLong(value, &n) || n < 7 || n > 12) { err(F("SF must be 7 to 12")); return; }
    settings.sf = n;
  } else if (strcmp(name, "BW") == 0) {
    bool valid = false;
    if (parseLong(value, &n)) {
      for (size_t i = 0; i < sizeof(BANDWIDTHS) / sizeof(BANDWIDTHS[0]); i++) {
        if (BANDWIDTHS[i] == n) valid = true;
      }
    }
    if (!valid) { err(F("BW must be one of 7800,10400,15600,20800,31250,41700,62500,125000,250000,500000")); return; }
    settings.bw = n;
  } else if (strcmp(name, "CR") == 0) {
    if (!parseLong(value, &n) || n < 5 || n > 8) { err(F("CR must be 5 to 8")); return; }
    settings.cr = n;
  } else if (strcmp(name, "PWR") == 0) {
    if (!parseLong(value, &n) || n < 2 || n > 20) { err(F("PWR must be 2 to 20")); return; }
    settings.power = n;
  } else if (strcmp(name, "RAW") == 0) {
    if (!parseOnOff(value, &settings.raw)) { err(F("RAW must be 0 or 1")); return; }
  } else if (strcmp(name, "LBT") == 0) {
    if (!parseOnOff(value, &settings.lbt)) { err(F("LBT must be 0 or 1")); return; }
  } else if (strcmp(name, "CRC") == 0) {
    if (!parseOnOff(value, &settings.crc)) { err(F("CRC must be 0 or 1")); return; }
  } else {
    err(F("Unknown command. Commands: TX: HEX: FREQ: SF: BW: CR: PWR: RAW: LBT: CRC: STATUS"));
    return;
  }
  applyRadioSettings();
  printStatus();
}

void handleLine() {
  if (lineLen == 0) return;

  if (strcmp(line, "STATUS") == 0) {
    printStatus();
    return;
  }

  char *colon = strchr(line, ':');
  if (colon == NULL) {
    err(F("Unknown command. Commands: TX: HEX: FREQ: SF: BW: CR: PWR: RAW: LBT: CRC: STATUS"));
    return;
  }
  *colon = '\0';
  const char *name = line;
  char *value = colon + 1;

  if (strcmp(name, "TX") == 0) {
    // Older versions of skinny-lora.py append a space to every command, drop it
    size_t n = strlen(value);
    while (n > 0 && value[n - 1] == ' ') value[--n] = '\0';

    if (lineOverflow || n > MAX_PAYLOAD) {
      Serial.print(F("ERR Message too long, max is "));
      Serial.print(MAX_PAYLOAD);
      Serial.println(F(" bytes. Nothing transmitted."));
      return;
    }
    // Normal mode sends the terminating '\0' too, receivers compare the payload as a C string.
    // Raw mode sends exactly what was typed.
    transmit((const uint8_t*)value, settings.raw ? n : n + 1, value);

  } else if (strcmp(name, "HEX") == 0) {
    uint8_t data[MAX_RAW_PACKET];
    int len = lineOverflow ? -1 : parseHex(value, data, settings.raw ? MAX_RAW_PACKET : RH_RF95_MAX_MESSAGE_LEN);
    if (len <= 0) {
      Serial.print(F("ERR HEX needs pairs of hex digits, max "));
      Serial.print(settings.raw ? MAX_RAW_PACKET : RH_RF95_MAX_MESSAGE_LEN);
      Serial.println(F(" bytes. Nothing transmitted."));
      return;
    }
    transmit(data, len, NULL);

  } else {
    handleSetting(name, value);
  }
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
    } else if (lineLen < sizeof(line) - 1) {
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

void printDecoded(const uint8_t *buf, size_t len) {
  // Skip trailing '\0' padding, show other non-printable bytes as '.'
  while (len > 0 && buf[len - 1] == 0) len--;
  for (size_t i = 0; i < len; i++) {
    Serial.print(isprint(buf[i]) ? (char)buf[i] : '.');
  }
  Serial.println();
}

void receivePacket() {
  // In raw mode the 4 header bytes RadioHead strips off are put back in front of the payload
  uint8_t packet[MAX_RAW_PACKET];
  uint8_t offset = settings.raw ? RH_RF95_HEADER_LEN : 0;
  uint8_t len = RH_RF95_MAX_MESSAGE_LEN;
  if (!rf95.recv(packet + offset, &len)) {
    Serial.println(F("Receive failed"));
    return;
  }
  if (settings.raw) {
    packet[0] = rf95.headerTo();
    packet[1] = rf95.headerFrom();
    packet[2] = rf95.headerId();
    packet[3] = rf95.headerFlags();
  }
  size_t total = len + offset;

  digitalWrite(LED_BUILTIN, HIGH);
  Serial.println(F("----------------- Start PACKET -----------------"));
  Serial.println(F("Received: "));
  printHex(packet, total);
  Serial.print(F("Decoded Value: "));
  printDecoded(packet, total);
  Serial.print(F("Length: "));
  Serial.println(total);
  Serial.print(F("RSSI: "));
  Serial.println(rf95.lastRssi(), DEC);
  Serial.print(F("SNR: "));
  Serial.println(rf95.lastSNR(), DEC);
  Serial.print(F("Time: "));
  Serial.print(millis());
  Serial.println(F(" ms"));
  Serial.println(F("----------------- End PACKET -----------------"));
}

void setup() {

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  Serial.begin(115200);
  // Wait briefly for a computer, then carry on so the board also runs from a battery
  while (!Serial && millis() < SERIAL_WAIT_MS) delay(1);
  delay(100);
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  while (!rf95.init()) {
    Serial.println(F("LoRa radio init failed"));
    while (1);
  }

  Serial.println(F("Welcome to the skinny-lora transceiver"));
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(FREQ)) {
    Serial.println(F("setFrequency failed"));
    while (1);
  }

  Serial.print(F("Freq set to: ")); Serial.println(FREQ);
  applyRadioSettings();
  printStatus();
}


void loop() {

  readSerial();

  if(rf95.available()) {
    receivePacket();
  }

  // Packets with a bad or missing CRC never reach recv(), so report them separately.
  // At most every few seconds, a busy band can produce a lot of them.
  uint16_t rxBad = rf95.rxBad();
  if (rxBad != lastRxBad && millis() - lastRxBadReportMs >= BAD_REPORT_MS) {
    Serial.print(F("Bad packets: "));
    Serial.print((uint16_t)(rxBad - lastRxBad));
    Serial.print(F(" new, "));
    Serial.print(rxBad);
    Serial.println(F(" total (CRC error or no CRC, send CRC:0 to accept packets without one)"));
    lastRxBad = rxBad;
    lastRxBadReportMs = millis();
  }
}
