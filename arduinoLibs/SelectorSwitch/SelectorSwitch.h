#ifndef SELECTOR_SWITCH_H
#define SELECTOR_SWITCH_H

#include <Arduino.h>
#include <Encoder.h>

class SelectorSwitch {
private:
    Encoder encoder;
    int buttonPin;
    bool buttonPressed;
    bool bmoveUp;
    bool bmoveDown;
    long lastPosition;
    long currentPosition;
    unsigned long lastDebounceTime;
    unsigned long debounceDelay;

public:
    // Constructor
    SelectorSwitch(int pinA, int pinB, int buttonPin);

    // Initialize the encoder and button
    void begin();

    // Update the status of the encoder
    void update();

    // Function to control the movement upwards
    bool moveUp();

    // Function to control the movement down
    bool moveDown();

    long currentPos();

    // Function to control button press with debounce
    bool isButtonPressed();
};

#endif
