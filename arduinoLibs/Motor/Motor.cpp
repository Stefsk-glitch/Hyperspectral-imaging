#include "Motor.h"

#define Pitch_circle_mm 36 

// Initialiseer de statische instantie
Motor* Motor::instance = nullptr;

Motor::Motor(int dirPin, int stepPin, int enPin)
    : dirPin(dirPin), stepPin(stepPin), enPin(enPin),
      speed(1000), running(false), Error(false), startTime(0), totalTime(0), accelerationTime(0), decelerationTime(0), AccelDeccelDistance(0), accelerationDistance(0),
      deccelerationDistance(0), lastTime(0), elapsedTime(0), scanLength(0.8), scanSpeed(0.200), totalDistance(1.65), FixedSpeed(true), FixedSpeedMotor(0.05), motorSpeedOld(0) {}

void Motor::begin() {
    pinMode(dirPin, OUTPUT);
    pinMode(stepPin, OUTPUT);
    pinMode(enPin, OUTPUT);
    digitalWrite(enPin, HIGH); // Zet motor uit

    instance = this;               // Wijs dit object toe aan de statische instantie
    setupTimer();                  // Stel de timer in
}

void Motor::UpdateSpeed() {
    float Speed = 0;
    if (FixedSpeed == false) {
        Speed = updateMotorSpeed();
    } else {
        Speed = FixedSpeedMotor;
    }
    float SpeedFloat = Speed;
    float result = 2000000.0f / (((SpeedFloat / ((PI * Pitch_circle_mm) / 1000.0f)) * 200) * 16 * 2); 
    //2000000 = CPU klok Hz (16000000) / prescale (8)
    //1000 van mm naar m
    //200 aantal stappen van stappenmotor per omwenteling
    //16 microssteps ingesteld op driver
    //2 keer interupt uitvoeren voor een hele stap (Hoog en Laag maken van step pin)
    long SpeedInt = round(result);
    //int SpeedInt = round((2000000/((((Speed/((PI*Pitch_circle_mm)/1000))*200)*16)*2)));     
    if (SpeedInt > 0) {
        speed = constrain(SpeedInt, 40, 10000); // Beperk de snelheid binnen het bereik
    }
    OCR1A = speed; // Update de timerwaarde
}

void Motor::FixSpeed(bool fixed) {
    FixedSpeed = fixed;
    UpdateSpeed();
}

void Motor::start() {
    if ((!Error) && (!running)) {
        running = true;
        digitalWrite(enPin, LOW); // Zet motor aan
        startTime = millis();     // Sla het moment op wanneer de motor start
        TIMSK1 |= (1 << OCIE1A); // Schakel timer interrupt in
    }
}

void Motor::stop() {
    running = false;
    digitalWrite(enPin, HIGH); // Zet motor uit
    TIMSK1 &= ~(1 << OCIE1A); // Schakel timer interrupt uit
}

void Motor::setDirection(bool forward) {
    digitalWrite(dirPin, forward ? HIGH : LOW);
}

bool Motor::isRunning() {
    return running;
}


bool Motor::isError() {
    return Error; // Geen fout
}

void Motor::setupTimer() {
    cli(); // Schakel interrupts tijdelijk uit
    TCCR1A = 0;
    TCCR1B = 0;
    TCNT1 = 0;
    OCR1A = speed;
    TCCR1B |= (1 << WGM12); // CTC-modus
    TCCR1B |= (1 << CS11);  // Prescaler 8
    TIMSK1 |= (1 << OCIE1A); // Schakel compare-match interrupt in
    sei(); // Schakel interrupts weer in
}

void Motor::isrStep() {
    if (instance && instance->running) {
        digitalWrite(instance->stepPin, !digitalRead(instance->stepPin)); // Toggle STEP pin
    }
}


void Motor::resetMotor() {
    Error = false;
    elapsedTime=0;
    lastTime = millis();
}

void Motor::setMotionSettings(float ScanSpeed, float ScanLength, float TotalDistance) {
    scanSpeed = ScanSpeed;
    scanLength = ScanLength;
    totalDistance = TotalDistance;
}


// Functie om de snelheid van de motor bij te werken op basis van de verstreken tijd
float Motor::updateMotorSpeed() {
    unsigned long currentTime = millis(); // Verkrijg de verstreken tijd sinds het opstarten in milliseconden
    float motorSpeed = 0.0;               // Standaard snelheid op nul
    float motorSpeedNew = 0;
    elapsedTime = (currentTime - startTime) / 1000.0;  
    //lastTime = currentTime;
    // Versnelling
    if (elapsedTime < accelerationTime) {
        motorSpeedNew = 0.02 + ((scanSpeed - 0.02) / accelerationTime) * elapsedTime; // Lineair versnellen
    }
    // Constante snelheid
    else if (elapsedTime < (accelerationTime + (scanLength / scanSpeed))) {
        motorSpeedNew = scanSpeed; 
    }
    // Deceleratie
    else if (elapsedTime < totalTime) {
        float timeSinceDecelStart = elapsedTime - (accelerationTime + scanLength / scanSpeed);
        motorSpeedNew = scanSpeed - ((scanSpeed - 0.02) / decelerationTime) * timeSinceDecelStart; // Lineair afremmen
    }
    // Stopconditie
    else {
        motorSpeedNew = 0.0; // Stop de motor als de totale tijd is verstreken
    }

    if (motorSpeedNew == 0) {
    motorSpeed = motorSpeedOld;
    } else {
        motorSpeed = motorSpeedNew;
        motorSpeedOld = motorSpeed;
    }

    return motorSpeed;
}

void Motor::calculateMotorSpeed() {
    lastTime = millis();
    AccelDeccelDistance = (totalDistance - scanLength);
    accelerationDistance = AccelDeccelDistance / 2.0;
    deccelerationDistance = accelerationDistance;

    float acceleration = (scanSpeed * scanSpeed - 0.02 * 0.02) / (2.0 * accelerationDistance);
    float deceleration = (scanSpeed * scanSpeed - 0.02 * 0.02) / (2.0 * deccelerationDistance);

    accelerationTime = (scanSpeed - 0.02) / acceleration;
    decelerationTime = (scanSpeed - 0.02) / deceleration;

    totalTime = (accelerationTime + (scanLength / scanSpeed) + decelerationTime);
}

// ISR definitie
ISR(TIMER1_COMPA_vect) {
    Motor::isrStep(); 
}

float Motor::GetAccelerationTime() {
    return accelerationTime;
}

float Motor::GetDeccelerationTime() {
    return decelerationTime;
}

float Motor::GetTotalTime() {
    return totalTime;
}

double Motor::GetElapsedTime() {
    return elapsedTime;
}

void Motor::SetFixedSpeed(float SpeedFixed) {
    FixedSpeedMotor = SpeedFixed;
}