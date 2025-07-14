// output two different frequency square wave
// "delay()" function is forbidden.

// output pin definition also satisfies 7-segment display experiments.
// 13 12 11 10 9 8 7 6
// A  B  C  D  E F G DP
#define SEG_A 0x0D
#define SEG_D 0x0A

// set default output states
byte state_A = 0b0;
byte state_D = 0b1;

// set timers default time
unsigned long preA = 0;
unsigned long preD = 0;

// set the intervals of two output signals
// A interval = 0.5 sec, B interval = 0.005 sec
const long interA = 500;
const long interD = 5;

void setup() {
  pinMode(SEG_A, OUTPUT);
  pinMode(SEG_D, OUTPUT);
}

void loop() {
  unsigned long current = millis();
  if (current - preA >= interA) {
    preA = current;
    // toggle A signal
    state_A = state_A ^ 1;
  }
  if (current - preD >= interD) {
    preD = current;
    // toggle D signal
    state_D = state_D ^ 1;
  }

  digitalWrite(SEG_A, state_A);
  digitalWrite(SEG_D, state_D);
}
