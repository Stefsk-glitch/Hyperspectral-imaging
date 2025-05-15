#ifndef ENC_H
#define ENC_H

#include <Arduino.h>

class Enc {
private:
    int pinA;
    int pinB;
    volatile double position;
    volatile int direction;
    float gearRatio;
    unsigned long lastTime;
    unsigned long lastPos;
    long double speed;
    long double mmPos;


public:
    Enc(int pinA, int pinB, float gearRatio);

    void begin();
    long double getSpeed();
    int getDirection();
    long double getPosition();
    void updateSpeed(); // Deze mag privé blijven
    // Maak de interrupt methoden publiek
    void handleInterruptA();
    void resetPosition();
    // Statische variabele voor de interrupt handler
    static Enc* interruptHandler;
};

#endif // ENC_H
