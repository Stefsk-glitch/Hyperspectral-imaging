#include <Wire.h>
#include <DHT.h>
#include "Display.h"
#include "SelectorSwitch.h"
#include "RGBcontrol.h"
#include "TempController.h"
#include "Motor.h"
#include "Enc.h"

#include <ArduinoJson.h>

// Define the settings and object for OLED-display
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
#define OLED_I2C_ADDR 0x3C
DisplayController display(SCREEN_WIDTH, SCREEN_HEIGHT, OLED_I2C_ADDR, OLED_RESET);

// Define the pins and objects for push buttons with RGB lighting
#define StopButton 2
bool FirstInteruptStopButton = false;
RGBController rgbController(5, 4, 6);

// Define the pins and object for encoder push button
#define EncButtonS1 23
#define EncButtonS2 24
#define EncButtonKEY 22
SelectorSwitch selector(EncButtonS1, EncButtonS2, EncButtonKEY);

// Define the pins and objects for the two temperature sensors
#define DHT21_PIN1 9  // Pin DHT21 sensor control box
#define DHT21_PIN2 10  // Pin DHT21 sensor LAB setup
TempController TempControlBox(DHT21_PIN1, 15000, 45000);
TempController TempLABsetup(DHT21_PIN2, 15000, 45000);
float temp1 = 0.0;
float temp2 = 0.0;

// Define the pins and objects for motor
#define STEP_PIN 11
#define DIR_PIN 12
#define EN_PIN 13
Motor motor(DIR_PIN, STEP_PIN, EN_PIN);

// Startup and timesettings
unsigned long startTime;
unsigned long delayTime = 5000; // 5 sec
unsigned long lastUpdate = 0;

// General settings
float scanLength = 1.0;
float scanSpeed = 0.011; 
float totalDistance = 1.67; // Totale afstand in meters

// Defining the states
enum State {
  Waiting,
  Homing,
  Accelerating,
  Scanning,
  Decelerating,
  Stopped,
  SafeStop
};

State currentState = Waiting;
State lastStringCurrentState = currentState;
String StringCurrentState = String(currentState);
bool StartButton = false;
bool ScanStart = false;

// Gebruik digitale pin 16
const int eindschakelaar1 = 16; 
const int eindschakelaar2 = 17;

String serial3Buffer = "";

// Declaration of the functions
void handleStopButton();

String stateToString(State state);

void setup() {
    Serial.begin(9600);
    Serial3.begin(9600);
    pinMode(StopButton, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(StopButton), handleStopButton, CHANGE); // Interrupt op Rising-edge
    selector.begin();
    rgbController.begin();
    // encoder.begin();
    
    pinMode(eindschakelaar1, INPUT_PULLUP);
    pinMode(eindschakelaar2, INPUT_PULLUP);
    
    if (!digitalRead(StopButton)) {
        currentState = Waiting;
    } else {
        currentState = SafeStop;
        FirstInteruptStopButton = true;
    }

    StartButton = false;
    ScanStart = false;

    motor.begin();
    motor.setDirection(false);
    motor.FixSpeed(true);
    motor.SetFixedSpeed(0.05);
    motor.stop();

    TempControlBox.begin();
    TempControlBox.attachTemp(&temp1);
    TempLABsetup.begin();
    TempLABsetup.attachTemp(&temp2);

    // Initialiseer het display
    if (!display.begin()) {
        Serial.println("Display niet gevonden, controleer verbinding!");
        while (true); 
    }
    display.clear();
    display.attachLength(&scanLength);
    display.attachSpeed(&scanSpeed); 
    display.attachTemp(&temp1, &temp2);
    display.attachState(&StringCurrentState);

    // Startup display with delay
    display.attachStartButton(&StartButton);
    display.printText("Startup...", 15, 15);
    display.updateDisplay();
    rgbController.setState(Startup);
    startTime = millis();
    while (millis() - startTime < delayTime) {
        rgbController.update();
    }
    display.clear();

    StringCurrentState = stateToString(currentState);
    TempControlBox.getTemp();
    TempLABsetup.getTemp();
    if (!digitalRead(StopButton)) {
        display.mainMenu();
    }
}

void loop() {

    handleSerial3();

    if (currentState != Waiting) {
        StartButton = false;
    }

    if ((lastStringCurrentState != currentState)){
        StringCurrentState = stateToString(currentState);
        lastStringCurrentState = currentState;
        if (currentState != SafeStop && currentState != Waiting) {
            display.scanInfo();
        }
    }

    bool isEindschakelaar1Triggered = digitalRead(eindschakelaar1) == HIGH;
    bool isEindschakelaar2Triggered = digitalRead(eindschakelaar2) == HIGH;

    if ((!(currentState == Waiting || currentState == Homing || currentState == Accelerating) && isEindschakelaar1Triggered) || isEindschakelaar2Triggered) {
        //delay(10); // Eenvoudige debounce
        if (digitalRead(eindschakelaar1) == HIGH || digitalRead(eindschakelaar2) == HIGH) {
            currentState = SafeStop;
        }
    }

    if ((digitalRead(StopButton)) && currentState != SafeStop) {
        currentState = SafeStop;
        FirstInteruptStopButton = true;
    }
  
    switch (currentState) {
        case Waiting:
        TempControlBox.update();
        TempLABsetup.update();
        rgbController.setState(Wait);
        rgbController.update();
        display.checkButtons(selector.moveUp(), selector.moveDown(), selector.isButtonPressed());
        selector.update();

        if (millis() - lastUpdate >= 16000) {
        display.TempUpdate(); 
        lastUpdate = millis(); 
        }

        if (StartButton) {
            motor.setDirection(false);
            motor.FixSpeed(true);
            motor.setMotionSettings(scanSpeed, scanLength, totalDistance);
            display.scanInfo();
            currentState = Homing;
        }

        break;

        case Homing:
        rgbController.setState(Home);
        rgbController.update();
        motor.start();

        if (digitalRead(eindschakelaar1) == HIGH) { 
            motor.stop();
            motor.calculateMotorSpeed();
            motor.setDirection(true); 
            motor.FixSpeed(false);
            motor.resetMotor();
            startTime = millis();
            while (millis() - startTime < 5000) {
                rgbController.update();
                if (digitalRead(StopButton)) {
                    currentState = SafeStop;
                    FirstInteruptStopButton = true;
                }
            }
            // encoder.resetPosition();
            rgbController.setState(Run);
            rgbController.update();
            currentState = Accelerating;
        }
        break;

        case Accelerating:
        motor.start();
        motor.UpdateSpeed();
        if (motor.GetElapsedTime() >= motor.GetAccelerationTime()) {
            currentState = Scanning;
        }
        break;

        case Scanning:
        motor.UpdateSpeed();
        if (motor.GetElapsedTime()  >= (motor.GetAccelerationTime() + scanLength / scanSpeed)) {
            currentState = Decelerating;
        }
        break;

        case Decelerating:
        motor.UpdateSpeed();

        if (motor.GetElapsedTime()  >= motor.GetTotalTime()) {
            motor.stop();
            currentState = Stopped;
        }
        break;

        case Stopped:
        rgbController.setState(Stop);
        rgbController.update();
        motor.stop();
        motor.resetMotor();
        startTime = millis();
        while (millis() - startTime < 2000) {
            rgbController.update();
            if (digitalRead(StopButton)) {
                currentState = SafeStop;
                FirstInteruptStopButton = true;
            }
        }    
        currentState = Waiting;
        display.mainMenu();
        break;

        case SafeStop:
        rgbController.setState(Safe);
        rgbController.update();
        motor.stop();
        motor.FixSpeed(true);
        if ((millis() - lastUpdate >= 16000) || FirstInteruptStopButton == true) {
            display.StopButtonScreen(); 
            lastUpdate = millis(); 
            FirstInteruptStopButton = false;
        }

        if (!digitalRead(StopButton)) {
            motor.resetMotor();
            // encoder.resetPosition();
            currentState = Waiting; 
            StringCurrentState = stateToString(currentState);
            display.mainMenu();
        }
        break;

        default:
        Serial.println("Onbekende state!");
        break;
    }
}

// Interrupt service function (ISR)
void handleStopButton() {
  currentState = SafeStop;
  motor.stop();
  FirstInteruptStopButton = true;
}

// Function for showing string program status in screen 
String stateToString(State state) {
    switch (state) {
        case Waiting:           return "Waiting";
        case Homing:            return "Homing";
        case Accelerating:      return "Accelerating";
        case Scanning:          return "Scanning";
        case Decelerating:      return "Decelerating";
        case Stopped:           return "Stopped";
        case SafeStop:          return "SafeStop";
        default:                return "Unknown";
    }
}

void handleSerial3() {
    while (Serial3.available()) {
        char c = Serial3.read();
        if (c == '\n') {
            StaticJsonDocument<200> doc;
            DeserializationError error = deserializeJson(doc, serial3Buffer);
            if (!error) {
                const char* cmd = doc["cmd"];
                Serial.print("Mega Command received: ");
                Serial.println(cmd);

                if (strcmp(cmd, "start_scan") == 0) {
                  StartButton = true;
                }

                if (strcmp(cmd, "stop_scan") == 0) {
                  currentState = SafeStop;
                  motor.stop();
                  FirstInteruptStopButton = true;
                  motor.resetMotor();
                  
                  currentState = Waiting; 
                  StringCurrentState = stateToString(currentState);
                  display.mainMenu();
                }

                // Respond with ack
                StaticJsonDocument<200> ackDoc;
                ackDoc["uno_ack"] = cmd;
                serializeJson(ackDoc, Serial3);
                Serial3.println();
            } else {
                Serial.print("Mega JSON parse failed: ");
                Serial.println(error.c_str());
            }
            serial3Buffer = ""; // Reset buffer
        } else {
            serial3Buffer += c;
            // prevent buffer overflow
            if (serial3Buffer.length() > 50) {
                serial3Buffer = "";
            }
        }
    }
}