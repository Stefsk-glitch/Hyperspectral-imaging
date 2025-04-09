# GigE Vision camera controller

Purpose of this library is to configure and to receive data from GigE Vision cameras in general, and especially Specim models FX10 and FX17. Main features are:
- FX10 and FX17 classes to provide easy interface for Specim cameras
- Discover function to connect to a camera easily
- A preview to display acquired data
- Almost complete implementation of GigE Vision specification
- Partial implementation of GenICam GenTL specification

## Basic usage

### Install

This example uses conda, but you don't have to use it. If you want to install both hyperspectral camera and linear scanner controllers, see readme file in the project root folder.
```
git clone https://gitlab.jyu.fi/jpasonen/linear-scanner-controller.git
conda create -n env python=3.10
conda activate env
pip install ./linear-scanner-controller/spectralcam
```

If you get errors about missing gvsp module, check section "Compiling extension modules" below.

### Open a connection

To open a connection to a camera (FX17 for example). First start python with: ```python -i```, then run:
```
from spectralcam.specim import FX17
from spectralcam.gentl import GCSystem

system = GCSystem() # This must be done only once during the program execution
fx17, intf = system.discover(FX17)
```

For the code above to work you need to make sure:
- Network cable is properly connected
- Host computer network interface has an IP address
  - IP address must be in the same network than the camera
- UDP port 3956 must be open for incoming traffic on the firewall
- Wait around 1 minute for the camera to boot
- See chapter "IP and firewall settings" for details

If you don't know the network IP address of the camera, you can force the IP using the MAC address (this method uses GenTL interface directly so a bit more manual work is needed):
```
from spectralcam.specim import FX17
from spectralcam.gentl import GCSystem

system = GCSystem()
system.update_interface_list()

# List interfaces (for your information only)
for i in range(system.get_num_interfaces()):
    print(system.get_interface_info(system.get_interface_id(i)))

# Open the interface the camera is connected to (replace x with index of the interface or use ID directly)
intf = system.open_interface(system.get_interface_id(x))

# Send FORCEIP command (replace MAC and IP addresses with correct ones)
intf.gvcp_forceip("12:34:56:78:9a:bc", "169.254.54.199")

# Open camera
fx17, intf = system.discover(FX17)
```

### Configure the camera

To get quickly started, you can just run:
```
fx17.quick_init()
```

Or if you want to change camera parameters (binning for example):
```
fx17.set_defaults(frame_rate=15.0, exposure_time=3000.0) # Not necessary if you know what you are doing

# Here you can make all sorts of configurations
fx17.set("BinningHorizontal", 2)

fx17.open_stream() # You need to open the stream channel to be able to acquire images
fx17.show_preview() # Show preview window
```

Here's more detailed example of changing and reading camera parameters. Lets set horizontal binning of FX10 for example:
```
fx10.get("Width") # Get the width of the frame.
confs = fx10.search("binning") # Search parameters for "binning". You'll see a list of matching parameters.
fx10.info("BinningHorizontal") # Show information about about the parameter. "HorizontalBinning" is from the output of the previous command.
fx10.get("BinningHorizontal") # Get current value of horizontal binning. It should be 1.
fx10.set("BinningHorizontal", 2) # Set a new value.
fx10.get(confs[0]) # Check the value again. You can also use the output of the search command or a string like the lines above.
fx10.get("Width") # Check width again, it should be now half of the original.
```

### Acquire image data

To capture images to the ```data``` variable:
```
fx17.start_acquire(True)
data = fx17.stop_acquire()
```

Or to just preview without capturing:
```
fx17.start_acquire()
fx17.stop_acquire()
```

To change preview bands:
```
fx17.get("Height") # Get number of spectral channels
fx17.preview_bands(100, 120, 140) # Set bands using index numbers of the channels
```
By default, red, green, and blue bands are set to 1/6, 3/6, 5/6 of the width of the spectral range.

### Quitting

When you are done, close everything. Closing the system will also close related interfaces and cameras. QT will likely print a few warnings when you exit the python terminal, but that shouldn't cause any harm.
```
system.close()
```

You can also close an individual camera or an interface the same way:
```
fx17.close()
intf.close()
```

### IP and firewall settings (on Windows)

Windows seems to be able to set an IP address automatically when a camera is connected. If not you can set static IP address from: Control Panel -> Network and Internet -> Network Connections -> Properties (in context menu) -> Internet Protocol Version 4 (TCP/IPv4) -> Properties -> General.

### IP and firewall settings (on Linux)

Linux distros are different so what is described here might or might not work on your computer. The most obvious way is to use your distro's built in graphical network settings to set the IP addresses manually.

Or you can set an IP the old fashioned way from a command line. First make sure network ~~damager~~ manager or a similar tool is not tinkering your settings. Then to list all interfaces and their IP addresses run ```ip addr```. To add a manual IP address (replace the IP, network mask, and interface name with correct ones) run ```sudo ip addr add 169.254.54.197/16 dev eth0```.

To open a port for incoming GigE Vision traffic run: ```sudo firewall-cmd --add-port 3956/udp```. Check if it worked by listing all firewall rules: ```sudo firewall-cmd --list-ports```. You should see a line with "3956/UDP".

### Compiling extension modules

Normally you shoudn't need to compile anything, because this library includes pre-compiled binary of C extension modules (gvsp.c is the only one) for Windows 10 and GNU/Linux. However if the pre-compiled version does not work on your system or you need to modify it, you need to compile it yourself. To do this you need a C compiler (usually gcc on Linux or MSVC on Windows). Then run:
```
cd linear-scanner-controller/spectralcam/spectralcam/gige/
python setup.py build_ext --inplace
```

You might need to install dependencies manually, see the setup.py file.

## Library structure

```
┌────────────────────────────────────────────────────┐
│                   gentl.GCSystem                   │
│                                                    │
└─────────────────────────┬──────────────────────────┘
                          │ open
                          ▼
┌────────────────────────────────────────────────────┐
│                 gentl.GCInterface                  │
│                                                    │
└─────────────────────────┬──────────────────────────┘
                          │ open
                          ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃               fx10.FX10 / fx17.FX17                ┃
┃          Software instance of the camera.          ┃
┃                                                    ┃
┃ ┌────────────────────┐                             ┃
┃ │   gvcp.PortGVCP    │                             ┃
┃ │                    │                             ┃
┃ │ get(...), set(...) │                             ┃
┃ └──────┬─────────────┘                             ┃
┃        │                                           ┃
┃ ┌──────▼──────┐ ┌─────────────┐  ┌───────────────┐ ┃
┃ │  gvcp.GVCP  │ │    gvsp.c   │  │preview.Preview│ ┃
┃ │             │ │             │  │               │ ┃
┃ │  Configure  │ │   Receive   ├──►  View images  │ ┃
┃ │  camera     │ │   images    │  │               │ ┃
┃ └──────┬──────┘ └──────▲──────┘  └───────────────┘ ┃
┗━━━━━━━━│━━━━━━━━━━━━━━━│━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
         │               │
         └───────┬───────┘
        ethernet │
      connection │
        ┌────────▼────────┐
        │                 │
        │  Actual camera  │
        │                 │
        └─────────────────┘
```
### FX10 and FX17

These classes provide an easy command line interface for Specim cameras FX10e and FX17e. See docstrings for detailed information of a method (e.g.  ```help(fx10.set)```). Methods in these classes can be roughly separated in few categories as follows:

```close``` is the only method implemented from GenTL specification. It closes all connections and frees up used memory etc.

```get_node, get_categories, get_features, search, info, get, set``` are used to view and use features of the camera. Features are defined in a device description file in the camera. It is received when you connect to the camera.

```open_stream, close_stream``` are used to open a stream channel. The channel needs to be open to be able to receive images from the camera. See GigE Vision specification for more information.

```start_acquire, stop_acquire, dark_ref_acquire``` are used to acquire image data from the camera.

```show_preview, hide_preview, preview_bands``` are used to control the preview window.

```set_defaults, quick_init``` are shortcuts for setting up the camera.

### GigE Vision

GiGE Vision defines the hardware and low level communication between a host system and a camera. It is compatible with GenICam and basically functions as a driver for the GenICam. It consists of two main modules: GVCP (GigE Vision Control Protocol) and GVSP (GigE Vision Streaming Protocol). GVCP defines how to read and write settings on a camera, while GVSP defines how to receive image data from the camera. The whole specification can be found on the internet.

This library implements most of GigE Vision features. It can be used to communicate with any GigE Vision compatible device, not only Specim cameras. GVSP module is written in C because Python is too slow to handle the data stream. Some notable missing features are: message channel, extended ID, some pixel formats.

### GenICam

GenICam standard defines software interfaces to control cameras and to receive data from them. It consist of multiple parts of which two are relevant for this library: GenAPI and GenTL. GenICam is compatible with multiple lower level specifications like GigE Vision and Camera Link, but this library supports GigE Vision only. The whole specification can be found on the internet.

GenAPI defines a standard way to read from and write settings to a camera. An official implementation is used for GenAPI (genicam package). Methods ```get``` and ```set``` in the FXBase class are the main way to use GenAPI.

GenTL defines software interfaces to open connections, to open data streams, and other very basic functions. The basic idea is that from one level you can open the next one, in following order: system -> interface -> device -> data stream -> buffer. In this implementation this schema is only partially followed. GCSystem, GCInterface, and GCDevice (partially) classes follow this pattern, but from device level onwards it is not implemented. This is because GenTL is not very human friendly to use, so implementing it would have just added another layer of complexity. FXBase and other FX* classes implement features defined in device, data stream, and buffer levels for Specim cameras.

### GCSystem.discover

Discover function is not part of GenICam, but it is added to provide an easy way to connect to a camera. It basically searches through all interfaces for a specified type of a camera. When the camera is found, it will return an instance of the camera and the interface. You can also use gentl lower level functions directly to accomplish the same thing, but it requires more manual work.

### Preview

Preview window shows 3 selected spectral bands in RGB colors. It is a slightly modified class from https://github.com/genicam/harvesters.
