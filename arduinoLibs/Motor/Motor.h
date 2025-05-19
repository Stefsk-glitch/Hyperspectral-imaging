#ifndef MOTOR_H
#define MOTOR_H

#include <Arduino.h>

class Motor {
public:
    Motor(int dirPin, int stepPin, int enPin);
    void begin();                   // Initialiseer de motor
    void UpdateSpeed();       // Stel de snelheid in (in microseconden per stap)
    void start();                   // Start de motor
    void stop();                    // Stop de motor
    void setDirection(bool forward); // Stel de draairichting in
    bool isRunning();               // Controleer of de motor draait
    bool isError();                 // Controleer of de motor een fout heeft (stall)
    static void isrStep();          // Maak deze functie publiek
    void calculateMotorSpeed();
    void setMotionSettings(float ScanSpeed, float ScanLength, float TotalDistance);
    void resetMotor();
    float GetAccelerationTime();
    float GetDeccelerationTime();
    float GetTotalTime();
    double GetElapsedTime();
    void SetFixedSpeed(float SpeedFixed);
    void FixSpeed(bool Fixed);
private:
    int dirPin;                     // Richtingspin
    int stepPin;                    // Steppin
    int enPin;                      // Enable pin
    int speed;                      // Snelheid (microseconden per stap)
    bool running;                   // Of de motor momenteel draait
    bool Error;
    void setupTimer();              // Stel de timer in voor stappen
    static Motor* instance;         // Statische instantie van de motor
    unsigned long startTime; // Tijd waarop de motor begon te draaien
    float updateMotorSpeed();
    // Motion profile settings
    float totalTime;        // Totale tijd voor de beweging
    float accelerationTime; // Versnellingstijd (van 0 naar scanSpeed)
    float decelerationTime;
    float AccelDeccelDistance; // Versnelling afstand
    float accelerationDistance; // Versnelling afstand
    float deccelerationDistance;
    unsigned long lastTime; // Voor de tijdsberekeningen
    double elapsedTime;
    float scanLength;
    float scanSpeed; 
    float totalDistance; // Totale afstand in meters
    bool FixedSpeed;
    float FixedSpeedMotor;
    float motorSpeedOld;
protected:

};

#endif
