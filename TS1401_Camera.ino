#include <Arduino_FreeRTOS.h>
#include <avr/io.h>  // AVR 레지스터 정의 포함
#include <avr/wdt.h>  // Watchdog Timer 헤더
#include <semphr.h>

#define TSL1401_CLK 11   // TSL1401 클럭 핀
#define TSL1401_SI  10   // TSL1401 SI 핀
#define TSL1401_AO  A0   // TSL1401 아날로그 출력 핀
#define NPIXELS     128  // 총 픽셀 수

#define FASTADC 1  // ADC 속도 빠르게 설정

// ADC 레지스터 조작을 위한 매크로 정의 (FASTADC에서 사용)
#ifndef sbi
#define sbi(sfr, bit) (_SFR_BYTE(sfr) |= _BV(bit))
#endif
#ifndef cbi
#define cbi(sfr, bit) (_SFR_BYTE(sfr) &= ~_BV(bit))
#endif

// 세마포어 선언
SemaphoreHandle_t xSerialSemaphore;
SemaphoreHandle_t xDataSemaphore;  // 픽셀 데이터 보호용

// 태스크 함수 선언
void TaskSerial(void* pvParameters);
void TaskCamera(void* pvParameters);

byte Pixel[NPIXELS];           // 원본 픽셀 데이터
byte PixelBuffer[NPIXELS];     // 전송용 버퍼
byte threshold_data[NPIXELS];  // 임계값 처리된 데이터

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
    // WDT 초기 비활성화 (초기화 중 리셋 방지)
    wdt_disable();

    Serial.begin(115200);
    while (!Serial)
    {
        ;  // 시리얼 포트가 연결될 때까지 대기
    }

    pinMode(TSL1401_CLK, OUTPUT);
    pinMode(TSL1401_SI, OUTPUT);

#if FASTADC && defined(__AVR__) && defined(ADCSRA)
    // AVR 아키텍처에서만 ADC 속도 최적화 (Arduino Uno, Nano, Mega 등)
    // ADC 프리스케일러를 16으로 설정 (더 빠른 ADC 변환)
    sbi(ADCSRA, ADPS2);
    cbi(ADCSRA, ADPS1);
    cbi(ADCSRA, ADPS0);
#endif

    // 세마포어 생성
    xSerialSemaphore = xSemaphoreCreateMutex();
    xDataSemaphore = xSemaphoreCreateMutex();

    if (xSerialSemaphore != NULL && xDataSemaphore != NULL)
    {
        // 시리얼 송신 태스크 생성
        xTaskCreate(TaskSerial, "Serial",
                    256,  // 스택 크기 증가
                    NULL,
                    2,  // 우선순위
                    NULL);

        // 카메라 읽기 태스크 생성
        xTaskCreate(TaskCamera, "Camera",
                    256,  // 스택 크기 증가
                    NULL,
                    1,  // 우선순위
                    NULL);

        // WDT 활성화 (2초 타임아웃)
        wdt_enable(WDTO_2S);
        
        // 태스크 스케줄러 시작
        vTaskStartScheduler();
    }
    else
    {
        // 세마포어 생성 실패 시 처리
        Serial.println("Failed to create semaphore");
    }
}

// 카메라 읽기 태스크
void TaskCamera(void* pvParameters)
{
    (void)pvParameters;

    const TickType_t xFrequency = pdMS_TO_TICKS(40);  // 40ms = 25Hz
    TickType_t xLastWakeTime = xTaskGetTickCount();

    for (;;)
    {
        // WDT 리셋 (태스크가 정상 동작 중임을 알림)
        wdt_reset();
        
        // 카메라 데이터 읽기
        read_TSL1401_camera();

        // 데이터 세마포어 획득하여 버퍼에 복사
        if (xSemaphoreTake(xDataSemaphore, portMAX_DELAY) == pdTRUE)
        {
            memcpy(PixelBuffer, Pixel, NPIXELS);  // 버퍼에 복사
            xSemaphoreGive(xDataSemaphore);
        }

        // 임계값 처리 (0과 255는 특수 케이스)
        // 0: 모든 픽셀이 0 (전부 검정)
        // 255: 모든 픽셀이 그대로 (임계값 무시)
        line_threshold(255);  // 255로 설정 (임계값 처리 사실상 비활성화)

        // 정확한 25Hz 주기 유지
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

// 시리얼 통신 태스크 (송신만 수행)
void TaskSerial(void* pvParameters)
{
    (void)pvParameters;

    const TickType_t xDelay = pdMS_TO_TICKS(100);  // 100ms 간격으로 데이터 전송
    TickType_t xLastWakeTime = xTaskGetTickCount();
    byte localPixelBuffer[NPIXELS];  // 로컬 버퍼

    for (;;)
    {
        // WDT 리셋 (태스크가 정상 동작 중임을 알림)
        wdt_reset();
        
        // 100ms마다 픽셀 데이터 전송
        if (xSemaphoreTake(xDataSemaphore, pdMS_TO_TICKS(10)) == pdTRUE)
        {
            memcpy(localPixelBuffer, PixelBuffer, NPIXELS);  // 로컬 버퍼에 복사
            xSemaphoreGive(xDataSemaphore);

            // 시리얼로 데이터 전송 (Serial 0번 사용)
            if (xSemaphoreTake(xSerialSemaphore, portMAX_DELAY) == pdTRUE)
            {
                for (int i = 0; i < NPIXELS; i++)
                {
                    Serial.print(localPixelBuffer[i]);
                    Serial.print(",");
                }
                Serial.println();
                xSemaphoreGive(xSerialSemaphore);
            }
        }

        // 정확한 100ms 주기 유지
        vTaskDelayUntil(&xLastWakeTime, xDelay);
    }
}

void loop()
{
    // FreeRTOS 사용 시 loop()는 비어있어야 함
    // 모든 작업은 태스크에서 처리됨
}
