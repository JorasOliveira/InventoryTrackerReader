/*
 * RFID RC522 reader/writer for NTAG215 -> Serial
 *
 * Serial protocol (9600 baud, newline-terminated):
 *   Arduino -> host:  READY                 on boot
 *                     UID:04 AB CD ...       when a tag is scanned
 *                     WROTE:OK               after a successful NDEF write
 *                     ERR:<reason>           on a failed write
 *   host -> Arduino:  WRITE:<url>            encode <url> as an NDEF URI
 *                                            record and write it to the tag
 *
 * Wiring (RC522 -> Arduino Uno):
 *   SDA/SS -> D10   SCK -> D13   MOSI -> D11   MISO -> D12
 *   RST -> D9       3.3V -> 3.3V (NOT 5V!)     GND -> GND
 *
 * Library: "MFRC522" by GithubCommunity.
 * Tags:    NTAG215 (NFC Forum Type 2) — UID is 7 bytes.
 */

#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN  10
#define RST_PIN 9

MFRC522 mfrc522(SS_PIN, RST_PIN);

// NDEF buffer (TLV + record + URL), padded to a multiple of 4. Plenty for our
// short URLs; NTAG215 has 504 bytes of user memory if we ever need more.
static const byte NDEF_BUF_MAX = 144;

void setup() {
  Serial.begin(9600);
  while (!Serial) { ; }
  SPI.begin();
  mfrc522.PCD_Init();
  Serial.println(F("READY"));
}

void loop() {
  // 1) Handle an incoming command (e.g. "WRITE:https://...").
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("WRITE:")) {
      writeNdefUrl(cmd.substring(6));
    }
    return;  // don't also do a read this iteration
  }

  // 2) Normal read: report the UID of any newly presented tag.
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial()) return;

  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
    if (i < mfrc522.uid.size - 1) uid += " ";
  }
  uid.toUpperCase();

  Serial.print(F("UID:"));
  Serial.println(uid);

  mfrc522.PICC_HaltA();
}

// Wake and select whatever tag is on the reader (works even if it was halted
// by a prior read). Returns true once a card is selected.
bool activateCard() {
  for (byte attempt = 0; attempt < 40; attempt++) {   // ~2 seconds
    byte atqa[2];
    byte size = sizeof(atqa);
    MFRC522::StatusCode r = mfrc522.PICC_WakeupA(atqa, &size);
    if (r == MFRC522::STATUS_OK || r == MFRC522::STATUS_COLLISION) {
      if (mfrc522.PICC_ReadCardSerial()) return true;
    }
    delay(50);
  }
  return false;
}

// Encode `url` as an NDEF URI record and write it to the NTAG215 starting at
// page 4, after ensuring the capability container marks the tag NDEF-formatted.
void writeNdefUrl(String url) {
  // URI identifier code: a known prefix is replaced by a single code byte.
  byte prefixCode = 0x00;          // 0x00 = no abbreviation
  String body = url;
  if (url.startsWith("https://"))     { prefixCode = 0x04; body = url.substring(8); }
  else if (url.startsWith("http://")) { prefixCode = 0x03; body = url.substring(7); }

  byte bodyLen    = (byte)body.length();
  byte payloadLen = 1 + bodyLen;       // prefix code + URI text
  byte msgLen     = 4 + payloadLen;    // record header (D1 01 PL 55) + payload
  int  tlvLen     = 2 + msgLen + 1;    // T,L + message + terminator (0xFE)

  // Pad up to a whole number of 4-byte pages.
  int padded = ((tlvLen + 3) / 4) * 4;
  if (padded > NDEF_BUF_MAX) {
    Serial.println(F("ERR:url too long"));
    return;
  }

  byte buf[NDEF_BUF_MAX];
  int i = 0;
  buf[i++] = 0x03;          // NDEF Message TLV tag
  buf[i++] = msgLen;        // TLV length
  buf[i++] = 0xD1;          // record: MB=1 ME=1 SR=1 TNF=well-known
  buf[i++] = 0x01;          // type length
  buf[i++] = payloadLen;    // payload length
  buf[i++] = 0x55;          // record type 'U' (URI)
  buf[i++] = prefixCode;    // URI prefix code
  for (byte j = 0; j < bodyLen; j++) buf[i++] = (byte)body[j];
  buf[i++] = 0xFE;          // TLV terminator
  while (i < padded) buf[i++] = 0x00;  // pad remainder of last page

  if (!activateCard()) {
    Serial.println(F("ERR:no card"));
    return;
  }

  // Capability Container for NTAG215: NDEF magic, v1.0, 504 bytes, read/write.
  byte cc[4] = {0xE1, 0x10, 0x3E, 0x00};
  mfrc522.MIFARE_Ultralight_Write(3, cc, 4);  // harmless to re-write on a tag

  // Write 4 bytes (one page) at a time, starting at page 4.
  byte page = 4;
  for (int p = 0; p < padded; p += 4) {
    MFRC522::StatusCode st = mfrc522.MIFARE_Ultralight_Write(page, &buf[p], 4);
    if (st != MFRC522::STATUS_OK) {
      Serial.print(F("ERR:write page "));
      Serial.println(page);
      mfrc522.PICC_HaltA();
      return;
    }
    page++;
  }

  mfrc522.PICC_HaltA();
  Serial.println(F("WROTE:OK"));
}
