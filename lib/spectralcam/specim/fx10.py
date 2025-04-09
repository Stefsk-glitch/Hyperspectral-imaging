import time

from ...spectralcam.specim.fxbase import FXBase
from ...spectralcam.gentl import GCSystem

class FX10(FXBase):
  """Class to provide easy Python interface for Specim FX10e."""

  DEV_INFO_VENDOR = "Specim"
  DEV_INFO_MODEL = "FX10e"

  def set_defaults(self, frame_rate: float = 20.0, exposure_time: float = 2000.0) -> None:
    """
    Set default parameters to the camera.

    :param frame_rate: Frame rate of the camera, default 20 fps
    :param exposure_time: Exposure time of the camera, default
    :returns: None
    :raises NotConnectedError: No connection
    :raises AckError: Problem with an acknowledgement from the camera
    """
    self._check_connection()

    trigger_interleave = self.get("Trigger_Interleave")
    if not trigger_interleave:
      self.set("Trigger_Interleave", True)

    en_aber_correction = self.get("AberCorrection_Enable")
    if not en_aber_correction:
      self.set("AberCorrection_Enable", True)

    # TODO Temperature_Update, Temperature_FPGA, Temperature_Proc

    frame_start_trigger_mode = self.get("FrameStart_TriggerMode")
    if frame_start_trigger_mode != "Off":
      self.set("FrameStart_TriggerMode", "Off")

    exposure_mode = self.get("ExposureMode")
    if exposure_mode != "Timed":
      self.set("ExposureMode", "Timed")

    en_frame_rate = self.get("EnAcquisitionFrameRate")
    if not en_frame_rate:
      self.set("EnAcquisitionFrameRate", True)

    self.set("ExposureTime", exposure_time)
    self.set("AcquisitionFrameRate", frame_rate)
    self.set("GevSCPD", 10000) # Packet send delay in 10 nano seconds

    acquisition_mode = self.get("AcquisitionMode")
    if acquisition_mode != "Continuous":
      self.set("AcquisitionMode", "Continuous")

    pulse_len = 200
    self.set("MotorShutter_PulseRev", pulse_len)
    time.sleep(pulse_len / 1000)

if __name__ == "__main__":

  # Find connected FX10 camera automatically (more or less)
  system = GCSystem()
  fx10, intf = system.discover(FX10)
