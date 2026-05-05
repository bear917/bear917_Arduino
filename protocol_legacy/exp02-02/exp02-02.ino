char myName[] = "NYCU";

#include <SPI.h>

void setup (void) {
  digitalWrite(SS, HIGH); // disable Slave Select
  SPI.begin ();
  SPI.beginTransaction(SPISettings(125000, MSBFIRST, SPI_MODE2));
}

void loop (void) {
  char c;
  digitalWrite(SS, LOW); // enable Slave Select
  
  // send test string
  for (const char *p = myName ; c = *p; p++) {
    SPI.transfer (c);
  }
  
  digitalWrite(SS, HIGH); // disable Slave Select
  delay(2000);
}
