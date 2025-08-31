#define TSL1401_CLK 11   // TSL1401 클럭 핀
#define TSL1401_SI  10   // TSL1401 SI 핀
#define TSL1401_AO  A0   // TSL1401 아날로그 출력 핀
#define NPIXELS     128  // 총 픽셀 수

#define FASTADC 1  // ADC 속도 빠르게 설정

byte Pixel[NPIXELS];           // 원본 픽셀 데이터
byte threshold_data[NPIXELS];  // 임계값 처리된 데이터

#define sbi(sfr, bit) (_SFR_BYTE(sfr) |= _BV(bit))
#define cbi(sfr, bit) (_SFR_BYTE(sfr) &= ~_BV(bit))

// 임계값 기반 이진화 함수 (값이 threshold 이상이면 1, 아니면 0)
void line_threshold(int threshold)
{
    for (int i = 0; i < NPIXELS; i++)
    {
        threshold_data[i] = (Pixel[i] > threshold) ? 1 : 0;
    }
}

// 카메라 데이터 읽기 (analogRead / 4 → 0~255 범위로 변환)
void read_TSL1401_camera()
{
    // SI 펄스 시작
    digitalWrite(TSL1401_SI, HIGH);
    digitalWrite(TSL1401_CLK, HIGH);
    delayMicroseconds(1);
    digitalWrite(TSL1401_CLK, LOW);
    digitalWrite(TSL1401_SI, LOW);
    delayMicroseconds(1);

    // 픽셀 값 읽기
    for (int i = 0; i < NPIXELS; i++)
    {
        digitalWrite(TSL1401_CLK, HIGH);
        delayMicroseconds(1);
        Pixel[i] = analogRead(TSL1401_AO) / 4;  // 0~1023 → 0~255
        digitalWrite(TSL1401_CLK, LOW);
        delayMicroseconds(1);
    }
}

void send_pixel_data()
{
    for (int i = 0; i < NPIXELS; i++)
    {

        Serial.print(Pixel[i]);
        Serial.print(",");
    }
    Serial.println();
}

void setup()
{
    Serial.begin(115200);

    pinMode(TSL1401_CLK, OUTPUT);
    pinMode(TSL1401_SI, OUTPUT);

#if FASTADC
    sbi(ADCSRA, ADPS2);
    cbi(ADCSRA, ADPS1);
    cbi(ADCSRA, ADPS0);
#endif
}

void loop()
{
    read_TSL1401_camera();  // 픽셀 읽기
    send_pixel_data();      // 원본 픽셀 데이터 전송
    line_threshold(255);    // 임계값 이진화

    delay(50);  // 200ms 대기 (너무 빠르면 플로터가 못 따라감)
}
