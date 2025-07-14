byte leftDisp = 4;
byte rightDisp = 5;
byte a = 13;
byte b = 12;
byte c = 11;
byte d = 10;
byte e = 9;
byte f = 8;
byte g = 7;
byte dp = 6;

unsigned long time_prev = 0;
unsigned long time_now = 0;

byte n[11] = {
  0b00000011, // display "0"
  0b10011111, // display "1"
  0b00100101, // display "2"
  0b00001101, // display "3"
  0b10011001, // display "4"
  0b01001001, // display "5"
  0b01000001, // display "6"
  0b00011111, // display "7"
  0b00000001, // display "8"
  0b00011001, // display "9"
  0b11111111  // display nothing, all dark
};

// message that will rotate form right to left
byte msg[] = {n[5],n[7],n[1],n[2],n[1],n[2],n[1], n[10], n[5], n[4], n[1], n[2], n[7], n[10]};  
int msg_length = sizeof(msg);

void setup() {
//  Serial.begin(9600);  // use serial commands will cause massive memory usage
  for (int i = 4; i < 14; i++) {
    pinMode(i, OUTPUT);
  }
}

void showDigit(byte myDigit) {
  digitalWrite(a, bitRead(myDigit, 7));
  digitalWrite(b, bitRead(myDigit, 6));
  digitalWrite(c, bitRead(myDigit, 5));
  digitalWrite(d, bitRead(myDigit, 4));

  digitalWrite(e, bitRead(myDigit, 3));
  digitalWrite(f, bitRead(myDigit, 2));
  digitalWrite(g, bitRead(myDigit, 1));
  digitalWrite(dp, bitRead(myDigit, 0));
}

void loop() {
  static int i_msg_0 = 0, i_msg_1 = 1;  // msg array index
  
  time_now = millis();
  
  if (time_now - time_prev > 500) {
    time_prev = time_now;
    if (++i_msg_0 == msg_length) i_msg_0 = 0;
    if (++i_msg_1 == msg_length) i_msg_1 = 0;
  } 

//  Serial.println(i_msg);

  
  digitalWrite(leftDisp, 0);
  digitalWrite(rightDisp, 1);
  showDigit(msg[i_msg_0]);
  delay(6);
  digitalWrite(leftDisp, 1);
  digitalWrite(rightDisp, 0);
  showDigit(msg[i_msg_1]);
  delay(6);
}
