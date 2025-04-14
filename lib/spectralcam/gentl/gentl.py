"""
  This module provides partial implementation of GenICam GenTL specification. It
  mostly handles layers above device level (system and interface). At device
  level and below, GenICam standard was not followed because it probably
  wouldn't suit the needs of this project. So basically this module makes it
  possible to find and connect to a GenICam device/camera.

  Also note that this module supports GigE Vision devices only.
"""

import socket
from typing import Union

import psutil
from psutil._common import snicaddr

from ...spectralcam.utils import ETH_MAX_MTU, netmask_to_short, ip_to_uint32, is_ipv4, is_normal_ip
from ...spectralcam.gige import GVCP_PORT, GVCPRequestId, GVCPAck, GVCPDiscoveryAck, GVCPDiscoveryCmd, GVCPForceIPCmd
from ...spectralcam.exceptions import AckError
from ...spectralcam.preview import PreviewFactory

# GenICam transport layer type codes
TLTYPE_GIGE = "GEV"

# GenICam device info codes
DEV_INFO_ID = 0
DEV_INFO_VENDOR = 1
DEV_INFO_MODEL = 2
DEV_INFO_TLTYPE = 3
DEV_INFO_DISPLAYNAME = 4
DEV_INFO_ACCESS_STATUS = 5
DEV_INFO_USER_DEFINED_NAME = 6
DEV_INFO_SERIAL_NUMBER = 7
DEV_INFO_VERSION = 8

# GenICam access status codes
DEV_ACCESS_STATUS_UNKNOWN = 0

class GCDeviceInfo:
  """Class to contain information about a device without a need to open it."""

  def __init__(self, addr: str, mask: str, device_info: GVCPDiscoveryAck) -> None:
    self.host_address = addr
    self.host_netmask = mask
    self.device = device_info

  def __str__(self) -> str:
    result = "GCDeviceInfo:\nHost:\n"
    result += f"  Host address:               {self.host_address}/{netmask_to_short(self.host_netmask)}\n"
    result += "Device:\n"
    result += "\n".join(list(map(lambda row: (f"  {row}"), str(self.device).split("\n"))))
    return result

  def get(self, cmd: int) -> Union[str, int]:
    """
    Get specific information about the device in GenICam specified format.
    
    :param cmd: Information to get (DEV_INFO_* constant)
    :returns: Requested information
    :raises NotImplementedError: Requested information is not supported
    """
    if cmd == DEV_INFO_ID:
      return self.device.mac_address
    elif cmd == DEV_INFO_VENDOR:
      return self.device.manufacturer_name
    elif cmd == DEV_INFO_MODEL:
      return self.device.model_name
    elif cmd == DEV_INFO_TLTYPE:
      return TLTYPE_GIGE # Only GigE Vision cameras are supported at the moment
    elif cmd == DEV_INFO_DISPLAYNAME:
      return self.device.model_name
    elif cmd == DEV_INFO_ACCESS_STATUS:
      return DEV_ACCESS_STATUS_UNKNOWN
    elif cmd == DEV_INFO_USER_DEFINED_NAME:
      return self.device.user_defined_name
    elif cmd == DEV_INFO_SERIAL_NUMBER:
      return self.device.serial_number
    elif cmd == DEV_INFO_VERSION:
      return self.device.device_version
    else:
      raise NotImplementedError(f"Info command {cmd} is not implemented")

class GCDevice:
  """
  Abstract class for GenICam devices.

  This class roughly implements GenICam GenTL Dev* functions for GigE Vision devices.
  """
  def __init__(self, dev_info: GCDeviceInfo) -> None:
    self._info: GCDeviceInfo = dev_info
    raise NotImplementedError("This is an abstract class - concrete implementation is required")

  is_open: bool = False

  def close(self) -> None:
    raise NotImplementedError("This is an abstract class - concrete implementation is required")

  def get_info(self, cmd: int = None) -> Union[GCDeviceInfo, str, int]:
    """
    Get information about this device.

    :param cmd: Specify the information to get (DEV_INFO_* constant)
    :returns: GCDeviceInfo object or requested information
    """
    if cmd == None:
      return self._info
    else:
      return self._info.get(cmd)

class DiscoverableGigeDevice(GCDevice):
  DEV_INFO_VENDOR: str = ""
  DEV_INFO_MODEL: str = ""

IF_INFO_ID = 0
IF_INFO_DISPLAYNAME = 1
IF_INFO_TLTYPE = 2

class GCInterfaceInfo:
  """Class to contain information about an interface without a need to open it."""

  def __init__(self, if_name: str, addrs: list[snicaddr]) -> None:
    self.name = if_name
    self.addrs = addrs

  def __str__(self) -> str:
    result = f"GCInterfaceInfo: interface {self.name}"
    for addr in self.addrs:
      result += f"\n  {addr.family.name} {addr.address}/{netmask_to_short(addr.netmask)}"
    return result

  def get(self, cmd: int) -> str:
    """
    Get specific information about the interface in GenICam specified format.
    
    :param cmd: Information to get (IF_INFO_* constant)
    :returns: Requested information
    :raises NotImplementedError: Requested information is not supported
    """
    if cmd == IF_INFO_ID:
      return self.name
    elif cmd == IF_INFO_DISPLAYNAME:
      return self.name
    elif cmd == IF_INFO_TLTYPE:
      return TLTYPE_GIGE # Only GigE Vision cameras are supported at the moment
    else:
      raise NotImplementedError(f"Info command {cmd} is not implemented")

class GCInterface:
  """
  Class to find GigE Vision cameras connected to the interface.

  This class roughly implements GenICam GenTL IF* functions for GigE Vision devices. The
  implementation is not strictly 1:1 according to GenICam specification, but it should require only
  reasonable amount of work to reprogram it to fully support GenICam.

  For this to work make sure that:
   - The interface has IP-address and netmask set in same subnet as the camera
   - GVCP default port UDP 3956 is open for incoming traffic
  """

  def __init__(self, if_info: GCInterfaceInfo) -> None:
    self._info = if_info
    self._existing_devs: dict[str, GCDeviceInfo] = {}
    self._open_devs: list[GCDevice] = []
    self._is_open = True
    self._socs: list[socket.socket] = []
    self._req_id = GVCPRequestId()

    for addr in self._info.addrs:
      soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      soc.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
      soc.bind((addr.address, GVCP_PORT))
      self._socs.append(soc)

  def __del__(self) -> None:
    if self.is_open:
      self.close()

  @property
  def is_open(self) -> bool:
    """Interface instance is open."""
    return self._is_open

  @property
  def open_devices(self) -> list[GCDevice]:
    """List of devices that have already been opened."""
    self._check_open()
    open_devices = list(filter(lambda dev: (dev.is_open), self._open_devs))
    self._open_devs = open_devices
    return open_devices

  def close(self) -> None:
    """
    Close the interface and all related devices.
    """
    self._check_open()
    for soc in self._socs:
      soc.close()
    for device in self.open_devices:
      device.close()
    self._is_open = False

  def get_info(self, cmd: int = None) -> Union[GCInterfaceInfo, str]:
    """
    Get information about this interface.

    :param cmd: Specify the information to get (IF_INFO_* constant)
    :returns: GCInterfaceInfo object or requested information
    """
    self._check_open()
    if cmd == None:
      return self._info
    else:
      return self._info.get(cmd)

  def get_device_id(self, index: int) -> str:
    """
    Get static identifier of a device.
    update_device_list must be called first.

    :param index: Index of the device
    :returns: Static identifier of the device
    :raises RuntimeError: Interface is closed
    :raises IndexError: Invalid index
    """
    self._check_open()
    return list(self._existing_devs.keys())[index]

  def get_device_info(self, id: str, cmd: int = None) -> Union[GCDeviceInfo, str, int]:
    """
    Get information about a device.
    update_device_list must be called first.

    :param id: Static ID of the device
    :param cmd: Specify the information to get (DEV_INFO_* constant)
    :returns: GCDeviceInfo object or requested information
    :raises RuntimeError: Interface is closed
    :raises KeyError: Invalid ID
    """
    self._check_open()
    if cmd == None:
      return self._existing_devs[id]
    else:
      return self._existing_devs[id].get(cmd)

  def get_num_devices(self) -> int:
    """
    Get number of devices.
    update_device_list must be called first.

    :returns: Number of devices connected to the interface
    :raises RuntimeError: Interface is closed
    """
    self._check_open()
    return len(self._existing_devs.values())

  def open_device(self, id: str, device_type: GCDevice = GCDevice, *args) -> GCDevice:
    """
    Create new instance of a device to configure it and to acquire images.
    update_device_list must be called first.

    :param id: Static ID of the device
    :param device_type: Class that needs to match the device you are trying to connect
    :returns: New instance of the device class
    :raises RuntimeError: Interface is closed or device is already open
    :raises KeyError: ID does not exist
    """
    self._check_open()
    for dev in self.open_devices:
      if id == dev.get_info(IF_INFO_ID):
        raise RuntimeError("Device is already open")
    dev = device_type(self._existing_devs[id], *args)
    self._open_devs.append(dev)
    return dev

  def update_device_list(self, timeout: float = 0.5, ack_bcast: bool = False) -> None:
    """
    Find all GigE Vision devices connected to this interface.

    :param timeout: Time to wait for an answer from devices (in seconds)
    :param ack_bcast: Allow cameras to broadcast their acknowledgement. Note that this application cannot receive broadcasted acknowledgements.
    :raises RuntimeError: Interface is closed
    """
    self._check_open()
    self._existing_devs = {}
    for i, addr in enumerate(self._info.addrs):
      soc = self._socs[i]
      soc.settimeout(timeout)
      for discovery in self.gvcp_discovery(soc, ack_bcast):
        self._existing_devs.update({ discovery.mac_address: GCDeviceInfo(addr.address, addr.netmask, discovery) })

  def gvcp_discovery(self, soc: socket.socket, ack_bcast: bool = False) -> list[GVCPDiscoveryAck]:
    """
    Send GVCP DISCOVERY command to cameras.

    :param soc: Socket to send and receive data
    :param ack_bcast: Allow cameras to broadcast their acknowledgement
    :returns: List discovery acknowledgement objects
    :raises RuntimeError: Interface is closed
    """
    self._check_open()
    devices = []

    request = GVCPDiscoveryCmd(self._req_id.get(), ack_bcast)
    soc.sendto(request.data, ("255.255.255.255", GVCP_PORT))

    # Listen for DISCOVERY_ACK
    while True:
      try:
        data = soc.recv(ETH_MAX_MTU)
      except socket.timeout:
        break

      # Add DISCOVERY_ACK to list of devices
      try:
        response = GVCPDiscoveryAck(data)
        if response.ack_id == request.req_id:
          devices.append(response)
      except AckError:
        pass
    return devices

  def gvcp_forceip(self, mac: str, ip: str, netmask: str = None, def_gateway: str = "0.0.0.0", force: bool = False, ack: bool = True, ack_bcast: bool = None, timeout: float = 0.5) -> Union[None, GVCPAck]:
    """
    Send GVCP FORCEIP command to a camera.
    By default force IP command is sent through a socket with matching network address. If netmask
    is not given it is determined automatically. Use parameter 'force' if you want to set an IP
    address that is not on the host network or you want restart camera's IP configuration cycle
    (using address 0.0.0.0). Note that this implementation cannot receive broadcasted
    acknowledgements from the camera due to limitations of Python.

    Example use:
    # List interfaces
    for i in range(system.get_num_interfaces()):
        print(system.get_interface_info(system.get_interface_id(i)))
    # Open the interface the camera is connected to (replace x with index of the interface or use ID directly)
    intf = system.open_interface(system.get_interface_id(x))
    # Send FORCEIP command (replace MAC and IP addresses with correct ones)
    intf.gvcp_forceip("12:34:56:78:9a:bc", "169.254.0.1")

    :param mac: MAC address of the camera
    :param ip: Desired IP address for the camera or 0.0.0.0 to trigger camera's IP configuration cycle again
    :param netmask: Desired netmask for the camera. Will be determined automatically based on host IP config if left empty.
    :param def_gateway: Desired default gateway for the camera
    :param force: Force command even if network does not match to host. In this case you won't be able to communicate with the camera.
    :param ack: Wait for acnowledgement from camera
    :param ack_bcast: Allow camera to broadcast it's acknowledgement
    :param timeout: How long to wait for acknowledgement (in seconds)
    :returns: None if parameter 'ack' is False or otherwise object containing acknowledgement from the camera
    :raises RuntimeError: Interface is closed
    :raises ValueError: Wrong network or netmask is not defined
    :raises socket.timeout: Acknowledgement was not received in time
    :raises AckError: Invalid acknowledgement from camera
    """
    self._check_open()

    target_ip_int = ip_to_uint32(ip)
    sel_soc = None
    request = None

    # Restart camera's IP configuration cycle
    if target_ip_int == 0:
      if ack_bcast == None: ack_bcast = False
      request = GVCPForceIPCmd(self._req_id.get(), mac, ip, "0.0.0.0", "0.0.0.0", ack_bcast, ack)
      sel_soc = self._socs[0]

    # Force IP regardless of host network settings
    elif force:
      if ack_bcast == None: ack_bcast = True
      if netmask == None:
        raise ValueError("Netmask must be defined if force is used.")
      request = GVCPForceIPCmd(self._req_id.get(), mac, ip, netmask, def_gateway, ack_bcast, ack)
      sel_soc = self._socs[0]

    # Force IP so that it allows host to communicate with the camera afterwards
    else:
      sel_netmask = None
      for i, addr in enumerate(self._info.addrs):
        mask_int = ip_to_uint32(addr.netmask)
        host_ip_int = ip_to_uint32(addr.address)
        if (host_ip_int & mask_int) == (target_ip_int & mask_int) and (netmask == addr.netmask or netmask == None):
          sel_netmask = addr.netmask
          sel_soc = self._socs[i]
          break
      if sel_netmask != None and sel_soc != None:
        if ack_bcast == None: ack_bcast = False
        request = GVCPForceIPCmd(self._req_id.get(), mac, ip, sel_netmask, def_gateway, ack_bcast, ack)
      else:
        raise ValueError("Network is not found on this interface.")

    # Send command
    sel_soc.settimeout(timeout)
    sel_soc.sendto(request.data, ("255.255.255.255", GVCP_PORT))

    # Wait for response
    if ack:
      data = sel_soc.recv(ETH_MAX_MTU)
      return GVCPAck(data)

  def _check_open(self):
    if not self.is_open:
      raise RuntimeError("Interface is closed")

class GCSystem:
  """
  Class to find GigE Vision cameras in local network.

  This class roughly implements GenICam GenTL TL* functions for GigE Vision devices. The
  implementation is not strictly 1:1 according to GenICam specification, but it should require only
  reasonable amount of work to reprogram it to fully support GenICam.
  """

  def __init__(self) -> None:
    self._existing_intfs: dict[str, GCInterfaceInfo] = {}
    self._open_intfs: list[GCInterface] = []
    self._is_open = True
    self.preview_factory = PreviewFactory()

  def __del__(self) -> None:
    if self.is_open:
      self.close()

  @property
  def is_open(self) -> bool:
    """System instance is open."""
    return self._is_open

  @property
  def open_interfaces(self) -> list[GCInterface]:
    """List of interfaces that have already been opened."""
    self._check_open()
    open_interfaces = list(filter(lambda inf: (inf.is_open), self._open_intfs))
    self._open_intfs = open_interfaces
    return open_interfaces

  def close(self) -> None:
    """
    Close the system object and all related interfaces.

    :raises RuntimeError: System is closed
    """
    self._check_open()
    for intf in self.open_interfaces:
      intf.close()
    self.preview_factory.join()
    self._is_open = False

  def get_interface_id(self, index: int) -> str:
    """
    Get static identifier of an interface.
    update_interface_list must be called first.

    :param index: Index of the interface
    :returns: Static identifier of the interface
    :raises RuntimeError: System is closed
    :raises IndexError: Invalid index
    """
    self._check_open()
    return list(self._existing_intfs.keys())[index]

  def get_interface_info(self, id: str, cmd: int = None) -> Union[GCInterfaceInfo, str]:
    """
    Get information about an interface.
    update_interface_list must be called first.

    :param id: Static ID of the interface
    :param cmd: Specify the information to get (IF_INFO_* constant)
    :returns: GCInterfaceInfo object or requested information
    :raises RuntimeError: System is closed
    :raises KeyError: Invalid ID
    """
    self._check_open()
    if cmd == None:
      return self._existing_intfs[id]
    else:
      return self._existing_intfs[id].get(cmd)

  def get_num_interfaces(self) -> int:
    """
    Get number of interfaces.
    update_interface_list must be called first.

    :returns: Number of interfaces
    :raises RuntimeError: System is closed
    """
    self._check_open()
    return len(self._existing_intfs.values())

  def open_interface(self, id: str) -> GCInterface:
    """
    Create new instance of an interface to search and connect to cameras.
    update_interface_list must be called first.

    :param id: Static ID of the interface
    :returns: New instance of the interface class
    :raises RuntimeError: System is closed or interface is already open
    :raises KeyError: ID does not exist
    """
    self._check_open()
    for intf in self.open_interfaces:
      if id == intf.get_info(IF_INFO_ID):
        raise RuntimeError("Interface is already open")
    intf = GCInterface(self._existing_intfs[id])
    self._open_intfs.append(intf)
    return intf

  def update_interface_list(self) -> None:
    """
    Find available interfaces and their IP addresses on the system.

    :raises RuntimeError: System is closed
    """
    self._check_open()
    self._existing_intfs = {}
    interfaces = psutil.net_if_addrs()
    stats_dict = psutil.net_if_stats()
    keys = interfaces.keys()
    for key in keys:
      try:
        stats = stats_dict[key]
        isup = stats.isup
      except KeyError:
        isup = False
      if isup:
        addrs = interfaces[key]
        addrs = list(filter(lambda addr: (addr.family == socket.AF_INET and is_ipv4(addr.address)), addrs))
        self._existing_intfs.update({key: GCInterfaceInfo(key, addrs)})

  def discover(self, device_type: DiscoverableGigeDevice, timeout: float = 0.2, all: bool = False) -> tuple[GCDevice, GCInterface]:
    """
    Short hand to search GigE Vision compatible devices (cameras). By default it will connect
    automatically if only one matching device is found. Otherwise user will be prompted to select a
    device.

    :param device_type: Class that implements the device you are trying to connect to
    :param timeout: How long to wait for responses from devices
    :param all: Lists all devices and forces not to connect automatically
    :returns: Instance of GenTL device (camera) and interface
    """
    dev_list: list[tuple[str, GCInterface]] = []
    inf_list: list[GCInterface] = []

    # Find all devices from all interfaces
    self.update_interface_list()
    inf_len = self.get_num_interfaces()
    for inf_index in range(inf_len):

      # Open an interface
      inf_id = self.get_interface_id(inf_index)
      filtered_inf = tuple(filter(lambda inf: inf.get_info(IF_INFO_ID) == inf_id, self.open_interfaces))
      if len(filtered_inf) > 0:
        [inf] = filtered_inf
      else:
        inf = self.open_interface(inf_id)
      inf_list.append(inf)

      # Find devices connected to the interface
      inf_addrs = inf.get_info().addrs
      inf_addrs = list(filter(is_normal_ip, inf_addrs))
      if len(inf_addrs) > 0:
        inf.update_device_list(timeout)
        dev_len = inf.get_num_devices()
        for dev_index in range(dev_len):
          dev_id = inf.get_device_id(dev_index)
          dev_vendor = inf.get_device_info(dev_id, DEV_INFO_VENDOR)
          dev_model = inf.get_device_info(dev_id, DEV_INFO_MODEL)
          if all or (device_type.DEV_INFO_VENDOR == dev_vendor and device_type.DEV_INFO_MODEL == dev_model):
            dev_list.append((dev_id, inf))

    # Select device to open from found devices
    open_device: GCDevice = None
    open_interface: GCInterface = None

    # No devices was found
    if len(dev_list) == 0:
      return None, None

    # Found 1 matching device - open automatically
    elif not all and len(dev_list) == 1:
      print(f"Found 1 matching camera")
      dev_id, inf = dev_list[0]
      dev_info = inf.get_device_info(dev_id)
      open_device = inf.open_device(dev_id, device_type, GVCP_PORT, self.preview_factory)
      open_interface = inf
      if open_device.is_open:
        print(f"Connected to {dev_info.device.mac_address}")


    # Found more than 1 device
    else:
      return None, None

    # Close unnecessary interfaces
    for inf in inf_list:
      if len(inf.open_devices) == 0:
        inf.close()

    return (open_device, open_interface)

  def _check_open(self):
    if not self.is_open:
      raise RuntimeError("Interface is closed")
