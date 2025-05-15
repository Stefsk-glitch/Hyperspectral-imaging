#include "SelectorSwitch.h"

// Constructor
SelectorSwitch::SelectorSwitch(int pinA, int pinB, int buttonPin)
    : encoder(pinA, pinB), buttonPin(buttonPin), buttonPressed(false), bmoveUp(false), bmoveDown(false),
      lastPosition(0), currentPosition(0), lastDebounceTime(0), debounceDelay(100) {} 

// Initialize the encoder and button
void SelectorSwitch::begin() {
    pinMode(buttonPin, INPUT_PULLUP); 
    debounceDelay = 100;
}

// Return a pointer to the Move struct
void SelectorSwitch::update() {
    bmoveUp = false;
    bmoveDown = false;
    currentPosition = encoder.read();
    if (abs(currentPosition - lastPosition) >= 4) {
        if (currentPosition > lastPosition) {
            bmoveUp = false;
            bmoveDown = true;
        } else if (currentPosition < lastPosition) {
            bmoveDown = false;
            bmoveUp = true;
        }

        lastPosition = currentPosition;
    }
}

bool SelectorSwitch::isButtonPressed() {
    bool currentButtonState = digitalRead(buttonPin);
    static bool lastButtonState = HIGH;
    buttonPressed = false;
    if ((millis() - lastDebounceTime) > debounceDelay) {
        if (currentButtonState == LOW && lastButtonState == HIGH) {
            buttonPressed = true;
            lastDebounceTime = millis();
            lastButtonState = false;
        }
        else {
            buttonPressed = false; 
        }
    }

    if (currentButtonState == HIGH && lastButtonState == LOW) {
        lastButtonState = currentButtonState;
    }
    
    return buttonPressed; 
}

// Function to control the movement upwards
bool SelectorSwitch::moveUp() {
    return bmoveUp; 
}

// Function to control the movement down
bool SelectorSwitch::moveDown() {
    return bmoveDown;
}

long SelectorSwitch::currentPos() {
    return currentPosition;
}