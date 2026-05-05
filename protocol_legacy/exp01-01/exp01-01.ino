// the content of trasmission data
String myName = "WANG HSIAO MING";

void setup() {
  // set data transmission rate
  Serial.begin(9600);
}

void loop() {
  
  // send a string every 0.5 second
  Serial.print(myName);
  delay(500);
}
