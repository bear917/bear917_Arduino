const int MAX_SIZE = 400;

int data[MAX_SIZE];

void setup() {
  Serial.begin(9600);
}

void loop() {
  static int cnt = 0;
  static int fcnt;

  if (cnt < MAX_SIZE) {
    for (cnt = 0; cnt < MAX_SIZE; cnt++) {
      data[cnt] = analogRead(A0);
    }

    for (fcnt = 0; fcnt < MAX_SIZE; fcnt++) {
      Serial.println(data[fcnt]);
    }

  }
}
