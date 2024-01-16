// Pins
const uint8_t btn_pin = 2;
const uint8_t led_pin = 5;

void setup() {

  // Set button pin to be input with pullup
  DDRD &= ~_BV(btn_pin);
  PORTD |= _BV(btn_pin); 

  // Sedt LED pin to be output
  DDRD |= _BV(led_pin);

  pinMode(btn_pin, INPUT_PULLUP);
  pinMode(led_pin, OUTPUT);

  attachInterrupt(digitalPinToInterrupt(btn_pin), toggle, FALLING);
}

void loop() {


  // Pretend we're doing other stuff
  delay(500);
}

void toggle() {
  PORTD ^= _BV(led_pin);
}
