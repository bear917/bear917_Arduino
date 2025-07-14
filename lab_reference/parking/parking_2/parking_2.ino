int trigPin = 4;                  //Trig Pin
int echoPin = 5;                  //Echo Pin

long duration, cm;
unsigned long previousPing = 0;
const long pingInterval = 5000; // unit: microsecond

int tonePin = 3;
int toneInterval = 100;
int toneValue = 1;
int isNear = 1;
unsigned long previousTone = 0;

void setup() {
  Serial.begin (9600);             // Serial Port begin
  pinMode(trigPin, OUTPUT);        // 定義輸入及輸出
  pinMode(echoPin, INPUT);
  pinMode(tonePin, OUTPUT);
}

void loop() {

  unsigned long current = millis();

  if (millis() - previousPing >= 500) {
    ping();
    previousPing = current;

    if (cm <= 5) {
      toneInterval = 50;
    } else if (cm <= 10) {
      isNear = 1;
      toneInterval = 100;
    } else if (cm <= 15) {
      isNear = 1;
      toneInterval = 200;
    } else if (cm <= 20) {
      isNear = 1;
      toneInterval = 500;
    } else {
      isNear = 0;
    }
  }



  if (millis() - previousTone >= toneInterval) {
    if (isNear) {
      previousTone = current;
      if (toneValue)
        toneValue = 0;
      else
        toneValue = 1;
      analogWrite(tonePin, toneValue);
    } else
      analogWrite(tonePin, 0);
  }


}

float ping() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(5);
  digitalWrite(trigPin, HIGH);     // 給 Trig 高電位，持續 10微秒
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  pinMode(echoPin, INPUT);             // 讀取 echo 的電位
  duration = pulseIn(echoPin, HIGH);   // 收到高電位時的時間

  cm = (duration / 2) / 29.1;       // 將時間換算成距離 cm 或 inch

  Serial.print("Distance : ");
  Serial.print(cm);
  Serial.print("cm");
  Serial.println();
}
