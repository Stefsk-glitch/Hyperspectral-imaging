# Hyperspectral-imaging
FX10 Camera made by Specim

# Using the project
Install Anaconda using: https://www.anaconda.com/download/success </br>
Open Anaconda Prompt </br>
Type ```conda -V``` to check if Anaconda is succesfully installed </br>
Type ```conda create -n env python=3.10.16 anaconda``` </br>
Type ```conda activate env``` </br>
Type ```git clone https://github.com/Stefsk-glitch/Hyperspectral-imaging``` </br>
Type ```pip install -r requirements.txt``` </br>


# Running the app on Linux
## Install Python 3.10.16
- ```wget https://www.python.org/ftp/python/3.10.16/Python-3.10.16.tgz```
```tar xzf Python-3.10.16.tgz```
```cd Python-3.10.16```
```sudo apt install tk-dev tcl-dev```
- ```./configure --enable-optimizations```
- ```sudo make altinstall```

## Create an environment inside of the project root floder
- ```python3.10 -m venv venv```
- ```source venv/bin/activate```
- ```pip install -r requirements.txt```

## Run the app
Inside of venv environment, run: ```python main.py```