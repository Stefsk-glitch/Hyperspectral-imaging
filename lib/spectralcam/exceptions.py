class CamControllerException(Exception):
  """Base exception for all camera controller exceptions"""
  pass

class AckError(CamControllerException):
  """Problem with return data of the camera (violation of GVCP specification)"""
  def __init__(self, *args: object) -> None:
    super().__init__(*args)
    self.ack = args[1]

class AckLengthError(AckError):
  """Length of return data of the camera is wrong (violation of GVCP specification)"""
  def __init__(self, msg: str, expected_len: int, actual_len: int) -> None:
    super().__init__(msg, expected_len, actual_len)
    self.expected_len = expected_len
    self.actual_len = actual_len

class AckValueError(AckError):
  """Some value in return data of the camera is wrong (violation of GVCP specification)"""
  def __init__(self, msg: str, expected_value: any, actual_value: any) -> None:
    super().__init__(msg, expected_value, actual_value)
    self.expected_value = expected_value
    self.actual_value = actual_value

class AckIdError(AckError):
  """Acknowledgement ID does not match last request ID"""
  def __init__(self, msg: str, req_id: int, ack_id: int) -> None:
    super().__init__(msg, req_id, ack_id)
    self.req_id = req_id
    self.ack_id = ack_id

class NotConnectedError(CamControllerException):
  """Cannot connect to the camera / no connection"""
  pass

class IsConnectedError(CamControllerException):
  """Already connected to the camera"""
  pass

class StreamClosedError(CamControllerException):
  """Stream channel is not open"""
  pass
