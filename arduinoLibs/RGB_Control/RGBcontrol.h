#ifndef RGBCONTROL_H
#define RGBCONTROL_H

#include <Arduino.h>

enum StateRGB {
    Home,
    Wait,
    Run,
    Stop,
    Safe,
    Startup
};

class RGBController {
private:
    int redPin;
    int greenPin;
    int bluePin;
    StateRGB currentState;
    unsigned long lastBlinkTime;
    bool blinkState;

public:
    // Constructor
    RGBController(int red, int green, int blue)
        : redPin(red), greenPin(green), bluePin(blue), currentState(Home), lastBlinkTime(0), blinkState(false) {}

    // Methoden
    void begin();
    void setRGB(int red, int green, int blue);
    void setState(StateRGB state);
    void update();
};

#endif // RGBCONTROL_H