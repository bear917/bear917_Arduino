/*
 * ECG Acquisition Firmware for Arduino UNO
 * -----------------------------------------
 * Samples ECG signal on A0 at SAMPLE_HZ using Timer1 CTC interrupt.
 * Sends binary packets over USB serial at BAUD_RATE.
 *
 * Packet format (5 bytes per sample, little-endian):
 *   [0] 0xAA     sync byte 1
 *   [1] 0x55     sync byte 2
 *   [2] counter  8-bit rolling counter (lets receiver detect drops)
 *   [3] adc_lo   ADC value low byte
 *   [4] adc_hi   ADC value high byte  (upper 6 bits = 0, ADC is 10-bit)
 *
 * Throughput at defaults: 250 Hz * 5 B = 1250 B/s  (plenty of headroom).
 *
 * Hardware:
 *   A0  <- ECG analog front-end output (biased to ~2.5 V)
 *   GND <- common ground with front-end
 */

// ---------------- Configuration ----------------
const uint8_t  ECG_PIN   = A0;
const uint32_t BAUD_RATE = 250000;   // 0% error at 16 MHz; reliable on UNO's 16U2
const uint16_t SAMPLE_HZ = 250;      // ECG is dominantly <40 Hz; 250 Hz is standard

// Sync bytes for packet framing
const uint8_t  SYNC_1 = 0xAA;
const uint8_t  SYNC_2 = 0x55;

// ---------------- Globals ----------------
volatile bool    sampleFlag    = false;
volatile uint8_t sampleCounter = 0;

// ---------------- Timer1 ISR: fires at SAMPLE_HZ ----------------
ISR(TIMER1_COMPA_vect) {
  sampleFlag = true;   // Keep ISR minimal — do ADC + serial in main loop
}

// ---------------- Timer1 setup: CTC mode at SAMPLE_HZ ----------------
void setupSamplingTimer() {
  noInterrupts();
  TCCR1A = 0;                                // Normal port operation
  TCCR1B = 0;
  TCNT1  = 0;

  // Prescaler 64 -> timer tick = 16 MHz / 64 = 250 kHz
  // OCR1A = (F_CPU / prescaler / target_hz) - 1
  //       = (16e6 / 64 / 250) - 1 = 999
  OCR1A = (F_CPU / 64UL / SAMPLE_HZ) - 1;

  TCCR1B |= (1 << WGM12);                    // CTC mode (clear timer on compare)
  TCCR1B |= (1 << CS11) | (1 << CS10);       // Prescaler 64
  TIMSK1 |= (1 << OCIE1A);                   // Enable compare-match A interrupt
  interrupts();
}

// ---------------- Optional: speed up ADC ----------------
// Default analogRead() takes ~104 µs (prescaler 128 -> ADC clock 125 kHz).
// We don't need faster at 250 Hz, but keep this around if you bump SAMPLE_HZ.
void fasterADC() {
  // Set ADC prescaler to 32 -> ADC clock = 500 kHz -> ~26 µs per conversion.
  // (ATmega328P datasheet: stay <=1 MHz for full 10-bit accuracy.)
  ADCSRA = (ADCSRA & 0xF8) | 0x05;
}

void setup() {
  Serial.begin(BAUD_RATE);

  analogReference(DEFAULT);   // 5 V reference. Use EXTERNAL if you bias to AREF.
  // fasterADC();              // Uncomment if you raise SAMPLE_HZ above ~500 Hz
  analogRead(ECG_PIN);        // Throwaway read (first conversion after mux switch)

  setupSamplingTimer();
}

void loop() {
  if (sampleFlag) {
    sampleFlag = false;

    uint16_t adc = analogRead(ECG_PIN);
    uint8_t  cnt = sampleCounter++;

    // Pack and send in one Serial.write() call to minimize overhead
    uint8_t packet[5] = {
      SYNC_1,
      SYNC_2,
      cnt,
      (uint8_t)(adc & 0xFF),
      (uint8_t)((adc >> 8) & 0xFF)
    };
    Serial.write(packet, 5);
  }
}
