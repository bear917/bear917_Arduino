/* source from: https://www.youtube.com/watch?v=6q1yEb_ukw8 
*/
const int btn_pin = 2;
const int led_pin = 5;

void setup() {
  DDRD = B00100000;
  PORTD = B00000100;
}

void loop() {
  int btn = (PIND & (1 << btn_pin)) >> btn_pin;

  if (!btn) {
    PORTD = _BV(led_pin) | PORTD;
  } else {
    PORTD = ~_BV(led_pin) & PORTD;
  }

}
