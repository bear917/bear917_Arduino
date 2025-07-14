void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
}

void loop() {
  // put your main code here, to run repeatedly:
  int raw_value = analogRead(A0);
  float temp = (raw_value * 5.0 / 1023) / 0.01;
  Serial.print("temp = ");
  Serial.print(temp);
  Serial.println(" degree Celsius");
  Serial.println();
  delay(500);
}
