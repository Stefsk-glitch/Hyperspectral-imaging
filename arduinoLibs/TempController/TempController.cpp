#include "TempController.h"

TempController::TempController(uint8_t sensorPin, unsigned long tempInterval, unsigned long nanTimeout)
    : dht(), pin(sensorPin), tempInterval(tempInterval), nanTimeout(nanTimeout),
      lastTempCheckTime(0), nanStartTime(0), temp(nullptr), tempError(false) {}

void TempController::begin() {
    dht.setup(pin);
}

void TempController::getTemp() {
        float firstTemp = dht.getTemperature();
        *temp = firstTemp;
    }

void TempController::update() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastTempCheckTime >= tempInterval) {
        lastTempCheckTime = currentMillis;
        float newTemp = dht.getTemperature();
        if (isnan(newTemp)) {
            handleNan(currentMillis);
        } else {
            resetNan();
            if (temp != nullptr) {
                *temp = newTemp;
            }
        }
    }
}

void TempController::attachTemp(float* tempPtr) {
    this->temp = tempPtr;
}

bool TempController::hasError() const {
    return tempError;
}

void TempController::handleNan(unsigned long currentMillis) {
    if (nanStartTime == 0) {
        nanStartTime = currentMillis;
    }
    if (currentMillis - nanStartTime >= nanTimeout) {
        tempError = true;
    }
}

void TempController::resetNan() {
    nanStartTime = 0;
    tempError = false;
}
