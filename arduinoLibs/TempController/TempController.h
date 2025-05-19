#ifndef TEMPCONTROLLER_H
#define TEMPCONTROLLER_H

#include <DHT.h>

class TempController {
public:
    TempController(uint8_t sensorPin, unsigned long tempInterval, unsigned long nanTimeout);

    void begin();
    void update();
    void getTemp();
    void attachTemp(float* tempPtr);
    bool hasError() const;

private:
    DHT dht;
    uint8_t pin;
    unsigned long tempInterval;
    unsigned long nanTimeout;
    unsigned long lastTempCheckTime;
    unsigned long nanStartTime;
    float* temp;
    bool tempError;

    void handleNan(unsigned long currentMillis);
    void resetNan();
};

#endif