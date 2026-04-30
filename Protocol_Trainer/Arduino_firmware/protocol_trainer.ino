#include <SoftwareSerial.h>
#include <SPI.h>

// RX = D9, TX = D8
SoftwareSerial protoUART(9, 8);

const int SPI_CS_PIN = 10;
const int MAX_BYTES = 32;
const int CMD_BUFFER_SIZE = 96;
const long SOFTSERIAL_MAX_BAUD = 57600;

// Listen 模式參數
const int RX_FRAME_BUFFER_SIZE = 64;        // 一個 frame 最大 byte 數
const unsigned long FRAME_TIMEOUT_MS = 30;  // 靜默這麼久就視為一個 frame 結束

char cmdBuffer[CMD_BUFFER_SIZE];
int cmdIndex = 0;

// Listen 狀態
bool listening = false;
long listenBaud = 0;
uint8_t rxFrame[RX_FRAME_BUFFER_SIZE];
int rxFrameLen = 0;
unsigned long lastRxMillis = 0;

void setup() {
  Serial.begin(115200);

  pinMode(SPI_CS_PIN, OUTPUT);
  digitalWrite(SPI_CS_PIN, HIGH);

  SPI.begin();

  Serial.println(F("Arduino Protocol Trainer Ready"));
  Serial.println(F("Command format:"));
  Serial.println(F("UART,<baud>,ASCII:<message>"));
  Serial.println(F("UART,<baud>,HEX:<hex bytes>"));
  Serial.println(F("SPI<mode>,<clock_hz>,ASCII:<message>"));
  Serial.println(F("SPI<mode>,<clock_hz>,HEX:<hex bytes>"));
  Serial.println(F("LISTEN,<baud>     -- start UART RX listen on D9"));
  Serial.println(F("STOP              -- stop listening"));
  Serial.print(F("Note: SoftwareSerial max reliable baud = "));
  Serial.println(SOFTSERIAL_MAX_BAUD);
}

void loop() {
  // 1) 處理從 PC 來的命令
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdIndex > 0) {
        cmdBuffer[cmdIndex] = '\0';
        processCommand(cmdBuffer);
        cmdIndex = 0;
      }
    } else {
      if (cmdIndex < CMD_BUFFER_SIZE - 1) {
        cmdBuffer[cmdIndex++] = c;
      } else {
        cmdIndex = 0;
        Serial.println(F("ERROR: Command too long"));
        while (Serial.available() > 0) {
          char d = Serial.read();
          if (d == '\n' || d == '\r') break;
        }
      }
    }
  }

  // 2) Listen 模式：抓 RX 上的 byte，靜默逾時就把 frame 吐出去
  if (listening) {
    while (protoUART.available() > 0 && rxFrameLen < RX_FRAME_BUFFER_SIZE) {
      rxFrame[rxFrameLen++] = (uint8_t)protoUART.read();
      lastRxMillis = millis();
    }

    // buffer 滿了：強制吐出
    if (rxFrameLen >= RX_FRAME_BUFFER_SIZE) {
      emitFrame();
    }
    // 有資料且靜默超過 timeout：吐出
    else if (rxFrameLen > 0 && (millis() - lastRxMillis) >= FRAME_TIMEOUT_MS) {
      emitFrame();
    }
  }
}

// ---------- frame 輸出 ----------

void emitFrame() {
  // 格式：RX:<hex bytes>   例如  RX:48 65 6C 6C 6F
  // 用純 HEX 是因為 ASCII 可能含不可印字元、容易破壞行格式；
  // 由 GUI 端把 HEX 還原成 ASCII 顯示。
  Serial.print(F("RX:"));
  for (int i = 0; i < rxFrameLen; i++) {
    if (i > 0) Serial.print(' ');
    if (rxFrame[i] < 0x10) Serial.print('0');
    Serial.print(rxFrame[i], HEX);
  }
  Serial.println();
  rxFrameLen = 0;
}

// ---------- 字串小工具 ----------

void trimInPlace(char *s) {
  int len = strlen(s);
  int start = 0;
  while (start < len && isspace((unsigned char)s[start])) start++;
  int end = len - 1;
  while (end >= start && isspace((unsigned char)s[end])) end--;
  int newLen = end - start + 1;
  if (start > 0 && newLen > 0) {
    memmove(s, s + start, newLen);
  }
  s[newLen > 0 ? newLen : 0] = '\0';
}

void toUpperInPlace(char *s) {
  for (; *s; s++) {
    *s = toupper((unsigned char)*s);
  }
}

// ---------- 命令處理 ----------

void processCommand(char *cmd) {
  // 先看是不是 LISTEN / STOP 這類無 payload 的命令
  // 為了判斷方便，先做一個 uppercase 的副本來比對開頭
  char headCopy[16];
  int headLen = 0;
  while (cmd[headLen] && cmd[headLen] != ',' && cmd[headLen] != ':' && headLen < (int)sizeof(headCopy) - 1) {
    headCopy[headLen] = toupper((unsigned char)cmd[headLen]);
    headLen++;
  }
  headCopy[headLen] = '\0';

  if (strcmp(headCopy, "STOP") == 0) {
    handleStop();
    return;
  }

  if (strcmp(headCopy, "LISTEN") == 0) {
    // LISTEN,<baud>
    char *firstComma = strchr(cmd, ',');
    if (firstComma == NULL) {
      Serial.println(F("ERROR: LISTEN requires baud (LISTEN,<baud>)"));
      return;
    }
    char *baudStr = firstComma + 1;
    trimInPlace(baudStr);
    long baud = atol(baudStr);
    if (baud <= 0) {
      Serial.println(F("ERROR: Invalid LISTEN baud"));
      return;
    }
    handleListen(baud);
    return;
  }

  // ---- 以下是原本的 UART/SPI 送出命令 ----

  char *colon = strchr(cmd, ':');
  if (colon == NULL) {
    Serial.println(F("ERROR: Missing ':'"));
    return;
  }

  *colon = '\0';
  char *header = cmd;
  char *payload = colon + 1;

  trimInPlace(header);
  trimInPlace(payload);
  toUpperInPlace(header);

  char *firstComma = strchr(header, ',');
  if (firstComma == NULL) {
    Serial.println(F("ERROR: Invalid header format"));
    return;
  }
  *firstComma = '\0';
  char *afterFirst = firstComma + 1;

  char *secondComma = strchr(afterFirst, ',');
  if (secondComma == NULL) {
    Serial.println(F("ERROR: Invalid header format"));
    return;
  }
  *secondComma = '\0';

  char *protocol = header;
  char *param    = afterFirst;
  char *format   = secondComma + 1;

  trimInPlace(protocol);
  trimInPlace(param);
  trimInPlace(format);

  uint8_t data[MAX_BYTES];
  int dataLength = 0;

  if (strcmp(format, "ASCII") == 0) {
    dataLength = asciiToBytes(payload, data, MAX_BYTES);
  } else if (strcmp(format, "HEX") == 0) {
    dataLength = hexToBytes(payload, data, MAX_BYTES);
  } else {
    Serial.print(F("ERROR: Unsupported format: "));
    Serial.println(format);
    return;
  }

  if (dataLength <= 0) {
    Serial.println(F("ERROR: Empty or invalid payload"));
    return;
  }

  // 送出命令進來時，若還在 listen，先自動停掉避免時序衝突
  if (listening) {
    handleStop();
  }

  if (strcmp(protocol, "UART") == 0) {
    long baud = atol(param);
    if (baud <= 0) {
      Serial.println(F("ERROR: Invalid UART baud rate"));
      return;
    }
    if (baud > SOFTSERIAL_MAX_BAUD) {
      Serial.print(F("WARN: baud "));
      Serial.print(baud);
      Serial.print(F(" exceeds SoftwareSerial limit "));
      Serial.print(SOFTSERIAL_MAX_BAUD);
      Serial.println(F(" -- data may be unreliable"));
    }
    sendUART(data, dataLength, baud);
  }
  else if (strcmp(protocol, "SPI0") == 0) sendSPI(data, dataLength, SPI_MODE0, 0, atol(param));
  else if (strcmp(protocol, "SPI1") == 0) sendSPI(data, dataLength, SPI_MODE1, 1, atol(param));
  else if (strcmp(protocol, "SPI2") == 0) sendSPI(data, dataLength, SPI_MODE2, 2, atol(param));
  else if (strcmp(protocol, "SPI3") == 0) sendSPI(data, dataLength, SPI_MODE3, 3, atol(param));
  else {
    Serial.print(F("ERROR: Unsupported protocol: "));
    Serial.println(protocol);
  }
}

// ---------- LISTEN / STOP ----------

void handleListen(long baud) {
  if (listening) {
    protoUART.end();
    listening = false;
  }

  if (baud > SOFTSERIAL_MAX_BAUD) {
    Serial.print(F("WARN: listen baud "));
    Serial.print(baud);
    Serial.print(F(" exceeds SoftwareSerial limit "));
    Serial.print(SOFTSERIAL_MAX_BAUD);
    Serial.println(F(" -- RX may drop bytes"));
  }

  protoUART.begin(baud);
  protoUART.listen();

  listening = true;
  listenBaud = baud;
  rxFrameLen = 0;
  lastRxMillis = 0;

  Serial.print(F("OK: LISTEN started @ "));
  Serial.print(baud);
  Serial.println(F(" bps"));
}

void handleStop() {
  if (!listening) {
    Serial.println(F("OK: STOP (was not listening)"));
    return;
  }

  // 把殘留的 byte 也 flush 出去，避免漏掉最後一個 frame
  if (rxFrameLen > 0) {
    emitFrame();
  }

  protoUART.end();
  listening = false;
  rxFrameLen = 0;

  Serial.println(F("OK: STOP listening"));
}

// ---------- Payload 解析 ----------

int asciiToBytes(const char *text, uint8_t *buffer, int maxLen) {
  int len = strlen(text);
  if (len > maxLen) len = maxLen;
  for (int i = 0; i < len; i++) {
    buffer[i] = (uint8_t)text[i];
  }
  return len;
}

int hexToBytes(const char *text, uint8_t *buffer, int maxLen) {
  int count = 0;
  const char *p = text;

  while (*p && count < maxLen) {
    while (*p && isspace((unsigned char)*p)) p++;
    if (!*p) break;

    char token[8];
    int tlen = 0;
    while (*p && !isspace((unsigned char)*p) && tlen < (int)sizeof(token) - 1) {
      token[tlen++] = *p++;
    }
    token[tlen] = '\0';

    if (tlen == 0) continue;

    for (int i = 0; i < tlen; i++) {
      token[i] = toupper((unsigned char)token[i]);
    }

    char *digits = token;
    if (tlen >= 2 && digits[0] == '0' && digits[1] == 'X') {
      digits += 2;
    }

    int dlen = strlen(digits);
    if (dlen == 0 || dlen > 2) {
      Serial.print(F("ERROR: Invalid HEX token: "));
      Serial.println(token);
      return -1;
    }

    char *endPtr;
    long value = strtol(digits, &endPtr, 16);
    if (*endPtr != '\0' || value < 0 || value > 255) {
      Serial.print(F("ERROR: Invalid HEX value: "));
      Serial.println(token);
      return -1;
    }

    buffer[count++] = (uint8_t)value;
  }

  return count;
}

// ---------- 協定輸出 ----------

void sendUART(uint8_t *data, int length, long baud) {
  protoUART.begin(baud);
  for (int i = 0; i < length; i++) {
    protoUART.write(data[i]);
  }
  protoUART.flush();
  protoUART.end();   // 用完關掉，避免 SoftwareSerial 中斷干擾下個動作

  Serial.print(F("OK: UART "));
  Serial.print(baud);
  Serial.print(F(" bps sent "));
  Serial.print(length);
  Serial.println(F(" byte(s)"));
}

void sendSPI(uint8_t *data, int length, uint8_t spiMode, int modeNumber, long clockHz) {
  if (clockHz <= 0) {
    Serial.println(F("ERROR: Invalid SPI clock"));
    return;
  }

  SPI.beginTransaction(SPISettings(clockHz, MSBFIRST, spiMode));
  digitalWrite(SPI_CS_PIN, LOW);

  for (int i = 0; i < length; i++) {
    SPI.transfer(data[i]);
  }

  digitalWrite(SPI_CS_PIN, HIGH);
  SPI.endTransaction();

  Serial.print(F("OK: SPI Mode "));
  Serial.print(modeNumber);
  Serial.print(F(", "));
  Serial.print(clockHz);
  Serial.print(F(" Hz sent "));
  Serial.print(length);
  Serial.println(F(" byte(s)"));
}
