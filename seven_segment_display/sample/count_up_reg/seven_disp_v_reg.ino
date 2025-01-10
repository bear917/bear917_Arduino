// Author: bear917
/*
     7-segment pinout assignment            common anode pinout
     |-A-|              | -13 -|               G F Com A B
     F   B              8     12               | |  |  | |
     |-G-|              | -7 - |
     E   C              9     11               | |  |  | |
     |-D-|  .DP         | -10- |   6           E D Com C DP
*/

void showOne(char content) {
  // Clear a~b bit
  PORTB &= 0b11000000;
  PORTD &= 0b00111111;

  switch (content) {
    case ' ':  // ASCII=32
      PORTB |= 0b00111111;
      PORTD |= 0b11000000;
      break;

    case '0':  // ASCII=48
      PORTB |= 0b00000000;
      PORTD |= 0b11000000;
      break;

    case '1':  // ASCII=49
      PORTB |= 0b00100111;
      PORTD |= 0b11000000;
      break;

    case '2':  // ASCII=50
      PORTB |= 0b00001001;
      PORTD |= 0b01000000;
      break;

    case '3':  // ASCII=51
      PORTB |= 0b00000011;
      PORTD |= 0b01000000;
      break;

    case '4':  // ASCII=52
      PORTB |= 0b00100110;
      PORTD |= 0b01000000;
      break;

    case '5':  // ASCII=53
      PORTB |= 0b00010010;
      PORTD |= 0b01000000;
      break;

    case '6':  // ASCII=54
      PORTB |= 0b00010000;
      PORTD |= 0b01000000;
      break;
    case '7':  // ASCII=55
      PORTB |= 0b00000110;
      PORTD |= 0b11000000;
      break;

    case '8':  // ASCII=56
      PORTB |= 0b00000000;
      PORTD |= 0b01000000;
      break;

    case '9':  // ASCII=57
      PORTB |= 0b00000110;
      PORTD |= 0b01000000;
      break;

    case '.':  // ASCII=46
      PORTB |= 0b00111111;
      PORTD |= 0b10000000;
      break;

    case 'c':  // ASCII=99
      PORTB |= 0b00011000;
      PORTD |= 0b11000000;
      break;

    case 'm':  // ASCII=109
      PORTB |= 0b00110101;
      PORTD |= 0b01000000;
      break;

    // blank as default
    default:  // Author: bear917
      PORTB |= 0b00111111;
      PORTD |= 0b11000000;
      break;
  }
}

void setup() {
  DDRB |= 0b00111111;
  DDRD |= 0b11111111;
}

void loop() {
  for (int i = 0; i < 10; i++) {
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
