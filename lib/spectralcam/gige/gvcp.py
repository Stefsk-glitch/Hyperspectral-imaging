"""
  This module implements GVCP part of GigE Vision specification. It should be
  100% compatible with GVCP specification and together with gvsp.c these modules
  implement most of GigE Vision features.

  These modules can be used as drivers for GenICam if needed. Partially this has
  been done already as PortGVCP class provides the port interface for official
  GenAPI implementation to access cameras GVCP registers.
"""
import io
import socket
import threading
from typing import Iterable, Union, Any
import zipfile

import numpy as np
from genicam.genapi import AbstractPort, EAccessMode

from ...spectralcam.utils import *
from ...spectralcam.exceptions import *

# Misc general GVCP constants
GVCP_KEY = 0x42
GVCP_PORT = 3956
GVCP_HEADER_SIZE = 8
GVCP_MAX_PAYLOAD_SIZE = IP4_MAX_MTU - (IP4_HEADER_SIZE + UDP_HEADER_SIZE + GVCP_HEADER_SIZE)
READMEM_HEADER_SIZE = 4
READMEM_MAX_PAYLOAD_SIZE = GVCP_MAX_PAYLOAD_SIZE - READMEM_HEADER_SIZE
# TODO Support for extended id?

# GVCP command and acknowledgement codes
DISCOVERY_CMD = 0x0002
DISCOVERY_ACK = 0x0003
FORCEIP_CMD = 0x0004
FORCEIP_ACK = 0x0005
PACKETRESEND_CMD = 0x0040
READREG_CMD = 0x0080
READREG_ACK = 0x0081
WRITEREG_CMD = 0x0082
WRITEREG_ACK = 0x0083
READMEM_CMD = 0x0084
READMEM_ACK = 0x0085
WRITEMEM_CMD = 0x0086
WRITEMEM_ACK = 0x0087
PENDING_ACK = 0x0089
EVENT_CMD = 0x00C0
EVENT_ACK = 0x00C1
EVENTDATA_CMD = 0x00C2
EVENTDATA_ACK = 0x00C3
ACTION_CMD = 0x0100
ACTION_ACK = 0x0101
def format_cmd_ack_name(val: int) -> str:
  """Get name of GigE Vision command / acknowledgement"""
  if val == DISCOVERY_CMD:
      return "DISCOVERY_CMD"
  if val == DISCOVERY_ACK:
      return "DISCOVERY_ACK"
  if val == FORCEIP_CMD:
      return "FORCEIP_CMD"
  if val == FORCEIP_ACK:
      return "FORCEIP_ACK"
  if val == PACKETRESEND_CMD:
      return "PACKETRESEND_CMD"
  if val == READREG_CMD:
      return "READREG_CMD"
  if val == READREG_ACK:
      return "READREG_ACK"
  if val == WRITEREG_CMD:
      return "WRITEREG_CMD"
  if val == WRITEREG_ACK:
      return "WRITEREG_ACK"
  if val == READMEM_CMD:
      return "READMEM_CMD"
  if val == READMEM_ACK:
      return "READMEM_ACK"
  if val == WRITEMEM_CMD:
      return "WRITEMEM_CMD"
  if val == WRITEMEM_ACK:
      return "WRITEMEM_ACK"
  if val == PENDING_ACK:
      return "PENDING_ACK"
  if val == EVENT_CMD:
      return "EVENT_CMD"
  if val == EVENT_ACK:
      return "EVENT_ACK"
  if val == EVENTDATA_CMD:
      return "EVENTDATA_CMD"
  if val == EVENTDATA_ACK:
      return "EVENTDATA_ACK"
  if val == ACTION_CMD:
      return "ACTION_CMD"
  if val == ACTION_ACK:
      return "ACTION_ACK"

# GVCP Status codes
GEV_STATUS_SUCCESS = 0x000
GEV_STATUS_PACKET_RESEND = 0x100
GEV_STATUS_NOT_IMPLEMENTED = 0x001
GEV_STATUS_INVALID_PARAMETER = 0x002
GEV_STATUS_INVALID_ADDRESS = 0x003
GEV_STATUS_WRITE_PROTECT = 0x004
GEV_STATUS_BAD_ALIGNMENT = 0x005
GEV_STATUS_ACCESS_DENIED = 0x006
GEV_STATUS_BUSY = 0x007
GEV_STATUS_PACKET_UNAVAILABLE = 0x00c
GEV_STATUS_DATA_OVERRUN = 0x00d
GEV_STATUS_INVALID_HEADER = 0x00e
GEV_STATUS_PACKET_NOT_YET_AVAILABLE = 0x010
GEV_STATUS_PACKET_AND_PREV_REMOVED_FROM_MEMORY = 0x011
GEV_STATUS_PACKET_REMOVED_FROM_MEMORY = 0x012
GEV_STATUS_NO_REF_TIME = 0x013
GEV_STATUS_PACKET_TEMPORARILY_UNAVAILABLE = 0x014
GEV_STATUS_OVERFLOW = 0x015
GEV_STATUS_ACTION_LATE = 0x016
GEV_STATUS_ERROR = 0xfff

# Some GVCP bootstrap register addresses etc.
REG_FIRST_URL = 0x00000200
REG_FIRST_URL_LEN = 512
REG_CCP = 0x00000A00
VAL_CONTROL_ACCESS = 0x00000002
REG_HEARTBEAT_TIMEOUT = 0x00000938
REG_GVCP_CAPABILITY = 0x00000934

# GVCP device mode: Endianess
DEV_MODE_LITTLE_ENDIAN = 0
DEV_MODE_BIG_ENDIAN = 1
def format_dev_mode_endianess(endianess: int) -> str:
  """Return human readable representation of the device bit endianess code."""
  if endianess == DEV_MODE_LITTLE_ENDIAN:
    return "LE (illegal)"
  elif endianess == DEV_MODE_BIG_ENDIAN:
    return "BE"
  else:
    return "Unknown"

# GVCP device mode: Device class
DEV_MODE_CLASS_TRANSMITTER = 0
DEV_MODE_CLASS_RECEIVER = 1
DEV_MODE_CLASS_TRANSCEIVER = 2
DEV_MODE_CLASS_PERIPHERAL = 3
def format_dev_mode_class(dev_class: int) -> str:
  """Return human readable representation of the device class code."""
  if dev_class == DEV_MODE_CLASS_TRANSMITTER:
    return "Transmitter"
  elif dev_class == DEV_MODE_CLASS_RECEIVER:
    return "Receiver"
  elif dev_class == DEV_MODE_CLASS_TRANSCEIVER:
    return "Transceiver"
  elif dev_class == DEV_MODE_CLASS_PERIPHERAL:
    return "Peripheral"
  else:
    return "Unknown"

# GVCP device mode: Current link configuration
DEV_MODE_LINK_SINGLE = 0
DEV_MODE_LINK_MULTI = 1
DEV_MODE_LINK_STATIC_LAG = 2
DEV_MODE_LINK_DYNAMIC_LAG = 3
def format_dev_mode_link(link_conf: int) -> str:
  """Return human readable representation of the current link configuration code."""
  if link_conf == DEV_MODE_LINK_SINGLE:
    return "Single link"
  elif link_conf == DEV_MODE_LINK_MULTI:
    return "Multi link"
  elif link_conf == DEV_MODE_LINK_STATIC_LAG:
    return "Static LAG"
  elif link_conf == DEV_MODE_LINK_DYNAMIC_LAG:
    return "Dynamic LAG"
  else:
    return "Unknown"

# GVCP device mode: Character set
DEV_MODE_CHARSET_RESERVED = 0
DEV_MODE_CHARSET_UTF8 = 1
DEV_MODE_CHARSET_ASCII = 2
def format_dev_mode_charset(charset: int) -> str:
  """Return human readable representation of the character set code."""
  if charset == DEV_MODE_CHARSET_RESERVED:
    return "Reserved"
  elif charset == DEV_MODE_CHARSET_UTF8:
    return "UTF-8"
  elif charset == DEV_MODE_CHARSET_ASCII:
    return "ASCII"
  else:
    return "Unknown"

class GVCPRequestId:
  """Class to get an unique request ID for GVCP commands."""
  def __init__(self) -> None:
    self.__req_id = 1

  def get(self) -> int:
    req_id = self.__req_id
    self.__req_id += 1
    if self.__req_id > 65535:
      self.__req_id = 1
    return req_id

class GVCPCmd:
  """Create GVCP command header. Base class for all GVCP commands."""

  def __init__(self, req_id: int, cmd: int, cmd_flag: int, payload: bytes = bytes(), ack: bool = True) -> None:
    assert cmd >= 0 and cmd <= 0xffff
    assert cmd_flag >= 0 and cmd_flag <= 15
    assert len(payload) <= GVCP_MAX_PAYLOAD_SIZE # GVCP does not allow packet fragmentation
    assert len(payload) % 4 == 0
    self.__req_id = req_id
    self.__cmd = cmd
    self.__cmd_flag = cmd_flag
    self.__payload = payload
    self.__ack = ack

    flag = (self.cmd_flag << 4) + (0x01 & self.ack)
    cmd_msb = 0xff & self.cmd >> 8
    cmd_lsb = 0xff & self.cmd
    payload_len = len(self.payload)
    payload_len_msb = 0xff & payload_len >> 8
    payload_len_lsb = 0xff & payload_len
    req_id_msb = 0xff & self.req_id >> 8
    req_id_lsb = 0xff & self.req_id
    header = [GVCP_KEY, flag, cmd_msb, cmd_lsb, payload_len_msb, payload_len_lsb, req_id_msb, req_id_lsb]
    padding = [0x00] * (payload_len % 4)
    self.__data = bytes(header) + bytes(self.payload) + bytes(padding)

  def __str__(self, width = 13) -> str:
    text = f"{self.__class__.__name__}:\n"
    padding = " "*(width - 12)
    text += f"  Acknowledge:{padding}{self.ack}\n"
    padding = " "*(width - 5)
    text += f"  Flag:{padding}0x{self.cmd_flag:x}\n"
    padding = " "*(width - 8)
    text += f"  Command:{padding}{self.cmd_name}\n"
    padding = " "*(width - 7)
    text += f"  Length:{padding}{len(self.payload)}\n"
    padding = " "*(width - 3)
    text += f"  ID:{padding}{self.req_id}"
    return text

  @property
  def req_id(self) -> int:
    return self.__req_id

  @property
  def cmd(self) -> int:
    return self.__cmd

  @property
  def cmd_name(self) -> str:
    return format_cmd_ack_name(self.__cmd)

  @property
  def cmd_flag(self) -> int:
    return self.__cmd_flag

  @property
  def payload(self) -> bytes:
    return self.__payload

  @property
  def ack(self) -> bool:
    return self.__ack

  @property
  def data(self) -> bytes:
    return self.__data

class GVCPDiscoveryCmd(GVCPCmd):
  """Create GVCP discovery command."""

  def __init__(self, req_id: int, ack_bcast: bool = False) -> None:
    flag = 0x1 & ack_bcast
    super().__init__(req_id, DISCOVERY_CMD, flag, ack=True)

class GVCPForceIPCmd(GVCPCmd):
  """Create GVCP force IP command."""

  def __init__(self, req_id: int, mac: str, ip: str, mask: str, def_gateway: str, ack_bcast: bool = False, ack: bool = True) -> None:
    cmd_flag = 0x1 & ack_bcast
    payload = bytes(2) + mac_to_bytes(mac) + bytes(12) + ip_to_bytes(ip) + bytes(12) + ip_to_bytes(mask) + bytes(12) + ip_to_bytes(def_gateway)
    super().__init__(req_id, FORCEIP_CMD, cmd_flag, payload, ack)
    self.__mac = mac
    self.__netmask = mask
    self.__ip = ip
    self.__default_gateway = def_gateway

  def __str__(self) -> str:
    text = super().__str__(17)
    text += f"\n  MAC-address:     {self.mac}"
    text += f"\n  IP-address:      {self.ip}"
    text += f"\n  Netmask:         {self.netmask}"
    text += f"\n  Default gateway: {self.default_gateway}"
    return text

  @property
  def mac(self) -> str:
    return self.__mac

  @property
  def ip(self) -> str:
    return self.__ip

  @property
  def netmask(self) -> str:
    return self.__netmask

  @property
  def default_gateway(self) -> str:
    return self.__default_gateway

class GVCPReadRegCmd(GVCPCmd):
  """Create GVCP read register command."""

  def __init__(self, req_id: int, addrs: list[int]) -> None:
    if len(addrs) < 1:
      raise ValueError("GVCP ERROR: At least one address is needed")
    if len(addrs) > 135:
      raise ValueError("GVCP ERROR: Cannot read over 135 addresses at once")
    payload = bytes([])
    for i in range(len(addrs)):
      if not is_uint32_4_multiple(addrs[i]):
        raise ValueError("GVCP ERROR: Address must be multiple of 4")
      payload = payload + uint32_to_bytes(addrs[i])
    super().__init__(req_id, READREG_CMD, 0, payload, True)
    self.__addrs = addrs

  def __str__(self) -> str:
    addrs = list(map(lambda v: f"0x{v:08x}", self.addrs))
    text = super().__str__()
    if len(addrs) == 1:
      text += f"\n  Address:     {addrs[0]}"
    else:
      text += f"\n  Addresses:   [{', '.join(addrs)}]"
    return text

  @property
  def addrs(self) -> list[int]:
    return self.__addrs.copy()

class GVCPWriteRegCmd(GVCPCmd):
  """Create GVCP write register command."""

  def __init__(self, req_id: int, addrs: list[int], values: Union[bytes, list[Union[int, float]]], ack: bool = True) -> None:
    if len(addrs) < 1:
      raise ValueError("GVCP ERROR: At least one address is needed")
    if len(addrs) > 67:
      raise ValueError("GVCP ERROR: Cannot write over 67 addresses at once")
    if type(values) == bytes:
      dt = np.dtype(np.uint32).newbyteorder(">")
      values = list(np.frombuffer(values, dt))
    if len(addrs) != len(values):
      raise ValueError("GVCP ERROR: Address and value counts do not match")
    self.__values = values
    payload = bytes([])
    raw_values = self.raw_values
    for i in range(len(addrs)):
      if not is_uint32_4_multiple(addrs[i]):
        raise ValueError("GVCP ERROR: Address must be multiple of 4")
      addr = uint32_to_bytes(addrs[i])
      value = uint32_to_bytes(raw_values[i])
      payload = payload + addr + value
    super().__init__(req_id, WRITEREG_CMD, 0, payload, ack)
    self.__addrs = addrs

  def __str__(self) -> str:
    text = super().__str__(15)
    addrs = self.addrs
    values = self.values
    raw_values = self.raw_values
    displayed = list(map(lambda i: f"0x{addrs[i]:08x}: {values[i]: 6} (0x{raw_values[i]:08x})", range(len(addrs))))
    if len(addrs) == 1:
      text += f"\n  Address/Value: {displayed[0]}"
    else:
      displayed = "\n    ".join(displayed)
      text += f"\n  Addresses/Values:\n    {displayed}"
    return text

  @property
  def addrs(self) -> list[int]:
    return self.__addrs.copy()

  @property
  def values(self) -> list[Union[int, float]]:
    return self.__values.copy()

  @property
  def raw_values(self) -> list[int]:
    return list(map(lambda v: float32_to_raw_uint(v) if type(v) == float else v, self.__values))

class GVCPReadMemCmd(GVCPCmd):
  """Create GVCP read memory command."""

  def __init__(self, req_id: int, addr: int, count: int) -> None:
    if not is_uint32_4_multiple(addr):
      raise ValueError("GVCP ERROR: Address must be multiple of 4")
    if count < 1:
      raise ValueError("GVCP ERROR: Register count must be greater than 0")
    if not is_uint32_4_multiple(count):
      raise ValueError("GVCP ERROR: Register count must be multiple of 4")
    if count > READMEM_MAX_PAYLOAD_SIZE:
      raise ValueError(f"GVCP ERROR: Register count must not be over {READMEM_MAX_PAYLOAD_SIZE}")
    addr_bytes = uint32_to_bytes(addr)
    count_bytes = uint16_to_bytes(count)
    payload = addr_bytes + bytes([0x00, 0x00]) + count_bytes
    super().__init__(req_id, READMEM_CMD, 0, payload, True)
    self.__addr = addr
    self.__count = count

  def __str__(self) -> str:
    text = super().__str__()
    text += f"\n  Address:     0x{self.addr:08x}"
    text += f"\n  Count:       {self.count}"
    return text

  @property
  def addr(self) -> int:
    return self.__addr

  @property
  def count(self) -> int:
    return self.__count

class GVCPWriteMemCmd(GVCPCmd):
  """Create GVCP write memory command."""

  def __init__(self, req_id: int, addr: int, value: Union[str, bytes], ack: bool = True) -> None:
    if not is_uint32_4_multiple(addr):
      raise ValueError("GVCP ERROR: Address must be multiple of 4")
    value_len = len(value)
    if value_len < 1:
      raise ValueError("GVCP ERROR: Length of the value must be greater than 0")
    if value_len > READMEM_MAX_PAYLOAD_SIZE:
      raise ValueError(f"GVCP ERROR: Length of the value must not be over {READMEM_MAX_PAYLOAD_SIZE}")
    self.__addr = addr
    self.__value = value
    self.__padding_len = 0 if value_len % 4 == 0 else 4 - value_len % 4
    addr_bytes = uint32_to_bytes(addr)
    padding = bytes([0]*self.padding_len)
    payload = addr_bytes + self.raw_value + padding
    super().__init__(req_id, WRITEMEM_CMD, 0, payload, ack)

  def __str__(self) -> str:
    values = format_bytearray(self.raw_value, 4)
    text = super().__str__()
    text += f"\n  Address:     0x{self.addr:08x}"
    text += f"\n  Value:{values}"
    return text

  @property
  def addr(self) -> int:
    return self.__addr

  @property
  def value(self) -> Union[str, bytes]:
    return self.__value

  @property
  def raw_value(self) -> bytes:
    return bytes(self.value, "utf-8") if type(self.value) == str else self.value

  @property
  def padding_len(self) -> int:
    return self.__padding_len

class GVCPActionCmd(GVCPCmd):
  """Create GVCP action command."""

  def __init__(self, req_id: int, device_key: int, group_key: int, group_mask: int, ack: bool = True, act_time: int = None) -> None:
    # Send command
    payload = uint32_to_bytes(device_key) + uint32_to_bytes(group_key) + uint32_to_bytes(group_mask)
    cmd_flag = 0x0
    if act_time != None:
      payload = payload + uint64_to_bytes(act_time)
      cmd_flag = 0x8
    super().__init__(req_id, ACTION_CMD, cmd_flag, payload, ack)
    self.__device_key = device_key
    self.__group_key = group_key
    self.__group_mask = group_mask
    self.__act_time = act_time

  def __str__(self) -> str:
    text = super().__str__()
    text += f"\n  Device key:  {self.device_key}"
    text += f"\n  Group key:   {self.group_key}"
    text += f"\n  Group mask:  {self.group_mask}"
    if self.action_time != None:
      text += f"\n  Action time: {self.action_time}"
    return text

  @property
  def device_key(self) -> int:
    return self.__device_key

  @property
  def group_key(self) -> int:
    return self.__group_key

  @property
  def group_mask(self) -> int:
    return self.__group_mask

  @property
  def action_time(self) -> int:
    return self.__act_time

class GVCPAck:
  """Parse GVCP acknowledge header. Base class for all GVCP acknowledgements."""

  def __init__(self, data: Union[bytes, Any]) -> None:
    if type(data) == bytes:
      self.__from_bytes(data)
    else:
      self.__from_ack(data)

  def __str__(self, width = 8) -> str:
    text = f"{self.__class__.__name__}:\n"
    severity = "ERROR: " if self.severity else ""
    specific = " (device specific code)" if self.__device_specific else ""
    padding = " "*(width - 7)
    text += f"  Status:{padding}{severity}{self.status_name}{specific}\n"
    padding = " "*(width - 5)
    text += f"  Type:{padding}{self.ack_name}\n"
    padding = " "*(width - 7)
    text += f"  Length:{padding}{self.length}\n"
    padding = " "*(width - 3)
    text += f"  ID:{padding}{self.ack_id}"
    return text

  def __from_bytes(self, data: bytes) -> None:
    if len(data) < GVCP_HEADER_SIZE:
      raise AckLengthError("GVCP ERROR: Received packet was too short for GVCP acknowledgement", GVCP_HEADER_SIZE, len(data))

    self.__severity = bool(data[0] & 0x80)
    self.__device_specific = bool(data[0] & 0x40)
    self.__status = bytes_to_uint12(data[0:2])
    self.__ack = bytes_to_uint16(data[2:4])
    self.__length = bytes_to_uint16(data[4:6])
    self.__ack_id = bytes_to_uint16(data[6:8])

    if len(data) - GVCP_HEADER_SIZE != self.__length:
      raise AckLengthError("GVCP ERROR: Actual size of the payload does not match reported size", self.__length, len(data) - GVCP_HEADER_SIZE)

    self.__payload = data[8:][:self.length]

    # Show status message
    if self.__severity:
      specific = " (device specific code)" if self.__device_specific else ""
      raise AckError(f"GVCP ERROR: Received {self.ack_name} ERROR: {self.status_name}{specific}", self)

  def __from_ack(self, data) -> None:
    self.__severity = data.__severity
    self.__device_specific = data.__device_specific
    self.__status = data.__status
    self.__ack = data.__ack
    self.__length = data.__length
    self.__ack_id = data.__ack_id
    self.__payload = data.__payload

  @property
  def severity(self) -> bool:
    """True = error, False = info"""
    return self.__severity

  @property
  def device_specific(self) -> bool:
    """True = device specific, False = standard GigE"""
    return self.__device_specific

  @property
  def status(self) -> bool:
    return self.__status

  @property
  def status_name(self) -> str:
    """Get name of GigE Vision status (in GVCP ack or GVSP header)"""
    if self.__device_specific:
      return f"0x{self.__status:04x}"

    if self.__status == GEV_STATUS_SUCCESS:
      return "SUCCESS"
    elif self.__status == GEV_STATUS_PACKET_RESEND:
      return "PACKET_RESEND"
    elif self.__status == GEV_STATUS_NOT_IMPLEMENTED:
      return "NOT_IMPLEMENTED"
    elif self.__status == GEV_STATUS_INVALID_PARAMETER:
      return "INVALID_PARAMETER"
    elif self.__status == GEV_STATUS_INVALID_ADDRESS:
      return "INVALID_ADDRESS"
    elif self.__status == GEV_STATUS_WRITE_PROTECT:
      return "WRITE_PROTECT"
    elif self.__status == GEV_STATUS_BAD_ALIGNMENT:
      return "BAD_ALIGNMENT"
    elif self.__status == GEV_STATUS_ACCESS_DENIED:
      return "ACCESS_DENIED"
    elif self.__status == GEV_STATUS_BUSY:
      return "BUSY"
    elif self.__status == GEV_STATUS_PACKET_UNAVAILABLE:
      return "PACKET_UNAVAILABLE"
    elif self.__status == GEV_STATUS_DATA_OVERRUN:
      return "DATA_OVERRUN"
    elif self.__status == GEV_STATUS_INVALID_HEADER:
      return "INVALID_HEADER"
    elif self.__status == GEV_STATUS_PACKET_NOT_YET_AVAILABLE:
      return "PACKET_NOT_YET_AVAILABLE"
    elif self.__status == GEV_STATUS_PACKET_AND_PREV_REMOVED_FROM_MEMORY:
      return "PACKET_AND_PREV_REMOVED_FROM_MEMORY"
    elif self.__status == GEV_STATUS_PACKET_REMOVED_FROM_MEMORY:
      return "PACKET_REMOVED_FROM_MEMORY"
    elif self.__status == GEV_STATUS_NO_REF_TIME:
      return "NO_REF_TIME"
    elif self.__status == GEV_STATUS_PACKET_TEMPORARILY_UNAVAILABLE:
      return "PACKET_TEMPORARILY_UNAVAILABLE"
    elif self.__status == GEV_STATUS_OVERFLOW:
      return "OVERFLOW"
    elif self.__status == GEV_STATUS_ACTION_LATE:
      return "ACTION_LATE"
    elif self.__status == GEV_STATUS_ERROR:
      return "ERROR"
    else:
      return f"0x{self.__status:04x}"

  @property
  def ack(self) -> int:
    return self.__ack

  @property
  def ack_name(self) -> str:
    return format_cmd_ack_name(self.__ack)

  @property
  def length(self) -> int:
    return self.__length

  @property
  def ack_id(self) -> int:
    return self.__ack_id

  @property
  def payload(self) -> bytes:
    return self.__payload

class GVCPDiscoveryAck(GVCPAck):
  """Parse GVCP discovery acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != DISCOVERY_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not a discovery ack", DISCOVERY_ACK, self.ack)
    if self.length != 248:
      raise AckLengthError("GVCP ERROR: Length of the received packet is too short", 248, self.length)
    payload = self.payload
    self.spec_version_major = bytes_to_uint16(payload[0:2])
    self.spec_version_minor = bytes_to_uint16(payload[2:4])
    device_mode = bytes_to_uint32(payload[4:8])
    self.endianess = (device_mode & 0x80000000) >> 31
    self.device_class = (device_mode & 0x70000000) >> 28
    self.link_config = (device_mode & 0x0F000000) >> 24
    self.charset = device_mode & 0xFF
    self.mac_address = f"{payload[10]:x}:{payload[11]:x}:{payload[12]:x}:{payload[13]:x}:{payload[14]:x}:{payload[15]:x}"
    self.ip_config_options = bytes_to_uint32(payload[16:20])
    self.ip_config_current = bytes_to_uint32(payload[20:24])
    self.current_ip = bytes_to_ip(payload[36:40])
    self.current_subnet_mask = bytes_to_ip(payload[52:56])
    self.default_gateway = bytes_to_ip(payload[68:72])
    self.manufacturer_name = bytes_to_str(payload[72:104])
    self.model_name = bytes_to_str(payload[104:136])
    self.device_version = bytes_to_str(payload[136:168])
    self.manufacturer_specific_info = bytes_to_str(payload[136:168])
    self.serial_number = bytes_to_str(payload[216:232])
    self.user_defined_name = bytes_to_str(payload[232:])

  def __str__(self) -> str:
    text = super().__str__(28)
    text += f"  Specification version:      {self.spec_version_major}.{self.spec_version_minor}\n"
    text += f"  Endianess:                  {format_dev_mode_endianess(self.endianess)}\n"
    text += f"  Device class:               {format_dev_mode_class(self.device_class)}\n"
    text += f"  Link configuration:         {format_dev_mode_link(self.link_config)}\n"
    text += f"  Character set:              {format_dev_mode_charset(self.charset)}\n"
    text += f"  MAC address:                {self.mac_address}\n"
    text += f"  IP config options:          0x{self.ip_config_options:x}\n"
    text += f"  Current IP config:          0x{self.ip_config_current:x}\n"
    text += f"  Current IP:                 {self.current_ip}\n"
    text += f"  Subnet mask:                {self.current_subnet_mask}\n"
    text += f"  Default gateway:            {self.default_gateway}\n"
    text += f"  Manufacturer name:          {self.manufacturer_name}\n"
    text += f"  Model name:                 {self.model_name}\n"
    text += f"  Device version:             {self.device_version}\n"
    text += f"  Manufacturer specific info: {self.manufacturer_specific_info}\n"
    text += f"  Serial number:              {self.serial_number}\n"
    text += f"  User defined name:          {self.user_defined_name}"
    return text

class GVCPReadRegAck(GVCPAck):
  """Parse GVCP read register acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != READREG_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not a read register ack", READREG_ACK, self.ack)
    if self.length < 4:
      raise AckLengthError("GVCP ERROR: Length of the received packet is too short", 4, self.length)

  def __str__(self) -> str:
    values = list(map(lambda v: f"0x{v:08x}", self.get_values(int)))
    text = super().__str__()
    if len(values) == 1:
      text += f"\n  Value:  {values[0]}"
    else:
      text += f"\n  Values: [{', '.join(values)}]"
    return text

  def get_values(self, return_type: type = bytes) -> Union[bytes, list[Union[int, float]]]:
    if return_type == bytes:
      return self.payload
    elif return_type == int:
      return bytes_to_uint32_list(self.payload)
    elif return_type == float:
      return bytes_to_float32_list(self.payload)
    else:
      raise TypeError("GVCP ERROR: Invalid return_type, allowed types: bytes, int, float", return_type)

class GVCPWriteRegAck(GVCPAck):
  """Parse GVCP write register acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != WRITEREG_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not a write register ack", WRITEREG_ACK, self.ack)
    if self.length < 4:
      raise AckLengthError("GVCP ERROR: Length of the received packet is too short", 4, self.length)
    self.__index = bytes_to_uint16(self.payload[2:4])

  def __str__(self) -> str:
    text = super().__str__()
    text += f"\n  Index:  {self.index}"
    return text

  @property
  def index(self) -> int:
    return self.__index

class GVCPReadMemAck(GVCPAck):
  """Parse GVCP read memory acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != READMEM_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not a read memory ack", READMEM_ACK, self.ack)
    if self.length < 8:
      raise AckLengthError("GVCP ERROR: Length of the received packet is too short", 8, self.length)
    self.__addr = bytes_to_uint32(self.payload[:4])

  def __str__(self) -> str:
    values = format_bytearray(self.get_values(bytes), 4)
    text = super().__str__(9)
    text += f"\n  Address: {self.addr}"
    text += f"\n  Value:   {values}"
    return text

  @property
  def addr(self) -> int:
    return self.__addr

  def get_values(self, return_type: type = bytes) -> Union[bytes, str]:
    if return_type == bytes:
      return self.payload[4:]
    elif return_type == str:
      return bytes_to_str(self.payload[4:])
    else:
      raise TypeError("GVCP ERROR: Invalid return_type, allowed types: bytes, str", return_type)

class GVCPWriteMemAck(GVCPAck):
  """Parse GVCP write memory acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != WRITEMEM_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not a write memory ack", WRITEMEM_ACK, self.ack)
    if self.length < 4:
      raise AckLengthError("GVCP ERROR: Length of the received packet is too short", 4, self.length)
    self.__index = bytes_to_uint16(self.payload[2:4])

  def __str__(self) -> str:
    text = super().__str__()
    text += f"\n  Index:  {self.index}"
    return text

  @property
  def index(self) -> int:
    return self.__index

class GVCPActionAck(GVCPAck):
  """Parse GVCP action acknowledgement."""

  def __init__(self, data: Union[bytes, GVCPAck]) -> None:
    super().__init__(data)
    if self.ack != ACTION_ACK:
      raise AckValueError("GVCP ERROR: Received packet is not an action ack", ACTION_ACK, self.ack)
    if self.length != 0:
      raise AckLengthError("GVCP ERROR: Length of the received packet is wrong", 0, self.length)

class DeviceDescriptionUrl:
  """Parse GigE Vision device description URL."""

  def __init__(self, url_str: str) -> None:
    schema_list = url_str.rsplit("?SchemaVersion=", 1)
    url_part_wirh_loc = schema_list[0]
    self.schema_version = schema_list[1] if len(schema_list) > 1 else None
    location, url_part = url_part_wirh_loc.split(":", 1)
    self.location = location.lower()
    if self.location == "local":
      url_part, address, length = url_part.split(";")
      self.address = int(address, 16)
      self.length = int(length, 16)
      if url_part.startswith("///"):
        url_part = url_part[3:]
      self.file_name = url_part
      url_part, extension = self.file_name.rsplit(".", 1)
      self.extension = extension.lower()
      self.url = None
    elif self.location == "file" or self.location == "http":
      if self.location == "file":
        self.url = url_part[2:] if url_part.startswith("///") else url_part
      else:
        self.url = url_part_wirh_loc
      url_part, self.file_name = url_part.rsplit("/", 1)
      url_part, extension = self.file_name.rsplit(".", 1)
      self.extension = extension.lower()
      self.address = None
      self.length = None
    else:
      raise AckValueError(f"GVCP ERROR: Unsupported URL type: {self.location}", None, self.location)

class GVCP:
  """Main class to handle GigE Vision control channel related operations."""

  def __init__(self):
    # Socket / packets
    self._soc = None
    self._soc_lock = threading.Lock()
    self._soc_timeout = 0.5 # in seconds
    self._req_id = GVCPRequestId()
    self._pending = False
    self.retries = 3
    """Number of times to retry a command before raising an error."""

    # Heartbeat
    self._heartbeat_timeout = 5.0 # in seconds
    self._heartbeat_rate = self._heartbeat_timeout / 3 # in seconds
    self._heartbeat_thread = None
    self._heartbeat_disable = threading.Event()

    # Support for optional features
    self.concat_support = None
    self.writemem_support = None
    self.action_support = None
    self.scheduled_action_support = None

    # Output formatting
    self.verbose = False
    self.debug = False

  @property
  def connected(self):
    """Connection is open."""
    return self._soc != None

  @property
  def pending(self) -> bool:
    """Received PENDING_ACK and waiting for the actual response."""
    return self._pending

  @property
  def ack_timeout(self) -> float:
    """Time to wait for an acknowledgement in seconds."""
    return self._soc_timeout

  @ack_timeout.setter
  def ack_timeout(self, timeout: float) -> None:
    self._soc_timeout = timeout
    self._soc.settimeout(timeout)

  @property
  def heartbeat_timeout(self) -> float:
    """GVCP heartbeat timeout in seconds."""
    return self._heartbeat_timeout

  @heartbeat_timeout.setter
  def heartbeat_timeout(self, timeout: float) -> None:
    self._heartbeat_timeout = timeout
    self._heartbeat_rate = timeout / 3
    if self.connected:
      self.writereg(REG_HEARTBEAT_TIMEOUT, round(timeout * 1000))

  def connect(self, addr: str, port: int = GVCP_PORT) -> None:
    """
    Connect to a camera with an IP address.

    :param addr: IP address of the camera
    :param port: UDP port of the camera (for GVCP), default is 3956
    :returns: None
    :raises NotConnectedError: Cannot connect
    :raises IsConnectedError: Already connected
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    self._soc_lock.acquire()
    if self.connected:
      self._soc_lock.release()
      raise IsConnectedError("GVCP ERROR: GVCP is already connected")
    try:
      self._soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      # TODO Fetch GVCP pending timeout from device register 0x0958 if it is implemented
      self._soc.settimeout(self._soc_timeout)
      self._soc.connect((addr, port))
    finally:
      self._soc_lock.release()
    self.writereg(REG_CCP, VAL_CONTROL_ACCESS)
    self.writereg(REG_HEARTBEAT_TIMEOUT, round(self._heartbeat_timeout * 1000))
    ccp_status = self.readreg(REG_CCP, int)
    if ccp_status == VAL_CONTROL_ACCESS:
      self._heartbeat_thread = threading.Thread(target=self._heartbeat)
      self._heartbeat_thread.start()
      if self.verbose:
        print("GVCP: Connected")
    else:
      self._soc_lock.acquire()
      self._soc.close()
      self._soc = None
      self._soc_lock.release()
      raise NotConnectedError(f"GVCP ERROR: Could not connect\nCCP register value: 0x{ccp_status:x}")

  def disconnect(self) -> None:
    """
    Disconnect from the camera.

    :returns: None
    :raises NotConnectedError: Already disconnected
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")
    self._heartbeat_disable.set()
    self.writereg(REG_CCP, 0)
    self._heartbeat_thread.join()
    self._heartbeat_disable.clear()
    self._soc_lock.acquire()
    self._soc.close()
    self._soc = None
    self._soc_lock.release()
    if self.verbose:
      print("GVCP: Disconnected")

  def discovery(self, return_type: type = bytes) -> Union[bytes, GVCPDiscoveryAck]:
    """
    Send discovery command to the camera.

    :param return_type: Type of the returned value
    :returns: Discovery acknowledgement as a GVCPDiscoveryAck object or raw bytes
    :raises NotConnectedError: No connection
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Send a packet and process response
    request = GVCPDiscoveryCmd(self._req_id.get())
    if self.verbose: print(request)
    response = GVCPDiscoveryAck(self._request(request))
    if self.verbose: print(response)

    # Handle return type
    if return_type == bytes:
      return response.payload
    elif return_type == GVCPDiscoveryAck:
      return response
    else:
      raise TypeError("GVCP ERROR: Invalid return_type, allowed types: bytes, GVCPDiscoveryAck", return_type)

  def readreg(self, addrs: Union[int, Iterable[int]], return_type: type = bytes) -> Union[bytes, int, float, list[Union[int, float]]]:
    """
    Read single or multiple registers from the camera.

    :param addrs: Register address or addresses
    :param return_type: Type of the returned value
    :returns: Value or values from camera registers
    :raises NotConnectedError: No connection
    :raises ValueError: Invalid value of address
    :raises TypeError: Invalid return_type
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Handle single register case
    if type(addrs) == int:
      addrs = [addrs]

    # Check support for register concatenation
    if len(addrs) > 1:
      if self.concat_support == None:
        self._check_capability()
      if not self.concat_support:
        raise NotImplementedError("GVCP ERROR: Device does not support register concatenation")

    # Send a packet and process response
    request = GVCPReadRegCmd(self._req_id.get(), addrs)
    if self.verbose: print(request)
    response = GVCPReadRegAck(self._request(request))
    if self.verbose: print(response)
    values = response.get_values(return_type)

    # Handle return type
    return values if type(values) == bytes or len(values) > 1 else values[0]

  def writereg(self, addrs: Union[int, list[int]], values: Union[bytes, int, float, list[Union[int, float]]], ack: bool = True) -> None:
    """
    Write single or multiple registers on the camera.

    :param addrs: Register address or addresses
    :param values: Register value or values corresponding to addresses
    :param ack: Ask camera to acknowledge
    :returns: None
    :raises NotConnectedError: No connection
    :raises ValueError: Invalid value of address
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Handle single register case
    if type(addrs) == int:
      addrs = [addrs]
    if type(values) == int or type(values) == float:
      values = [values]

    # Check support for register concatenation
    if len(addrs) > 1:
      if self.concat_support == None:
        self._check_capability()
      if not self.concat_support:
        raise NotImplementedError("GVCP ERROR: Device does not support register concatenation")

    # Send a packet
    request = GVCPWriteRegCmd(self._req_id.get(), addrs, values, ack)
    if self.verbose: print(request)
    response = self._request(request)

    # Handle response
    if ack:
      response = GVCPWriteRegAck(response)
      if self.verbose:
        print(response)

  def readmem(self, addr: int, count: int, return_type: type = bytes) -> Union[bytes, str]:
    """
    Read multiple registers as a string from the camera.

    :param addr: First register address
    :param count: Amount of registers to read
    :param return_type: Format of the returned value
    :returns: Values of the registers
    :raises NotConnectedError: No connection
    :raises ValueError: Invalid value of address
    :raises TypeError: Invalid return_type
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Send a packet and process response
    request = GVCPReadMemCmd(self._req_id.get(), addr, count)
    if self.verbose: print(request)
    response = GVCPReadMemAck(self._request(request))
    if response.addr != addr:
      raise AckValueError("GVCP ERROR: Acknowledged address was different to requested address", addr, response.addr)
    if self.verbose: print(response)

    return response.get_values(return_type)

  def writemem(self, addr: int, value: Union[str, bytes], ack: bool = True) -> None:
    """
    Write multiple registers with a string to the camera.

    :param addr: First register address
    :param value: String or bytes to write to camera memory
    :param ack: Ask camera to acknowledge request
    :returns: None
    :raises NotConnectedError: No connection
    :raises NotImplementedError: Device does not support WRITEMEM command
    :raises ValueError: Invalid address or value
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Check support for WRITEMEM command
    if self.writemem_support == None:
      self._check_capability()
    if not self.writemem_support:
      raise NotImplementedError("GVCP ERROR: Device does not support WRITEMEM command")

    # Send a packet
    request = GVCPWriteMemCmd(self._req_id.get(), addr, value, ack)
    if self.verbose: print(request)
    response = self._request(request)

    # Handle response
    if ack:
      response = GVCPWriteMemAck(response)
      if self.verbose:
        print(response)

  def action(self, device_key: int, group_key: int, group_mask: int, ack: bool = True, act_time: int = None) -> None:
    """
    Send action command to the camera. Note that this method cannot be used for broadcasting.

    :param device_key: Device key (see GigE Vision specs)
    :param group_key: Group key (see GigE Vision specs)
    :param group_mask: Group mask (see GigE Vision specs)
    :returns: None
    :raises NotConnectedError: No connection
    :raises NotImplementedError: Device does not support ACTION or scheduled ACTION command
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time (note that ACTION does not need to return ack)
    """
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Check support for ACTION command
    if self.action_support == None:
      self._check_capability()
    if not self.action_support:
      raise NotImplementedError("GVCP ERROR: Device does not support ACTION command")

    # Check support for scheduled ACTION command
    if act_time != None:
      if self.scheduled_action_support == None:
        self._check_capability()
      if not self.scheduled_action_support:
        raise NotImplementedError("GVCP ERROR: Device does not support scheduled ACTION command")

    # Send a packet
    request = GVCPActionCmd(self._req_id.get(), device_key, group_key, group_mask, ack, act_time)
    if self.verbose: print(request)
    response = self._request(request)

    # Handle response
    if ack:
      response = GVCPActionAck(response)
      if self.verbose:
        print(response)

  def get_device_description_url(self, return_type: Union[str, DeviceDescriptionUrl] = str) -> Union[str, DeviceDescriptionUrl]:
    """
    Get the device description file URL from the camera.

    :param return_type: Type of the returned value
    :returns: URL string in format specified in GigE Visions specs or parsed object
    :raises NotConnectedError: No connection
    :raises AckError: Problem with an acknowledgement from the camera
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    # TODO Support for manifest table
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")
    url = self.readmem(REG_FIRST_URL, REG_FIRST_URL_LEN, str)
    if self.verbose:
      print("GVCP: Read device description URL")
    return url if return_type == str else DeviceDescriptionUrl(url)

  def get_device_description_file(self, path: str = None) -> str:
    """
    Get the device description file automatically. Optionally you specify where to save the file.

    :param path: Path where to save the file on hard drive, optional
    :returns: Device description file XML
    :raises NotConnectedError: No connection
    :raises AckError: Problem with an acknowledgement from the camera
    :raises NotImplementedError: Device escription files stored in internet are not supported
    :raises socket.timeout: Camera didn't send an acknowledgement in time
    """
    # TODO Support for manifest table
    if not self.connected:
      raise NotConnectedError("GVCP ERROR: Not connected, call gvcp.connect() first")

    # Fetch address for device description file
    url = self.get_device_description_url(DeviceDescriptionUrl)

    # Device description file is saved on the local machine
    if url.location == "file":
      if url.extension == "xml":
        file = open(url.url)
        xml_str = file.read()
      elif url.extension == "zip":
        file = zipfile.ZipFile(url.url)
        xml_str = file.read(file.namelist()[0]).decode("utf-8")
      else:
        raise AckValueError(f"GVCP ERROR: Unsupported device description file format: {url.extension}", None, url.extension)

    # Device description file is saved on the camera memory
    elif url.location == "local":
      addr = url.address
      len_total = url.length
      len_left = len_total
      packet_size = 512

      # Fetch device decription file in 512 byte chunks
      ddf = bytes()
      while len_left >= packet_size:
        ddf_part = self.readmem(addr, packet_size, bytes)
        ddf = ddf + ddf_part
        addr += packet_size
        len_left -= packet_size
      if len_left % 4:
        len_left = len_left + 4 - (len_left % 4)
      ddf_part = self.readmem(addr, len_left, bytes)
      ddf = ddf + ddf_part
      ddf = ddf[:len_total]

      # Unzip if needed and save to string
      if url.extension == "xml":
        xml_str = ddf
      if url.extension == "zip":
        z_file = zipfile.ZipFile(io.BytesIO(ddf))
        xml_str = z_file.read(z_file.namelist()[0]).decode("utf-8")
      else:
        raise AckValueError(f"GVCP ERROR: Unsupported device description file format: {url.extension}", None, url.extension)

    # Device description file is saved on the internet
    elif url.location == "http":
      raise NotImplementedError("GVCP ERROR: Web site location for device description file is not implemented")
    else:
      raise AckValueError(f"GVCP ERROR: Unsupported device description file location: {url.location}", None, url.location)

    # Save xml if path is given
    if (path != None):
      z_file.extractall(path)
      if self.verbose:
        print(f"GVCP: Device description file saved to: {path}")
    return xml_str

  def _request(self, request: GVCPCmd) -> GVCPAck:
    self._soc_lock.acquire()
    try:
      response = self._exec_request(request, 1)
    finally:
      self._soc_lock.release()
    return response

  def _exec_request(self, request: GVCPCmd, retry: int) -> GVCPAck:
    response = None
    req_len = self._soc.send(request.data)
    if self.debug:
      print(f"GVCP: Sent {request.cmd_name}, id: {request.req_id}, length: {req_len} bytes")
    if request.ack:
      try:
        response = self._handle_ack(self._soc.recv(ETH_MAX_MTU), request.req_id)
        while self._pending:
          response = self._handle_ack(self._soc.recv(ETH_MAX_MTU), request.req_id)
      except socket.timeout as err_timeout:
        if retry < self.retries:
          if self.verbose:
            print(f"GVCP: Attempt {retry} timed out")
          retry += 1
          response = self._exec_request(request, retry)
        else:
          raise err_timeout
    return response

  def _handle_ack(self, data: bytes, req_id: int) -> GVCPAck:
    response = GVCPAck(data)
    if req_id != None and response.ack_id != req_id:
      raise AckIdError("GVCP ERROR: Acknowledgement ID does not match last request ID", req_id, response.ack_id)
    if self.debug:
      specific_msg = "(device specific code)" if response.device_specific else ""
      print(f"GVCP: Received {response.ack_name} INFO: {response.status_name} {specific_msg}")

    # Handle PENDING acknowledge
    if response.ack == PENDING_ACK:
      assert response.length >= 4
      if not self._pending:
        timeout = bytes_to_uint16(data[10:12])
        self._soc.settimeout(timeout / 1000 + 0.01)
        self._pending = True
    elif self._pending:
      self._soc.settimeout(self._soc_timeout)
      self._pending = False

    # Return payload
    return response

  def _heartbeat(self):
    if self.verbose:
      print("GVCP: Starting to send heartbeat")
    while not self._heartbeat_disable.is_set():
      self._heartbeat_disable.wait(self._heartbeat_rate)
      if not self._heartbeat_disable.is_set():
        try:
          request = GVCPReadRegCmd(self._req_id.get(), [REG_CCP])
          response = GVCPReadRegAck(self._request(request))
          ccp_status = response.get_values(int)[0]
        except socket.timeout:
          ccp_status = 0
        if ccp_status != VAL_CONTROL_ACCESS:
          self._soc.close()
          self._soc = None
          raise NotConnectedError("GVCP ERROR: Connection lost")
        elif self.debug:
          print("GVCP: Sent heartbeat refresh packet")
    if self.verbose:
      print("GVCP: Stopping heartbeat")

  def _check_capability(self):
    capability = self.readreg(REG_GVCP_CAPABILITY, int)
    self.concat_support = bool(capability & 0x00000001)
    self.writemem_support = bool(capability & 0x00000002)
    self.action_support = bool(capability & 0x00000040)
    self.scheduled_action_support = bool(capability & 0x00020000)

class PortGVCP(AbstractPort):
  """GenICam port interface - to access GVCP module from device description NodeMap"""

  def __init__(self, gvcp: GVCP):
    super().__init__()
    if isinstance(gvcp, GVCP):
      self.gvcp = gvcp
    else:
      raise TypeError('Port must be initialized with a GVCP object.')

  def is_open(self) -> bool:
    """Is connection to the camera open (for configuration)"""
    return self.gvcp.connected

  def write(self, address: int, value: bytes) -> None:
    """Write value through GVCP module"""
    if len(value) <= 4:
      self.gvcp.writereg(address, bytes_to_uint32(value))
    else:
      self.gvcp.writemem(address, value)

  def read(self, address: int, length: int) -> bytes:
    """Read value through GVCP module"""
    if length <= 4:
      return self.gvcp.readreg(address, bytes)
    else:
      return self.gvcp.readmem(address, length, bytes)

  def get_access_mode(self) -> EAccessMode:
    """Get access mode of this port (read / write)"""
    return EAccessMode.RW if self.is_open() else EAccessMode.NA
