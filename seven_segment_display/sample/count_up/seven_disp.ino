/*
     7-segment pinout assignment            common anode pinout
     |-A-|              | -13 -|               G F Com A B
     F   B              8     12               | |  |  | |
     |-G-|              | -7 - |
     E   C              9     11               | |  |  | |
     |-D-|  .DP         | -10- |   6           E D Com C DP
*/

// assign pin on UNO
#define SEG_A  0xD
#define SEG_B  0xC
#define SEG_C  0xB
#define SEG_D  0xA
#define SEG_E  0x9
#define SEG_F  0x8
#define SEG_G  0x7
#define SEG_DP 0x6

//      SHAPE_N => 0b[ABCDEFGDP]
#define SHAPE_BLK  0b11111111
#define SHAPE_0    0b00000011
#define SHAPE_1    0b10011111
#define SHAPE_2    0b00100101
#define SHAPE_3    0b00001101
#define SHAPE_4    0b10011001
#define SHAPE_5    0b01001001
#define SHAPE_6    0b01000001
#define SHAPE_7    0b00011011
#define SHAPE_8    0b00000001
#define SHAPE_9    0b00011001
#define SHAPE_DP   0b11111110
#define SHAPE_C    0b01100011
#define SHAPE_M    0b11010101

void showOne(char content) {
  byte shape = SHAPE_BLK;
  switch (content) {
    case '0': // ASCII=48
      shape = SHAPE_0;
      break;
    case '1': // ASCII=49
      shape = SHAPE_1;
      break;
    case '2': // ASCII=50
      shape = SHAPE_2;
      break;
    case '3': // ASCII=51
      shape = SHAPE_3;
      break;
    case '4': // ASCII=52
      shape = SHAPE_4;
      break;
    case '5': // ASCII=53
      shape = SHAPE_5;
      break;
    case '6': // ASCII=54
      shape = SHAPE_6;
      break;
    case '7': // ASCII=55
      shape = SHAPE_7;
      break;
    case '8': // ASCII=56
      shape = SHAPE_8;
      break;
    case '9': // ASCII=57
      shape = SHAPE_9;
      break;
    case '.': // ASCII=46
      shape = SHAPE_DP;
      break;
    case 'c': // ASCII=99
      shape = SHAPE_C;
      break;
    case 'm': // ASCII=109
      shape = SHAPE_M;
      break;
    case ' ': // ASCII=32
      shape = SHAPE_BLK;
      break;

    default:
      shape = SHAPE_BLK;
      break;
  }

  digitalWrite(SEG_A, bitRead(shape, 7));
  digitalWrite(SEG_B, bitRead(shape, 6));
  digitalWrite(SEG_C, bitRead(shape, 5));
  digitalWrite(SEG_D, bitRead(shape, 4));
  digitalWrite(SEG_E, bitRead(shape, 3));
  digitalWrite(SEG_F, bitRead(shape, 2));
  digitalWrite(SEG_G, bitRead(shape, 1));
  digitalWrite(SEG_DP, bitRead(shape, 0));
}

void setup() {
  // for testing
  Serial.begin(9600);

  pinMode(SEG_A, OUTPUT);
  pinMode(SEG_B, OUTPUT);
  pinMode(SEG_C, OUTPUT);
  pinMode(SEG_D, OUTPUT);
  pinMode(SEG_E, OUTPUT);
  pinMode(SEG_F, OUTPUT);
  pinMode(SEG_G, OUTPUT);
  pinMode(SEG_DP, OUTPUT);
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
