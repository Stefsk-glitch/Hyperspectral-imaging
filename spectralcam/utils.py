import struct

from genicam.genapi import IValue, IInteger, IFloat, IString, IEnumeration, ICommand, IBoolean, IRegister
from psutil._common import snicaddr

# Network related constants
IP4_MAX_MTU = 576
ETH_MAX_MTU = 1500
IP4_HEADER_SIZE = 20
UDP_HEADER_SIZE = 8

def is_uint32_4_multiple(value: int) -> bool:
  """Check that value is 32 bits long unsigned integer and is divisible by 4."""
  return value >= 0 and value <= 0xffffffff and value % 4 == 0

def uint16_to_bytes(value: int) -> bytes:
  """Convert 16 bits long unsigned integer to a byte buffer (big endian)."""
  assert value >= 0 and value <= 0xffff
  byte1 = (value >> 8) & 0xff
  byte2 = value & 0xff
  return bytes([byte1, byte2])

def uint32_to_bytes(value: int) -> bytes:
  """Convert 32 bits long unsigned integer to a byte buffer (big endian)."""
  assert value >= 0 and value <= 0xffffffff
  byte1 = (value >> 24) & 0xff
  byte2 = (value >> 16) & 0xff
  byte3 = (value >> 8) & 0xff
  byte4 = value & 0xff
  return bytes([byte1, byte2, byte3, byte4])

def uint64_to_bytes(value: int) -> bytes:
  """Convert 64 bits long unsigned integer to a byte buffer (big endian)."""
  assert value >= 0 and value <= 0xffffffffffffffff
  byte1 = (value >> 56) & 0xff
  byte2 = (value >> 48) & 0xff
  byte3 = (value >> 40) & 0xff
  byte4 = (value >> 32) & 0xff
  byte5 = (value >> 24) & 0xff
  byte6 = (value >> 16) & 0xff
  byte7 = (value >> 8) & 0xff
  byte8 = value & 0xff
  return bytes([byte1, byte2, byte3, byte4, byte5, byte6, byte7, byte8])

def bytes_to_uint12(byte_list: bytes) -> int:
  """Convert a byte buffer (big endian) to 12 bits long unsigned integer."""
  assert len(byte_list) >= 2
  return ((byte_list[0] << 8) + byte_list[1]) & 0x0fff

def bytes_to_uint16(byte_list: bytes) -> int:
  """Convert a byte buffer (big endian) to 16 bits long unsigned integer."""
  assert len(byte_list) >= 2
  return (byte_list[0] << 8) + byte_list[1]

def bytes_to_uint32(byte_list: bytes) -> int:
  """Convert a byte buffer (big endian) to 32 bits long unsigned integer."""
  assert len(byte_list) >= 4
  return (byte_list[0] << 24) + (byte_list[1] << 16) + (byte_list[2] << 8) + byte_list[3]

def bytes_to_uint32_list(byte_list: bytes) -> list[int]:
  """Convert a byte buffer (big endian) to list of 32 bits long unsigned integers."""
  byte_list_len = len(byte_list)
  assert byte_list_len % 4 == 0
  result = []
  for i4 in range(byte_list_len >> 2):
    i = i4 << 2
    result.append(bytes_to_uint32(byte_list[i:i+4]))
  return result

def bytes_to_float32(value: bytes) -> float:
  """Convert a byte buffer (big endian) to 32 bits long float."""
  assert len(value) == 4
  return struct.unpack("f", value[::-1])[0]

def float32_to_raw_uint(value: float) -> int:
  """Convert 32 bits long float to raw integer value (big endian)."""
  return bytes_to_uint32(struct.pack("f", value)[::-1])

def bytes_to_float32_list(byte_list: bytes) -> list[float]:
  """Convert list of 32 bits long floats to a byte buffer (big endian)."""
  byte_list_len = len(byte_list)
  assert byte_list_len % 4 == 0
  result = []
  for i4 in range(byte_list_len >> 2):
    i = i4 << 2
    result.append(bytes_to_float32(byte_list[i:i+4]))
  return result

def bytes_to_str(byte_list: bytes) -> str:
  """Convert a byte buffer to a string (UTF-8). Null character terminates the string."""
  try:
    index = byte_list.index(0x00)
    return byte_list[:index].decode()
  except ValueError:
    return byte_list.decode()

def bytes_to_ip(byte_list: bytes) -> str:
  """Convert a byte buffer to an IP address string."""
  assert len(byte_list) >= 4
  return "{0}.{1}.{2}.{3}".format(byte_list[0], byte_list[1], byte_list[2], byte_list[3])

def netmask_to_short(netmask: str) -> int:
  """
  Convert a long format netmask string to a short format integer.
  E.g. 255.255.255.0 -> 24
  """
  assert is_ipv4(netmask)
  mask = ip_to_uint32(netmask)
  result = 32
  bit = 1
  while not mask & bit and result > 0:
    result -= 1
    bit = bit << 1
  return result

def ip_to_uint32(addr: str) -> int:
  """Convert an IP address string to an integer."""
  assert is_ipv4(addr)
  a = addr.split(".")
  return (int(a[0]) << 24) + (int(a[1]) << 16) + (int(a[2]) << 8) + (int(a[3]))

def ip_to_bytes(addr: str) -> bytes:
  """Convert an IP address string to a byte buffer."""
  assert is_ipv4(addr)
  a = addr.split(".")
  byte1 = int(a[0], 10) & 0xFF
  byte2 = int(a[1], 10) & 0xFF
  byte3 = int(a[2], 10) & 0xFF
  byte4 = int(a[3], 10) & 0xFF
  return bytes([byte1, byte2, byte3, byte4])

def mac_to_bytes(addr: str) -> bytes:
  """Convert a MAC address string to an integer."""
  assert is_mac(addr)
  s = "-" if addr.find("-") > -1 else ":"
  a = addr.split(s)
  byte1 = int(a[0], 16) & 0xFF
  byte2 = int(a[1], 16) & 0xFF
  byte3 = int(a[2], 16) & 0xFF
  byte4 = int(a[3], 16) & 0xFF
  byte5 = int(a[4], 16) & 0xFF
  byte6 = int(a[5], 16) & 0xFF
  return bytes([byte1, byte2, byte3, byte4, byte5, byte6])

def is_feature(feature: IValue) -> bool:
  """Check that an object is a GenICam feature."""
  f_types = [IInteger, IFloat, IString, IEnumeration, ICommand, IBoolean, IRegister]
  for f_type in f_types:
    if type(feature) == f_type:
      return True
  return False

def format_bytearray(array: bytes, indent: int = 0) -> str:
  """Convert a byte buffer to a nice string representation that can be displayed on the command line."""
  result = ""
  hex_str = " "*indent
  char_str = " "*indent
  hex_lines = []
  char_lines = []
  for i, b in enumerate(array):
    hex_str += f"{b:02x} "
    if b >= 0x20 and b <= 0x7E:
      char_str += f" {chr(b)} "
    else:
      char_str += " . "
    if (i + 1) % 16 == 0 or i + 1 == len(array):
      hex_lines.append(hex_str)
      char_lines.append(char_str)
      hex_str = " "*indent
      char_str = " "*indent
    elif (i + 1) % 8 == 0:
      hex_str += " "
      char_str += " "
  for i in range(len(hex_lines)):
    result += "\n" + hex_lines[i]
    result += "\n" + char_lines[i]
  return result

def is_ipv4(addr: str) -> bool:
  """Check that string is correct IPv4 address."""
  try:
    addr = [int(a) for a in addr.split(".")]
  except ValueError:
    return False
  if len(addr) != 4:
    return False
  for a in addr:
    if a < 0 or a > 255:
      return False
  return True

def is_mac(addr: str) -> bool:
  """Check that string is correct MAC address."""
  s = "-" if addr.find("-") > -1 else ":"
  try:
    addr = [int(a, 16) for a in addr.split(s)]
  except ValueError:
    return False
  if len(addr) != 6:
    return False
  for a in addr:
    if a < 0 or a > 255:
      return False
  return True

def is_normal_ip(address: snicaddr) -> bool:
  """
  Check that IP address is not special, i.e. loopback or broadcast address.

  :param addr: IP address
  :param mask: Corresponding netmask
  :returns: True if address is not special, False otherwise
  """
  try:
    addr = [int(a) for a in address.address.split(".")]
    mask = [~int(m) & 0xff for m in address.netmask.split(".")]
  except ValueError:
    return False
  if addr[0] == 127: # Loopback addresses
    return False
  if addr == [255,255,255,255]: # Broadcast address
    return False
  test = [addr[i] & mask[i] for i in range(4)]
  if test == mask: # Broadcast address
    return False
  return True

