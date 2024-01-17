// Works on Arduino UNO R3
// pin11 PB3

void setup() {
  // Set pin11 as output pin
  DDRB |= _BV(3);
}

void loop() {
  // blink output on pin11
  PORTB |= _BV(3);
  PORTB &= ~_BV(3); 
}
