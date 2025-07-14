void setup() {
  setup_ta();
}

void loop() {
  for (int i = 9; i>=1; i--) {
    showOne(i + 48);
    delay(300);
  }

  showOne('.');
  delay(300);
  showOne('c');
  delay(300);
  showOne('m');
  delay(300);
  showOne(' ');
  delay(300);
}
