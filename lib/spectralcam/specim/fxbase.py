from collections import deque
from typing import Union
import time
from threading import Event
import threading

import numpy as np
from genicam.genapi import NodeMap
from genicam.genapi import IValue, ICategory, ICommand, IEnumeration

from ...spectralcam.utils import *
from ...spectralcam.gige import GVCP, GVCPDiscoveryAck, PortGVCP, GVCP_PORT, gvsp
from ...spectralcam.preview import PreviewFactory
from ...spectralcam.gentl import GCDeviceInfo, DiscoverableGigeDevice
from ...spectralcam.exceptions import *

class FXBase(DiscoverableGigeDevice):
  """
  Base class to provide easy Python interface for Specim FX cameras.

  This class is not compatible with GenICam interface even though it handles the same layer in the
  application stack and incorporates some GenICam components. This is to make it easier to use and
  maintain this class as GenICam has quite many unnecessary features. If GenICam support is needed
  in the future this class can be probably used as a base for such class.
  """

  def __init__(self, dev_info: GCDeviceInfo, port: int = GVCP_PORT, preview_factory: PreviewFactory = None):

    # GVSP
    self._gvsp_port = 0
    self._gvsp_p = None
    self._is_acquiring = False

    # Buffer to save data to
    self.buffer = deque()
    self.record = False

    # Show messages in CLI
    self._verbose = False
    self.print_info = True

    # Connect GVCP
    self._gvcp = GVCP()
    self.gvcp.connect(dev_info.device.current_ip, port)
    if self._verbose:
      print("FX: Connection established")

    # Update device info
    self._info = dev_info
    self._info.device = self.gvcp.discovery(GVCPDiscoveryAck)
    if self._verbose:
      print("FX: Device info updated")

    # Fetch device description file and create nodes
    xml_str = self.gvcp.get_device_description_file()
    gc_port = PortGVCP(self.gvcp)
    gc_xml = NodeMap()
    gc_xml.load_xml_from_string(xml_str)
    gc_xml.connect(gc_port)
    self._gc_xml = gc_xml
    if self._verbose:
      print("FX: Device description file fetched")

    # Temperature monitoring
    self.en_temp_warning = True
    self.temp_update_rate = 30.0 # in seconds
    self.temp_fpga_warn = self.get("Temperature_FPGALowLimit") # in °C
    self.temp_pcb_warn = self.get("Temperature_ProcLowLimit") # in °C
    self._temp_stop = threading.Event()
    self._temp_thread = threading.Thread(target=self._check_temperature_loop)
    self._temp_thread.start()

    # Initialize preview
    self.preview = None
    spectral = self.get("Height")
    self.red_band = round(spectral * 1/6)
    self.green_band = round(spectral * 3/6)
    self.blue_band = round(spectral * 5/6)
    if preview_factory != None:
      binning = self.get("BinningHorizontal")
      width = self.get("Width")
      width = width * binning
      height = round(width * 0.75)
      self.preview = preview_factory.create(width, height, f"Preview {self.DEV_INFO_MODEL}")
    if self._verbose:
      print("FX: Preview window initialized")

  def __del__(self) -> None:
    if self.is_open:
      self.close()

  @property
  def verbose(self) -> bool:
    """Show verbose messages in terminal."""
    return self._verbose

  @verbose.setter
  def verbose(self, value: bool) -> None:
    self.gvcp.verbose = value
    if self._gvsp_p != None:
      gvsp.set_verbose(self._gvsp_p, value)
    self._verbose = value

  @property
  def gvcp(self) -> GVCP:
    """Instance of GigE Vision control channel"""
    return self._gvcp

  @property
  def is_open(self) -> bool:
    """Connection to a camera is open."""
    return self.gvcp.connected

  @property
  def is_stream_open(self) -> bool:
    """Stream channel is open (see GigE Vision specs for more info)"""
    return self.gvcp.connected and self.get("GevSCPHostPort") != 0

  @property
  def is_acquiring(self) -> bool:
    """Frame acquiring is active"""
    return self._is_acquiring

  frame_cb = None
  """Frame callback function. It is called every time a new frame is received."""

  def close(self) -> None:
    """
    Close all related resources to the camera.

    :returns: None
    :raises NotConnectedError: Already disconnected
    :raises AckError: Problem with an acknowledgement from the camera
    """
    if self.is_open:
      if self.is_stream_open:
        if self.is_acquiring:
          self.stop_acquire()
          time.sleep(0.05) # Weird behaviour of FX17 camera...
        self.close_stream()
      self._temp_stop.set()
      self._temp_thread.join()
      self.gvcp.disconnect()
    if self.preview != None:
      self.preview.hide()
    if self._verbose:
      print("FX: Device closed")

  def get_node(self, name: Union[str, int]) -> Union[IValue, None]:
    """
    Get single feature, category, etc. from camera's description file by it's name or by register address.

    :param name: Full name of the item (case sensitive)
    :returns: Feture, category, etc. or None if name does not match any item
    :raises NotConnectedError: No connection
    :raises TypeError: Invalid name
    """
    self._check_connection()
    if type(name) == str:
      return getattr(self._gc_xml, name)
    elif type(name) == int:
      for node in self._gc_xml.nodes:
        try:
          if hasattr(node, "address") and node.address == name:
            return node
        except:
          pass
    else:
      raise TypeError("Invalid name")

  def get_categories(self) -> list[ICategory]:
    """
    List camera feature categories.

    :returns: List of feature categories
    :raises NotConnectedError: No connection
    """
    self._check_connection()
    categories = []
    i = 0
    for node in self._gc_xml.nodes:
      if type(node) == ICategory:
        categories.append(node)
        if self.verbose or self.print_info:
          print("{0}: {1}".format(i, node.node.name))
        i += 1
    return categories

  def get_features(self, category: Union[None, str, ICategory] = None) -> list[IValue]:
    """
    List all features or features in a category.

    :param category: Category to list, or None to list all features
    :returns: List of camera features
    :raises NotConnectedError: No connection
    :raises TypeError: Wrong type of the category
    """
    self._check_connection()
    if type(category) == str:
      category = self.get_node(category)
    if isinstance(category, ICategory):
      nodes = category.features
    elif category == None:
      nodes = self._gc_xml.nodes
    else:
      raise TypeError("Not a category")
    features = []
    i = 0
    for feature in nodes:
      if is_feature(feature):
        features.append(feature)
        if self.verbose or self.print_info:
          print("{0}: {1}".format(i, feature.node.name))
        i += 1
    return features

  def search(self, search: str) -> list[IValue]:
    """
    Search features by their name.

    :param search: String to search
    :returns: List of features matching the search
    :raises NotConnectedError: No connection
    """
    self._check_connection()
    features = []
    i = 0
    search = search.lower()
    for feature in self._gc_xml.nodes:
      if is_feature(feature) and feature.node.name.lower().find(search) >= 0:
        features.append(feature)
        if self.verbose or self.print_info:
          print("{0}: {1}".format(i, feature.node.name))
        i += 1
    return features

  def info(self, feature: Union[str, IValue]) -> None:
    """
    Prints information about a feature.

    :param feature: Camera feature or it's name
    :returns: None
    :raises NotConnectedError: No connection
    :raises TypeError: Invalid feature
    """
    self._check_connection()
    if type(feature) == str:
      feature = self.get_node(feature)
    elif isinstance(feature, IValue):
      pass
    else:
      raise TypeError("Invalid feature type")
    if self.verbose or self.print_info:
      print(f"Name:         {feature.node.name}")
      print(f"Display name: {feature.node.display_name}")
      print(f"Type:         {type(feature).__name__}")
      print(f"Description:  {feature.node.description}")
      print(f"Tooltip:      {feature.node.tooltip}")
      print(f"Visibility:   {feature.node.visibility}")
      if isinstance(feature, IEnumeration):
        print("Enumerate entries:")
        for entry in feature.entries:
          symbolic = entry.symbolic + ":"
          print(f"  {entry.value:2} {symbolic:16} {entry.node.description}")

  def get(self, feature: Union[str, IValue]) -> any:
    """
    Read value of a feature (= register in the camera).

    :param feature: Camera feature or it's name
    :returns: Value of the feature, type depends on the feature
    :raises NotConnectedError: No connection
    :raises TypeError: Invalid feature
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_connection()
    if type(feature) == str:
      feature = self.get_node(feature)
    elif isinstance(feature, IValue):
      pass
    else:
      raise TypeError("Invalid feature type")
    if isinstance(feature, ICommand):
      return feature.is_done()
    else:
      return feature.value

  def set(self, feature: Union[str, IValue], value: any) -> None:
    """
    Write value of a feature (= register in the camera).

    :param feature: Camera feature or it's name
    :param value: Value to set
    :returns: None
    :raises NotConnectedError: No connection
    :raises TypeError: Invalid feature
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_connection()
    if type(feature) == str:
      feature_obj = getattr(self._gc_xml, feature)
    elif isinstance(feature, IValue):
      feature_obj = feature
    else:
      raise TypeError("Invalid feature type")
    if isinstance(feature_obj, ICommand):
      feature_obj.execute()
    else:
      feature_obj.value = value

  def open_stream(self) -> None:
    """
    Open GVSP stream channel and start listening for incoming frames.

    :returns: None
    :raises NotConnectedError: No connection
    :raises AckError: Problem with an acknowledgement from the camera
    :raises MemoryError: Cannot allocate memory
    :raises ValueError: Invalid GVSP packet or payload size (likely a problem with the camera or a bug)
    """
    self._check_connection()
    if self._verbose:
      print("FX: Opening stream channel...")

    def handle_frame(frame, bit_depth):
      intercept = False
      if self.frame_cb != None:
        intercept = self.frame_cb(frame, bit_depth)
      if not intercept:
        if self.record:
          self.buffer.append(frame)
        if self.preview != None and self.preview.is_visible():
          shift = bit_depth - 8
          preview = np.array([frame[self.red_band], frame[self.green_band], frame[self.blue_band]]).swapaxes(0, 1) >> shift
          self.preview.push_row(preview)

    # Initialize GVSP module to receive frames
    host_addr = self._info.host_address
    payload_size = self.get("PayloadSize")
    packet_size = self.get("DeviceStreamChannelPacketSize")
    self._gvsp_p, self._gvsp_port = gvsp.create_socket(host_addr)
    gvsp.set_frame_cb(self._gvsp_p, handle_frame)
    gvsp.create_buffer(self._gvsp_p, payload_size, packet_size)

    # Set receiver address and port
    self._set_gev_scda(ip_to_uint32(host_addr))
    self.set("GevSCPHostPort", self._gvsp_port)
    if self._verbose:
      print("FX: Stream channel open")

  def close_stream(self) -> None:
    """
    Close GVSP stream channel and stop listening for incoming frames.

    :returns: None
    :raises NotConnectedError: No connection
    :raises StreamClosedError: Stream channel is already closed
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_stream_channel()
    if self._verbose:
      print("FX: Closing stream channel...")
    self._set_gev_scda(0)
    self.set("GevSCPHostPort", 0)
    gvsp.free_buffer(self._gvsp_p)
    gvsp.close_socket(self._gvsp_p)
    if self._verbose:
      print("FX: Stream channel closed")

  def start_acquire(self, record: bool = False) -> None:
    """
    Start acquiring frames.

    :param record: Record frames. Recorded buffer will be returned by stop_acquire.
    :returns: None
    :raises NotConnectedError: No connection
    :raises StreamClosedError: Stream channel is not open
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_stream_channel()
    if self._verbose:
      print("FX: Start acquire")
    self._is_acquiring = True
    self.record = record
    gvsp.start_receive(self._gvsp_p, self._info.device.current_ip)
    self.set("AcquisitionStart", 1)

  def stop_acquire(self) -> Union[None, np.ndarray]:
    """
    Stop acquiring frames.

    :returns: Numpy array of recorded frames or None if recording was not turned on
    :raises NotConnectedError: No connection
    :raises StreamClosedError: Stream channel is not open
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_stream_channel()
    if self._verbose:
      print("FX: Stop acquire")
    self.set("AcquisitionStop", 1)
    gvsp.stop_receive(self._gvsp_p)
    self._is_acquiring = False
    if self.record:
      record = np.array(self.buffer)
      self.buffer.clear()
      return record
    else:
      return None

  def dark_ref_acquire(self, frame_count: int = 40) -> np.ndarray:
    """
    Acquire dark reference frame.

    :param frame_count: Number of frames to acquire, default is 40
    :returns: Numpy array of acquired frames
    :raises NotConnectedError: No connection
    :raises StreamClosedError: Stream channel is not open
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_stream_channel()
    if self._verbose:
      print("FX: Acquiring dark reference data")

    ready = Event()
    frame_no = 0
    old_cb = self.frame_cb
    pulse_len = 200

    def handle_count(frame, bit_depth):
      nonlocal frame_no
      frame_no += 1
      if frame_no == frame_count:
        ready.set()
      return False

    self.frame_cb = handle_count
    self.set("MotorShutter_PulseFwd", pulse_len)
    time.sleep(pulse_len / 1000)
    self.start_acquire(True)

    ready.wait()
    record = self.stop_acquire()
    self.frame_cb = old_cb
    self.set("MotorShutter_PulseRev", pulse_len)
    time.sleep(pulse_len / 1000)
    return record

  def show_preview(self) -> None:
    """
    Open preview window.

    :returns: None
    :raises NotConnectedError: No connection
    """
    self._check_connection()
    if self._verbose:
      print("FX: Showing preview window")
    if self.preview != None:
      self.preview.show()

  def hide_preview(self) -> None:
    """
    Close preview window.

    :returns: None
    """
    if self._verbose:
      print("FX: Hiding preview window")
    if self.preview != None:
      self.preview.hide()

  def preview_bands(self, red, green, blue) -> None:
    """
    Set R, G, and B bands of the preview window. Value is index of the spectral channel.

    :param red: Index for red color
    :param green: Index for green color
    :param blue: Index for blue color
    :returns: None
    """
    if self._verbose:
      print("FX: Setting preview bands")
    self.red_band = red
    self.green_band = green
    self.blue_band = blue

  def quick_init(self) -> None:
    """
    Setup camera quickly - good for testing purposes.

    :returns: None
    :raises NotConnectedError: Cannot connect
    :raises IsConnectedError: Already connected
    :raises AckError: Problem with an acknowledgement from the camera
    :raises MemoryError: Cannot allocate memory
    :raises ValueError: Invalid packet or payload size (likely a problem with the camera or a bug)
    """
    self.set_defaults()
    self.open_stream()
    self.show_preview()

  def _check_temperature_loop(self):
    if self._verbose:
      print("FX: Monitoring temperature")
    while True:
      if self.en_temp_warning:
        # genicam.genapi seems to have some problem with threads, cannot use self.get/set here :(
        self.gvcp.writereg(0x00300068, 0) # Temperature_Update
        fpga_temp = self.gvcp.readreg(0x00300050, float) # Temperature_FPGA
        processor_temp = self.gvcp.readreg(0x00300040, float) # Temperature_Proc
        if fpga_temp >= self.temp_fpga_warn:
          print(f"WARNING: FPGA temperature over {self.temp_fpga_warn} °C")
        if processor_temp >= self.temp_pcb_warn:
          print(f"WARNING: Processor PCB temperature over {self.temp_pcb_warn} °C")
      self._temp_stop.wait(self.temp_update_rate)
      if self._temp_stop.is_set():
        break

  def _check_connection(self) -> None:
    if not self.is_open:
      raise NotConnectedError(f"Not connected, ")

  def _check_stream_channel(self) -> None:
    self._check_connection()
    if not self.is_stream_open:
      raise StreamClosedError(f"Stream channel is not open, call {self.__class__.__name__}.open() first")

  def _set_gev_scda(self, address: int) -> None:
    # Error in FX17e device description XML, this register actually writable so we need to set it the hard way
    scda_addr = self.get_node("GevSCDAReg").address
    self.gvcp.writereg(scda_addr, address)
