#include "RGBcontrol.h"

// Stel de RGB-waarden in
void RGBController::setRGB(int red, int green, int blue) {
    analogWrite(redPin, 255 - red);
    analogWrite(greenPin, 255 - green);
    analogWrite(bluePin, 255 - blue);
}

// Initialiseer de pinnen als OUTPUT
void RGBController::begin() {
    pinMode(redPin, OUTPUT);
    pinMode(greenPin, OUTPUT);
    pinMode(bluePin, OUTPUT);
    setRGB(0, 0, 0); // Zet LED uit bij start
}

// Stel de huidige status in
void RGBController::setState(StateRGB state) {
    currentState = state;
}

// Beheer de RGB LED op basis van de huidige status
void RGBController::update() {
    unsigned long currentTime = millis();

    switch (currentState) {
        case Home:
            if (currentTime - lastBlinkTime >= 500) { // Knipper elke 500ms
                lastBlinkTime = currentTime;
                blinkState = !blinkState;
                setRGB(blinkState ? 0 : 0, blinkState ? 255 : 0, 0); // Groen knipperend
            }
            break;

        case Wait:
            setRGB(255, 255, 0); // Geel continu
            break;

        case Run:
            setRGB(0, 255, 0); // Groen continu
            break;

        case Stop:
            if (currentTime - lastBlinkTime >= 500) { // Knipper elke 500ms
                lastBlinkTime = currentTime;
                blinkState = !blinkState;
                setRGB(blinkState ? 255 : 0, 0, 0); // Rood knipperend
            }
            break;

        case Safe:
            setRGB(255, 0, 0); // Rood continu
            break;

        case Startup:
            if (currentTime - lastBlinkTime >= 500) { // Knipper elke 500ms
                lastBlinkTime = currentTime;
                blinkState = !blinkState;
                setRGB(blinkState ? 255 : 0, blinkState ? 255 : 0, 0); // Geel knipperend
            }
            break;
    }
}
