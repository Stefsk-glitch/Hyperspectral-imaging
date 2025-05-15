#include "Enc.h"

// Constructor
Enc::Enc(int pinA, int pinB, float gearRatio) : pinA(pinA), pinB(pinB), gearRatio(gearRatio) {
    position = 0;
    direction = 0;
    lastTime = 0;
    lastPos = 0;
    speed = 0;
    mmPos = 0;
}

// Static interrupt service routines
static void handleInterruptAWrapper() {
    Enc* instance = Enc::interruptHandler;
    if (instance) {
        instance->handleInterruptA();
    }
}

// static void handleInterruptBWrapper() {
//     Enc* instance = Enc::interruptHandler;
//     if (instance) {
//         instance->handleInterruptB();
//     }
// }

// Initialize the encoder
void Enc::begin() {
    pinMode(pinA, INPUT);
    pinMode(pinB, INPUT);

    // Assign the current object instance to the interruptHandler static member
    interruptHandler = this;

    // Attach interrupts using the wrapper functions
    attachInterrupt(digitalPinToInterrupt(pinA), handleInterruptAWrapper, CHANGE);
    // attachInterrupt(digitalPinToInterrupt(pinB), handleInterruptBWrapper, CHANGE);
}

// Handlers for interrupts
void Enc::handleInterruptA() {
  static int lastState = LOW;
  int currentState = digitalRead(pinA);
  if (currentState != lastState) {
    if (digitalRead(pinB) != currentState) {
      position--;
      direction=0;
    } else {
      position++;
      direction=1;
    }
  }
  lastState = currentState;
}

// Calculate speed
void Enc::updateSpeed() {
    unsigned long currentTime = micros();
    long double tempPos = getPosition();
    double deltaPos = tempPos - lastPos;
    long double deltaTime = (currentTime - lastTime) / 1000000;

    speed = (deltaPos) / deltaTime; 
    lastTime = currentTime;
    lastPos = tempPos;
}

// Return speed
long double Enc::getSpeed() {
    return speed;
}

// Return direction
int Enc::getDirection() {
    return direction;
}

// Return position
long double Enc::getPosition() {
    mmPos = (position * gearRatio);
    return mmPos;
}

void Enc::resetPosition() {
    position = 0;
    mmPos = 0;
}

// Static member to hold the current instance of Enc for interrupt handling
Enc* Enc::interruptHandler = nullptr;
