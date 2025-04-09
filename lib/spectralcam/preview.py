import time
from threading import Thread, Event, Lock
from collections import deque
from typing import Union

import numpy as np
from vispy import gloo, app
from vispy.gloo import Program
from vispy.util.transforms import ortho

# Preview class is mostly copied from harvester https://github.com/genicam/harvesters (Apache 2.0 licence)

class PreviewWindow(app.Canvas):
  """Actual preview window class. Creates a vispy canvas on a window to display frames from a camera."""

  def __init__(self, width: int, height: int, title: str, display_rate: float = 30.0):
    super().__init__(title=title, size=(width, height), autoswap=True, vsync=True, keys='interactive')

    self._background_color = "gray"
    self._width, self._height = width, height
    self._row = self._height - 1
    self._is_dragging = False
    self._origin = [0, 0]
    self._display_rate = display_rate
    self._timer = app.Timer(1. / self._display_rate, connect=self.update, start=True)

    self._buffers = []

    vertex_shader = """
      uniform mat4 u_model;
      uniform mat4 u_view;
      uniform mat4 u_projection;

      attribute vec2 a_position;
      attribute vec2 a_texcoord;

      varying vec2 v_texcoord;

      void main (void)
      {
        v_texcoord = a_texcoord;
        gl_Position = u_projection * u_view * u_model * vec4(a_position, 0.0, 1.0);
      }
    """

    fragment_shader = """
      varying vec2 v_texcoord;
      uniform sampler2D texture;
      void main()
      {
        gl_FragColor = texture2D(texture, v_texcoord);
      }
    """

    self._translate = 0.
    self._latest_translate = self._translate
    self._magnification = 1.

    # Apply shaders.
    self._program = Program(vertex_shader, fragment_shader, count=4)

    self._vertices = np.zeros(4, dtype=[
      ('a_position', np.float32, 2),
      ('a_texcoord', np.float32, 2)
    ])
    self._vertices['a_texcoord'] = np.array(
      [[0., 1.], [1., 1.], [0., 0.], [1., 0.]]
    )

    self._texture = np.zeros(
      (self._height, self._width, 3),
      dtype="uint8"
    )

    self._program['u_model'] = np.eye(4, dtype=np.float32)
    self._program['u_view'] = np.eye(4, dtype=np.float32)
    self._program['texture'] = self._texture

    self._coordinate = [0, 0]

    self.apply_magnification()

  @property
  def display_rate(self):
    return self._display_rate

  @display_rate.setter
  def display_rate(self, value):
    self._display_rate = value
    self._timer.stop()
    self._timer.start(interval=1./self._display_rate)

  def set_size(self, width: int, height: int) -> None:
    updated = False
    if self._width != width or self._height != height:
      self._width = width
      self._height = height
      updated = True
    if updated:
      self.native.resize(width, height)
      self.apply_magnification()

  def release_buffers(self):
    for _buffer in self._buffers:
      if _buffer:
        _buffer.queue()
    self._buffers.clear()

  def on_draw(self, event):
    gloo.clear(color=self._background_color)
    self._program.draw('triangle_strip')

  def push_row(self, row: np.ndarray) -> None:
    """Add new row to the preview window."""
    if len(row) != self._width:
      multiplier = self._width / len(row)
      if multiplier.is_integer():
        row = np.repeat(row, multiplier, 0)
      else:
        raise ValueError("Preview row length is invalid")
    if self._row >= 0:
      self._texture[self._row] = row
      self._row -= 1
    else:
      self._texture = np.roll(self._texture, 1, 0)
      self._texture[0] = row
    self._program['texture'] = self._texture

  def apply_magnification(self):
    canvas_w, canvas_h = self.physical_size
    gloo.set_viewport(0, 0, canvas_w, canvas_h)

    ratio = self._magnification
    w, h = self._width, self._height

    self._program['u_projection'] = ortho(
      self._coordinate[0],
      canvas_w * ratio + self._coordinate[0],
      self._coordinate[1],
      canvas_h * ratio + self._coordinate[1],
      -1, 1
    )

    x, y = int((canvas_w * ratio - w) / 2), int((canvas_h * ratio - h) / 2)  # centering x & y

    self._vertices['a_position'] = np.array(
      [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]
    )

    self._program.bind(gloo.VertexBuffer(self._vertices))

  def on_mouse_wheel(self, event):
    self._translate += event.delta[1]
    power = 5.  # 2 ** exponent
    stride = 7.
    translate = self._translate
    translate = min(power * stride, translate)
    translate = max(-power * stride, translate)
    self._translate = translate
    self._magnification = 2 ** -(self._translate / stride)
    if self._latest_translate != self._translate:
      self.apply_magnification()
      self._latest_translate = self._translate

  def on_mouse_press(self, event):
    self._is_dragging = True
    self._origin = event.pos

  def on_mouse_release(self, event):
    self._is_dragging = False

  def on_mouse_move(self, event):
    if self._is_dragging:
      adjustment = 1.
      ratio = self._magnification * adjustment
      delta = event.pos - self._origin
      self._origin = event.pos
      self._coordinate[0] -= (delta[0] * ratio)
      self._coordinate[1] += (delta[1] * ratio)
      self.apply_magnification()

PREVIEW_NONE = 0
PREVIEW_CREATE = 1
PREVIEW_DESTROY = 2
PREVIEW_SHOW = 3
PREVIEW_HIDE = 4

class Preview():
  """Class to control the preview window."""

  def __init__(self, params: tuple[int, int, str], event: Event, lock: Lock) -> None:
    self._params = params
    self._cmds = deque()
    self._event = event
    self._lock = lock
    self._preview: Union[None, PreviewWindow] = None
    self._cmds.appendleft(PREVIEW_CREATE)
    self._event.set()

  def close(self) -> None:
    """Close the window permanently. All resources reserved by the window instance will be freed."""
    self._lock.acquire()
    self._cmds.appendleft(PREVIEW_DESTROY)
    self._event.set()
    self._lock.release()

  def show(self) -> None:
    """Make the window visible on screen."""
    self._lock.acquire()
    self._cmds.appendleft(PREVIEW_SHOW)
    self._event.set()
    self._lock.release()

  def hide(self) -> None:
    """Hide the window from screen."""
    self._lock.acquire()
    self._cmds.appendleft(PREVIEW_HIDE)
    self._event.set()
    self._lock.release()

  def getcmd(self) -> Union[None, int]:
    if len(self._cmds) > 0:
      return self._cmds.pop()
    else:
      return None

  def is_visible(self) -> bool:
    """Returns true when the window is visible on the screen."""
    return self._preview != None and self._preview.native.isVisible()

  def push_row(self, row: np.ndarray) -> None:
    """
    Add new row of pixels to the preview.
    
    :param row: Row of pixels to add
    """
    self._preview.push_row(row)

class PreviewFactory():
  """
  Starts a separate thread to handle preview windows. Only one instance of this should be created
  during a program lifecycle.

  QT does not support multiple threads very well, or like, at all...
  """
  def __init__(self) -> None:
    self._instances: list[Preview] = []
    self._event = Event()
    self._lock = Lock()
    self._quit = False
    self._thread = Thread(target=self._loop)
    self._thread.start()

  def _loop(self):
    while True:
      visible_count = 0
      if self._quit:
        for instance in self._instances:
          instance._preview.native.destroy()
          instance._preview.app.process_events()
        break
      self._lock.acquire()
      for instance in self._instances:
        if self._event.is_set():
          while True:
            cmd = instance.getcmd()
            if cmd == None:
              break
            elif cmd == PREVIEW_CREATE and instance._preview == None:
              width, height, title = instance._params
              instance._preview = PreviewWindow(width, height, title)
            elif cmd == PREVIEW_DESTROY and instance._preview != None:
              instance._preview.native.destroy()
              self._instances.remove(instance)
            elif cmd == PREVIEW_SHOW and instance._preview != None:
              instance._preview.native.show()
            elif cmd == PREVIEW_HIDE and instance._preview != None:
              instance._preview.native.hide()
            else:
              print("WARNING: Cannot complete the command, a preview window is probably not created.")
        if instance._preview != None and instance._preview.native.isVisible():
          instance._preview.app.process_events()
          visible_count += 1
      self._event.clear()
      self._lock.release()
      if visible_count == 0:
        self._event.wait()
      else:
        time.sleep(0.05)

  def create(self, width: int = 640, height: int = 480, title: str = "Preview") -> Preview:
    """
    Create a new preview window.
    
    :param width: Width of the preview window
    :param height: Height of the preview window
    :param title: Text show on the preview window top bar

    :returns: Instance of preview class
    """
    params = (width, height, title)
    instance = Preview(params, self._event, self._lock)
    self._instances.append(instance)
    return instance

  def join(self):
    """
    Close all window instances and shut down the thread. Call this only when you want to close the
    whole python program.
    """
    self._event.set()
    self._quit = True
    self._thread.join()
