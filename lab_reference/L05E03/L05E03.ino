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

#define BTNU 0x03
#define BTND 0x02

int buttonStateU;
int lastButtonStateU = LOW;
unsigned long lastDebounceTimeU = 0;
unsigned long debounceDelayU = 50;

int buttonStateD;
int lastButtonStateD = LOW;
unsigned long lastDebounceTimeD = 0;
unsigned long debounceDelayD = 50;

int brightness = 255;

void addOne() {
  if (brightness >= 255)
    brightness = 255;
  else
    brightness += 51;
}

void minusOne() {
  if (brightness <= 0)
    brightness = 0;
  else
    brightness -= 51;
}


void setup() {
  pinMode(SEG_A, OUTPUT);
  pinMode(SEG_B, OUTPUT);
  pinMode(SEG_C, OUTPUT);
  pinMode(SEG_D, OUTPUT);
  pinMode(SEG_E, OUTPUT);
  pinMode(SEG_F, OUTPUT);
  pinMode(SEG_G, OUTPUT);
  pinMode(SEG_DP, OUTPUT);
  pinMode(BTNU, INPUT_PULLUP);
  pinMode(BTND, INPUT_PULLUP);
  Serial.begin(9600);



  digitalWrite(SEG_A, HIGH);
  digitalWrite(SEG_B, HIGH);
  digitalWrite(SEG_F, HIGH);
  digitalWrite(SEG_G, HIGH);
}

void loop() {
  int readingU = digitalRead(BTNU);
  int readingD = digitalRead(BTND);

  if (readingU != lastButtonStateU) {
    lastDebounceTimeU = millis();
  }

  if ((millis() - lastDebounceTimeU) > debounceDelayU) {
    if (readingU != buttonStateU) {
      buttonStateU = readingU;

      if (buttonStateU == LOW) {
        addOne();
      }
    }
  }

  if (readingD != lastButtonStateD) {
    lastDebounceTimeD = millis();
  }

  if ((millis() - lastDebounceTimeD) > debounceDelayD) {
    if (readingD != buttonStateD) {
      buttonStateD = readingD;

      if (buttonStateD == LOW) {
        minusOne();
      }
    }
  }

  lastButtonStateU = readingU;
  lastButtonStateD = readingD;

  //
  //  analogWrite(SEG_A, brightness);
  //  analogWrite(SEG_B, brightness);
  analogWrite(SEG_C, brightness);
  analogWrite(SEG_D, brightness);
  analogWrite(SEG_E, brightness);
  //  analogWrite(SEG_F, brightness);
  //  analogWrite(SEG_G, brightness);
  analogWrite(SEG_DP, brightness);




}
