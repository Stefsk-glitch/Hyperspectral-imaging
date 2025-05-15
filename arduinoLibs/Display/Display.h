#ifndef DISPLAY_H
#define DISPLAY_H

#include <Wire.h>
#include <Adafruit_SSD1306.h>

class DisplayController {
public:
    // Constructor
    DisplayController(int width, int height, int i2c_addr, int resetPin);
    
    // Initialize the display
    bool begin();
    
    // Available screens in display
    void mainMenu();
    void settingLength();
    void settingSpeed();
    void scanInfo();
    void TempScreen();
    void StopButtonScreen();

    // Button control
    void checkButtons(bool MoveUp, bool MoveDown, bool Select);
   
    // Show text
    void printText(const char* text, int x, int y);
    
    // Update screen
    void clear();
    void updateDisplay();
    void TempUpdate();
    
    // Function to link the pointers
    void attachLength(float* length);
    void attachSpeed(float* speed);
    void attachStartButton(bool* buttonStart); 
    void attachState(String* MainState); 
    void attachTemp(float* T1, float* T2);

private:
    // Navigation and selection functions
    void navigateMenu(bool up);
    void selectMenu();

    // Pointers to the external variables
    float* Length;  // 
    float* Speed;
    float* Temp1;
    float* Temp2;
    String* State;
    bool* StartButton;

    Adafruit_SSD1306 display;  // OLED display object
    
    int i2cAddress; 
    int selectedItem;
    int numItems;
    bool AdjustmodeLength;
    bool AdjustmodeSpeed;
    bool InfoMode;
    bool TempMode;
};

#endif  // DISPLAY_H
