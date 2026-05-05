// the content of trasmission data
String myName = "NYCU";

void setup() {
  // set data transmission rate
  Serial.begin(115200);
}

void loop() {
  
  // send a string every 0.5 second
  Serial.print(myName);
  delay(500);
}
