#include "Display.h"

// Constructor
DisplayController::DisplayController(int width, int height, int i2c_addr, int resetPin)
    : display(width, height, &Wire, resetPin), i2cAddress(i2c_addr), selectedItem(0), numItems(5), AdjustmodeLength(false), AdjustmodeSpeed(false) { // Pass correct i2cAddress
    selectedItem = 0;
    numItems = 5;
    AdjustmodeLength = false;
    AdjustmodeSpeed = false;
    InfoMode = false;
    TempMode = false;
}

// Initialize the display
bool DisplayController::begin() {
    if (!display.begin(SSD1306_SWITCHCAPVCC, i2cAddress)) {  
        Serial.println("OLED initialisatie mislukt!");
        return false;
    }

    // Standard settings for text and rotation
    display.setRotation(2);
    display.setTextSize(1); 
    display.setTextColor(SSD1306_WHITE); 
    
    display.clearDisplay();
    display.display();
    return true;
}

// Screen that serves as the main menu
void DisplayController::mainMenu() {
    clear();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    
    String menuItems[numItems] = {"Info", "Start scan", "Scanlengte", "Scansnelheid", "Temperatuur"};
    
    for (int i = 0; i < numItems; i++) {
        if (i == selectedItem) {
            display.setCursor(3, 13 + (i * 10)); // Position for the indicator
            display.print("> ");  // Show the arrow for the selected item
        } else {
            display.setCursor(3, 13 + (i * 10));  // Position without indicator
            display.print("  ");  // Empty space for unselected items
        }
        display.setCursor(15, 13 + (i * 10));  // Beginning of text (after "> ")
        display.print(menuItems[i]);
    }
    updateDisplay();
}

void DisplayController::StopButtonScreen() {
    static const unsigned char PROGMEM image_Warning_bits[] = {0x00,0x03,0x00,0x00,0x00,0x07,0x80,0x00,0x00,0x0f,0xc0,0x00,0x00,0x0f,0xc0,0x00,0x00,0x1f,0xe0,0x00,0x00,0x3c,0xf0,0x00,0x00,0x3c,0xf0,0x00,0x00,0x7c,0xf8,0x00,0x00,0xfc,0xfc,0x00,0x00,0xfc,0xfc,0x00,0x01,0xfc,0xfe,0x00,0x03,0xfc,0xff,0x00,0x03,0xfc,0xff,0x00,0x07,0xfc,0xff,0x80,0x0f,0xfc,0xff,0xc0,0x0f,0xfc,0xff,0xc0,0x1f,0xfc,0xff,0xe0,0x3f,0xff,0xff,0xf0,0x3f,0xff,0xff,0xf0,0x7f,0xfc,0xff,0xf8,0xff,0xfc,0xff,0xfc,0xff,0xff,0xff,0xfc,0x7f,0xff,0xff,0xf8};
    display.clearDisplay();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.drawBitmap(46, 17, image_Warning_bits, 30, 23, 1);
    display.setCursor(10, 46);
    display.print("STOPKNOP INGEDRUKT");
    display.display();
    selectedItem = 0;
    AdjustmodeLength = false;
    AdjustmodeSpeed = false;
    TempMode = false;
    InfoMode = false;
}


// Menu navigation function (up/down)
void DisplayController::navigateMenu(bool up) {
    if (up) {
        if (!AdjustmodeLength && !AdjustmodeSpeed && !TempMode && !InfoMode) {
            selectedItem--;
            if (selectedItem < 0) selectedItem = numItems - 1;  // Als we bovenaan zijn, ga naar beneden
        } else if (AdjustmodeLength) {
            if (*Length < 0.1) {
                *Length = 0.1;
            } else *Length = *Length - float(0.01);
        }
        else if (AdjustmodeSpeed) {
            if (*Speed < 0.01) {
                *Speed = 0.01;
            } else *Speed = *Speed - float(0.001);
        }
    } else {
        if (!AdjustmodeLength && !AdjustmodeSpeed && !TempMode && !InfoMode) {
            selectedItem++;
            if (selectedItem >= numItems) selectedItem = 0;  // Als we onderaan zijn, ga naar boven
        } else if (AdjustmodeLength) {
            if (*Length > 1.2) {
                *Length = 1.2;
            } else *Length = *Length + float(0.01);
        }
        else if (AdjustmodeSpeed) {
            if (*Speed > 0.3) {
                *Speed = 0.3;
            } else *Speed = *Speed + float(0.001);
        }
    }
    if (!AdjustmodeLength && !AdjustmodeSpeed && !TempMode && !InfoMode) {
            mainMenu();
        } else if (AdjustmodeLength) settingLength();
        else if (AdjustmodeSpeed) settingSpeed();
    
}

// Function to select
void DisplayController::selectMenu() {
    if (AdjustmodeLength || AdjustmodeSpeed || TempMode || InfoMode) {
        AdjustmodeLength = false;
        AdjustmodeSpeed = false;
        TempMode = false;
        InfoMode = false;
        mainMenu();
    } else if (selectedItem == 0) {
        scanInfo();
        InfoMode = true;
    } else if (selectedItem == 1) {
        scanInfo();
        *StartButton = true;
    } else if (selectedItem == 2) {
        settingLength();
        AdjustmodeLength = true;
    } else if (selectedItem == 3) {
        settingSpeed();
        AdjustmodeSpeed = true;
    } else if (selectedItem == 4) {
        TempScreen();
        TempMode = true;
    }
}

// Check button and change the selected option
void DisplayController::checkButtons(bool MoveUp, bool MoveDown, bool Select) {
    
    if (MoveUp == HIGH) {
        navigateMenu(true);  // Beweeg omhoog als de up-knop ingedrukt is
    }
    
    if (MoveDown == HIGH) {
        navigateMenu(false);  // Beweeg omlaag als de down-knop ingedrukt is
    }
    
    if (Select == HIGH) {
        selectMenu();  // Selecteer het item als de select-knop wordt ingedrukt
    }
}

// Speed ​​adjustment menu
void DisplayController::settingSpeed() {
    clear();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.setCursor(4, 19);
    display.print("Scansnelheid:");
    display.setCursor(85, 37);
    display.print("m/s");
    display.setCursor(45, 37);
    if (this->Speed) {  
        display.setCursor(45, 37);
        display.print(*this->Speed, 3);
    }
    updateDisplay();
}

// Length ​​adjustment menu
void DisplayController::settingLength() {
    clear();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.setCursor(4, 19);
    display.print("Scanlengte:");
    display.setCursor(85, 37);
    display.print("m");
    display.setCursor(45, 37);
    if (this->Length) {  
        display.setCursor(45, 37);
        display.print(*this->Length, 2);
    }
    updateDisplay();
}

// ScanInfo function
void DisplayController::scanInfo() {
    clear();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.setCursor(3, 17);
    display.print("Status:");
    display.setCursor(47, 17);
    display.print(*this->State);
    display.setCursor(3, 54);
    display.print("Snelheid:");
    display.setCursor(3, 43);
    display.print("Lengte:");
    display.setCursor(2, 31);
    display.print("Instellingen scan");
    display.setCursor(107, 54);
    display.print("m/s");
    display.setCursor(107, 43);
    display.print("m");
    display.setCursor(65, 54);
    display.print(*this->Speed, 3);
    display.setCursor(65, 43);
    display.print(*this->Length, 3);
    updateDisplay();
}

// Dispay screen "Temperature"
void DisplayController::TempScreen() {
    display.clearDisplay();
    display.drawRect(0, 0, 128, 64, 1);
    display.setTextColor(1);
    display.setTextWrap(false);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.setCursor(3, 22);
    display.print("T1");
    display.setCursor(21, 17);
    display.print("Temperatuur");
    display.setCursor(3, 44);
    display.print("T2");
    display.setCursor(21, 26);
    display.print("besturingskast");
    display.setCursor(21, 39);
    display.print("Temperatuur");
    display.setCursor(21, 48);
    display.print("LAB-opstelling");
    display.display();
}

// Display text on a specific line
void DisplayController::printText(const char* text, int x, int y) {
    display.setCursor(x, y);
    display.print(text);
}

// Clear screen
void DisplayController::clear() {
    display.clearDisplay();
}

// Update screen
void DisplayController::updateDisplay() {
    display.display();
}

// Link the external variable
void DisplayController::attachLength(float* length) {
    this->Length = length;  
}

// Link the external variable
void DisplayController::attachSpeed(float* speed) {
    this->Speed = speed;  // Koppel de externe variabele
}

// Link the external variable
void DisplayController::attachTemp(float* T1, float* T2) {
    this->Temp1 = T1;
    this->Temp2 = T2;
}

// Link the external variable
void DisplayController::attachState(String* MainState) {
    this->State = MainState;
}

// Update temperature on screen
void DisplayController::TempUpdate() {
    display.fillRect(1, 1, 126, 9, SSD1306_BLACK);
    display.setCursor(63, 2);
    display.print("T2");
    display.setCursor(3, 2);
    display.print("T1");
    display.setCursor(17, 2);
    display.print(String(*this->Temp1, 1) + char(247) + "C");
    display.setCursor(78, 2);
    display.print(String(*this->Temp2, 1) + char(247) + "C");
    display.drawLine(1, 10, 126, 10, 1);
    display.display();
}


// Link the external variable
void DisplayController::attachStartButton(bool* buttonStart) {
    this->StartButton = buttonStart;
}