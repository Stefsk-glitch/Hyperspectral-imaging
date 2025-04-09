#if defined(unix) || defined(__unix__) || defined(__unix)
  #define IS_UNIX 1
#elif defined(_WIN32)
  #define IS_WIN32 1
#else
  #error "Unsupported platform. Only Windows and Linux are supported."
#endif

#ifdef IS_WIN32
  #pragma comment(lib, "ws2_32.lib")
#endif

#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_21_API_VERSION // Prevent usage of deprecated Numpy API

#include <Python.h>
#include "numpy/arrayobject.h"
#include <stdio.h>
#include <errno.h>
#if defined IS_UNIX
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <pthread.h>
#elif defined IS_WIN32
  #include <Ws2tcpip.h>
  #include <winsock2.h>
  #include <windows.h>
#endif

#define false 0
#define true 1

#define BUF_SIZE 2048
#define GVSP_HEADER_SIZE 8
#define GVSP_TOTAL_HEADER_SIZE 36 // IP + UDP + GVSP header

#define MONO8 0x01080001
#define MONO10 0x01100003
#define MONO10PACKED 0x010C0004
#define MONO12 0x01100005
#define MONO12PACKED 0x010C0006
#define MONO16 0x01100007

typedef unsigned char bool;
typedef unsigned short ushort;
typedef unsigned long ulong;
typedef unsigned char byte;

char errmsg[256];

#if defined IS_UNIX
  typedef int soc_t;
  typedef pthread_mutex_t mutex_t;
  typedef pthread_t thread_t;
  int lock_mutex(pthread_mutex_t *mutex)
  {
    return pthread_mutex_lock(mutex);
  }
  int unlock_mutex(pthread_mutex_t *mutex)
  {
    return pthread_mutex_unlock(mutex);
  }
#elif defined IS_WIN32
  typedef SOCKET soc_t;
  typedef HANDLE thread_t;
  typedef HANDLE mutex_t;
  typedef unsigned long in_addr_t;
  int lock_mutex(HANDLE *mutex)
  {
    return WaitForSingleObject(mutex, INFINITE);
  }
  int unlock_mutex(HANDLE *mutex)
  {
    return ReleaseMutex(mutex);
  }
#endif

struct gvsp
{
  // Feedback settings
  bool verbose;
  bool warnings;

  // Socket and receive loop
  soc_t sockfd;
  ushort port;
  thread_t recv_thread;

  // Receiving enabled (this must be protected by g_en_lock)
  bool recv_en;
  mutex_t en_lock;

  // Image (these must be protected by g_frame_lock)
  ulong size_x;
  ulong size_s;
  ulong frame_size;
  bool leader_received;
  ulong received_packets;
  ulong packet_count;
  ulong packet_size;
  ulong payload_size;
  ulong pixel_format;
  byte *frame_buf;
  mutex_t frame_lock;

  // Output for frame data
  PyObject *frame_cb;
};

ulong bytes_to_uint16(byte *bytes)
{
  return (*bytes << 8) + *(bytes + 1);
}

ulong bytes_to_uint24(byte *bytes)
{
  return (*bytes << 16) + (*(bytes + 1) << 8) + *(bytes + 2);
}

ulong bytes_to_uint32(byte *bytes)
{
  return (*bytes << 24) + (*(bytes+1) << 16) + (*(bytes+2) << 8) + *(bytes+3);
}

PyObject * handle_py_error(void)
{
  if (errno != 0)
  {
    PyObject *type_obj;
    const char *msg = strerror(errno);
    // Map most likely errnos to Python exceptions
    switch (errno)
    {
      case EACCES:
      case EPERM:
        type_obj = PyExc_PermissionError;
        break;
      case EISCONN:
      case ENOTCONN:
      case EADDRINUSE:
        type_obj = PyExc_ConnectionError;
        break;
      case EINVAL:
      case EBADF:
        type_obj = PyExc_OSError;
        break;
      case ENOBUFS:
      case ENOMEM:
        type_obj = PyExc_MemoryError;
        break;
      default:
        type_obj = PyExc_Exception;
        break;
    }
    PyErr_SetString(type_obj, msg);
    errno = 0;
  }

  if (PyErr_Occurred() != NULL)
  {
    PyObject *type_obj;
    PyObject *msg_obj;
    PyObject *traceback_obj;
    PyObject *msgout_obj;
    char prefix[] = "GVSP: ";
    size_t prefix_len = strlen(prefix);

    PyErr_Fetch(&type_obj, &msg_obj, &traceback_obj);
    Py_ssize_t msg_len = 0;
    const char *msg = PyUnicode_AsUTF8AndSize(msg_obj, &msg_len);

    char *msgout = malloc(prefix_len + msg_len);
    memcpy(msgout, prefix, prefix_len);
    memcpy(msgout + prefix_len, msg, msg_len);

    msgout_obj = PyUnicode_FromStringAndSize(msgout, prefix_len + msg_len);
    PyErr_Restore(type_obj, msgout_obj, traceback_obj);

    Py_DECREF(msg_obj);
    free(msgout);
    return NULL;
  }

  return PyLong_FromLong(0);
}

bool is_receiving(struct gvsp *g)
{
  lock_mutex(&g->en_lock);
  if (g->recv_en)
  {
    unlock_mutex(&g->en_lock);
    PyErr_SetString(PyExc_ConnectionError, "Listening incoming packets is active");
    return true;
  }
  unlock_mutex(&g->en_lock);
  // If we get here it is safe to assume there's only 1 thread running
  return false;
}

bool is_not_receiving(struct gvsp *g)
{
  lock_mutex(&g->en_lock);
  if (!g->recv_en)
  {
    unlock_mutex(&g->en_lock);
    PyErr_SetString(PyExc_ConnectionError, "Already stopped listening incoming packets");
    return true;
  }
  unlock_mutex(&g->en_lock);
  return false;
}

bool has_no_socket(struct gvsp *g)
{
  if (g->sockfd < 0)
  {
    PyErr_SetString(PyExc_ConnectionError, "No socket, you must first call gvsp.create_socket()");
    return true;
  }
  return false;
}

bool has_buffer(struct gvsp *g)
{
  if (g->frame_buf != NULL)
  {
    PyErr_SetString(PyExc_MemoryError, "Buffer already exists");
    return true;
  }
  return false;
}

bool has_no_buffer(struct gvsp *g)
{
  if (g->frame_buf == NULL)
  {
    PyErr_SetString(PyExc_MemoryError, "Buffer does not exist, you must first call gvsp.create_buffer()");
    return true;
  }
  return false;
}

void init_gvsp(struct gvsp *g)
{
#if defined IS_UNIX
  mutex_t en_lock = PTHREAD_MUTEX_INITIALIZER;
  mutex_t frame_lock = PTHREAD_MUTEX_INITIALIZER;
#elif defined IS_WIN32
  mutex_t en_lock = CreateMutex(NULL, false, NULL);
  mutex_t frame_lock = CreateMutex(NULL, false, NULL);
#endif

  g->verbose = false;
  g->warnings = true;

  g->sockfd = -1;
  g->port = 0;

  g->recv_en = false;
  g->en_lock = en_lock;

  g->size_x = 0;
  g->size_s = 0;
  g->leader_received = false;
  g->received_packets = 0;
  g->packet_count = 0;
  g->packet_size = 0;
  g->payload_size = 0;
  g->frame_buf = NULL;
  g->frame_lock = frame_lock;

  g->frame_cb = NULL;
}

struct gvsp * get_gvsp(PyObject *args, PyObject *kwargs)
{
  PyObject *g_caps;
  static char *kwlist[] = {"g", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &g_caps))
  {
    return NULL;
  }
  return PyCapsule_GetPointer(g_caps, "gvsp");
}

void free_frame(void *caps)
{
  void *buf = PyCapsule_GetPointer(caps, PyCapsule_GetName(caps));
  free(buf);
}

bool validate_header(struct gvsp *g, byte *buf)
{
  ulong status;
  if (*buf != 0 || *(buf+1) != 0)
  {
    status = bytes_to_uint16(buf);
    if (g->warnings) printf("GVSP WARNING: Received packet with status: 0x%04lx\n", status);
    return false;
  }
  if (*(buf+2) == 0 && *(buf+3) == 0)
  {
    return false;
  }
  if (*(buf+4) & 0x80)
  {
    if (g->warnings) printf("GVSP WARNING: Extended ID is not supported\n");
    return false;
  }
  return true;
}

void * decode_mono8(struct gvsp *g, int *typenum)
{
  ulong payload_size = (g->size_s * g->size_x);
  byte *frame = malloc(g->size_s * g->size_x * sizeof(byte));
  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  memcpy(frame, g->frame_buf, payload_size);
  *typenum = NPY_UINT8;
  return frame;
}

void * decode_mono10(struct gvsp *g, int *typenum)
{
  ulong payload_size = g->size_s * g->size_x * 2;
  ushort *frame = malloc(g->size_s * g->size_x * sizeof(ushort));
  ulong buf_i;
  byte *buf_p;

  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  for (buf_i = 0; buf_i < payload_size; buf_i += 2)
  {
    buf_p = g->frame_buf + buf_i;
    *(frame + (buf_i >> 1)) = ((*(buf_p+1) & 0x03) << 8) + *buf_p;
  }

  *typenum = NPY_UINT16;
  return frame;
}

void * decode_mono10packed(struct gvsp *g, int *typenum)
{
  ulong payload_size = ((g->size_s * g->size_x) >> 1) * 3;
  ushort *frame = malloc(g->size_s * g->size_x * sizeof(ushort));
  ulong frame_i = 0;
  ulong buf_i;
  byte *buf_p;

  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  for (buf_i = 0; buf_i < payload_size; buf_i += 3)
  {
    frame_i += 2;
    buf_p = g->frame_buf + buf_i;
    *(frame + frame_i) = (*(buf_p) << 2) + (*(buf_p+1) & 0x03);
    *(frame + frame_i + 1) = (*(buf_p+2) << 2) + ((*(buf_p+1) & 0x30) >> 4);
  }

  *typenum = NPY_UINT16;
  return frame;
}

void * decode_mono12(struct gvsp *g, int *typenum)
{
  ulong payload_size = g->size_s * g->size_x * 2;
  ushort *frame = malloc(g->size_s * g->size_x * sizeof(ushort));
  ulong buf_i;
  byte *buf_p;

  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  for (buf_i = 0; buf_i < payload_size; buf_i += 2)
  {
    buf_p = g->frame_buf + buf_i;
    *(frame + (buf_i >> 1)) = ((*(buf_p+1) & 0x0f) << 8) + *buf_p;
  }

  *typenum = NPY_UINT16;
  return frame;
}

void * decode_mono12packed(struct gvsp *g, int *typenum)
{
  ulong payload_size = ((g->size_s * g->size_x) >> 1) * 3;
  ushort *frame = malloc(g->size_s * g->size_x * sizeof(ushort));
  ulong frame_i = 0;
  ulong buf_i;
  byte *buf_p;

  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  for (buf_i = 0; buf_i < payload_size; buf_i += 3)
  {
    frame_i += 2;
    buf_p = g->frame_buf + buf_i;
    *(frame + frame_i) = (*(buf_p) << 4) + (*(buf_p+1) & 0x0f);
    *(frame + frame_i + 1) = (*(buf_p+2) << 4) + ((*(buf_p+1) & 0xf0) >> 4);
  }

  *typenum = NPY_UINT16;
  return frame;
}

void * decode_mono16(struct gvsp *g, int *typenum)
{
  ulong payload_size = g->size_s * g->size_x * 2;
  ushort *frame = malloc(g->size_s * g->size_x * sizeof(ushort));
  ulong buf_i;
  byte *buf_p;

  if (frame == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to allocate memory for a frame, STOPPING THREAD");
    return NULL;
  }
  for (buf_i = 0; buf_i < payload_size; buf_i += 2)
  {
    buf_p = g->frame_buf + buf_i;
    *(frame + (buf_i >> 1)) = (*(buf_p+1) << 8) + *buf_p;
  }

  *typenum = NPY_UINT16;
  return frame;
}

// Protected by g_frame_lock
int handle_leader(struct gvsp *g, byte *buf, ulong buf_len)
{
  // General for all payload types
  if (!validate_header(g, buf) || buf_len < 12)
  {
    if (g->warnings) printf("GVSP WARNING: Received invalid leader packet\n");
    return 0;
  }
  byte *payload = buf + GVSP_HEADER_SIZE;
  ulong payload_len = buf_len - GVSP_HEADER_SIZE;
  if (bytes_to_uint16(payload + 2) != 0x0001)
  {
    if (g->warnings) printf("GVSP WARNING: No other format than uncompressed image is supported\n");
    return 0;
  }

  // Specific to uncompressed image (only supported format. TODO more of them?)
  if (payload_len != 36)
  {
    if (g->warnings) printf("GVSP WARNING: Received invalid uncompressed image leader packet\n");
    return 0;
  }
  if (*payload != 0)
  {
    if (g->warnings) printf("GVSP WARNING: Interlacing is not supported\n");
    return 0;
  }
  g->pixel_format = bytes_to_uint32(payload + 12);
  g->size_x = bytes_to_uint32(payload + 16);
  g->size_s = bytes_to_uint32(payload + 20);
  g->frame_size = g->size_x * g->size_s;
  g->received_packets = 0;
  g->leader_received = true;
  // TODO support for ROI / offset
  // TODO support for padding
  return 0;
}

// Protected by g_frame_lock
int handle_frame(struct gvsp *g, byte *buf, ulong buf_len)
{
  ulong packet_id = bytes_to_uint24(buf + 5);
  ulong start = (packet_id - 1) * g->packet_size;
  ulong i;
  if (GVSP_HEADER_SIZE + g->packet_size > buf_len)
  {
    if (g->warnings) printf("GVSP WARNING: Received data payload packet is too small, expected %ld bytes, received %ld bytes\n", GVSP_HEADER_SIZE + g->packet_size, buf_len);
    return 0;
  }
  if (start + g->packet_size > g->payload_size)
  {
    if (g->warnings) printf("GVSP WARNING: Received data payload packet exceeds frame buffer size\n");
    return 0;
  }
  for (i = 0; i < g->packet_size; i++)
  {
    *(g->frame_buf + start + i) = *(buf + GVSP_HEADER_SIZE + i);
  }
  g->received_packets++;
  return 0;
}

// Protected by g_frame_lock
int handle_trailer(struct gvsp *g, byte *buf, ulong buf_len)
{

  if (!g->leader_received)
  {
    if (g->warnings) printf("GVSP WARNING: Trailer received before leader\n");
    return 0;
  }
  g->leader_received = false;
  if (!validate_header(g, buf) || buf_len < 12)
  {
    if (g->warnings) printf("GVSP WARNING: Received invalid trailer packet\n");
    return 0;
  }
  if (g->received_packets != g->packet_count)
  {
    if (g->warnings) printf("GVSP WARNING: %ld packets dropped\n", g->packet_count - g->received_packets);
    return 0;
  }

  PyGILState_STATE gil;
  PyObject *frame_py;
  PyObject *args_py;
  PyObject *caps_py;
  void *frame = NULL; // unsigend char or usinged short
  npy_intp nds[] = {g->size_s, g->size_x};
  int typenum;
  int bit_depth = 0;

  // Decode received frame data
  switch (g->pixel_format)
  {
    case MONO8:
      frame = decode_mono8(g, &typenum);
      bit_depth = 8;
      break;
    case MONO10:
      frame = decode_mono10(g, &typenum);
      bit_depth = 10;
      break;
    case MONO10PACKED:
      frame = decode_mono10packed(g, &typenum);
      bit_depth = 10;
      break;
    case MONO12:
      frame = decode_mono12(g, &typenum);
      bit_depth = 12;
      break;
    case MONO12PACKED:
      frame = decode_mono12packed(g, &typenum);
      bit_depth = 12;
      break;
    case MONO16:
      frame = decode_mono16(g, &typenum);
      bit_depth = 16;
      break;
    default:
      if (g->warnings) printf("GVSP WARNING: Pixel format is not supported\n");
  }
  if (frame == NULL)
  {
    return -1;
  }

  // Create numpy.ndarray of the frame
  gil = PyGILState_Ensure();
  frame_py = PyArray_SimpleNewFromData(2, nds, typenum, frame);
  if (frame_py == NULL)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to create numpy.ndarray from a frame, STOPPING THREAD");
    return -1;
  }
  caps_py = PyCapsule_New(frame, "wrapped_buffer", (PyCapsule_Destructor)&free_frame);
  if (PyArray_SetBaseObject((PyArrayObject*)frame_py, caps_py) == -1)
  {
    strcpy(errmsg, "GVSP ERROR: Failed to set destructor function for frame, STOPPING THREAD");
    Py_DECREF(frame_py);
    return -1;
  }

  // Ouput frame
  if (g->frame_cb != NULL)
  {
    args_py = Py_BuildValue("(Oi)", frame_py, bit_depth);
    PyObject_CallObject(g->frame_cb, args_py);
    Py_DECREF(args_py);
  }
  Py_DECREF(frame_py);
  PyGILState_Release(gil);

  return 0;
}

#if defined IS_UNIX
void * receive(void *vargp)
#elif defined IS_WIN32
DWORD receive(void *vargp)
#endif
{
  struct gvsp *g = vargp;
  byte *buf;
#if defined IS_UNIX
  ssize_t buf_len;
#elif defined IS_WIN32
  int buf_len;
#endif
  ushort packet_format;
  int result = 0;

  buf = malloc(BUF_SIZE);
  if (buf == NULL)
  {
    printf("GVSP ERROR: Failed to allocate memory, aborting thread");
    errno = ENOMEM;
#if defined IS_UNIX
    return NULL;
#elif defined IS_WIN32
    return 0;
#endif
  }
  if (g->verbose) printf("GVSP: Receiver is listening port: %d\n", g->port);
  while (true)
  {
    buf_len = recv(g->sockfd, buf, BUF_SIZE, 0);
    lock_mutex(&g->frame_lock);
    if (buf_len > 0)
    {
      packet_format = *(buf + 4) & 0x0f;
      if (packet_format == 3)
      {
        result = handle_frame(g, buf, (ulong)buf_len);
      }
      else if (packet_format == 1)
      {
        result = handle_leader(g, buf, (ulong)buf_len);
      }
      else if (packet_format == 2)
      {
        result = handle_trailer(g, buf, (ulong)buf_len);
      }
    }
    lock_mutex(&g->en_lock);
    if (!g->recv_en)
    {
      unlock_mutex(&g->en_lock);
      unlock_mutex(&g->frame_lock);
      break;
    }
    unlock_mutex(&g->en_lock);
    unlock_mutex(&g->frame_lock);
    if (result < 0)
    {
      printf(errmsg);
      break;
    }
  }
  free(buf);
#if defined IS_UNIX
  return NULL;
#elif defined IS_WIN32
  return 0;
#endif
}

int init_receive(struct gvsp *g)
{
#if defined IS_UNIX
  pthread_create(&g->recv_thread, NULL, receive, g);
#elif defined IS_WIN32
  g->recv_thread = CreateThread(NULL, 0, receive, g, 0, NULL);
#endif
  return 0;
}

int open_connection(struct gvsp *g, char *ip_str)
{
  // Initialize address
  struct sockaddr_in addr;
  in_addr_t ip;
  memset(&addr, '0', sizeof addr);
  inet_pton(AF_INET, ip_str, &ip);
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = ip;
  addr.sin_port = htons(g->port);

  // Send dummy packet to open firewall
  byte data[4] = {0, 0, 0, 0};
  if (sendto(g->sockfd, data, sizeof data, 0, (struct sockaddr*) &addr, sizeof addr) < 0)
  {
    return -1;
  }

  if (g->verbose) printf("GVSP: Connection open\n");
  return 0;
}

static const char DOC_CREATE_SOCKET[] = "Create and bind a socket to receive frames from the camera.\n\n"
":param addr: Host IP address\n"
":returns: Tuple of GVSP instance and host port\n"
":raises MemoryError: Failed to allocate memory for GVSP instance\n";
static PyObject * create_socket(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  char *ip_str;
  static char *kwlist[] = {"addr", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s", kwlist, &ip_str)) goto err1;

  // Create an "instance" of GVSP
  struct gvsp *g;
  g = malloc(sizeof (struct gvsp));
  if (g == NULL)
  {
    PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory for GVSP instance");
    goto err1;
  }
  init_gvsp(g);

#ifdef IS_WIN32
  // Initialize Windows sockets
  WSADATA wsa;
  if (WSAStartup(MAKEWORD(2,2),&wsa) != 0) goto err1;
#endif

  // Initialize arguments
  struct sockaddr_in addr_init;
  struct sockaddr_in addr_fin;
  in_addr_t ip;
  socklen_t addr_fin_len = sizeof addr_fin;
  memset(&addr_init, '0', sizeof addr_init);
  memset(&addr_fin, '0', sizeof addr_fin);
  inet_pton(AF_INET, ip_str, &ip);
  addr_init.sin_family = AF_INET;
  addr_init.sin_addr.s_addr = ip;
  addr_init.sin_port = htons(0);

  // Set receive timeout
#if defined IS_UNIX
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 100000;
#elif defined IS_WIN32
  DWORD tv = 100;
#endif

  // Create socket and bind it to host address
  g->sockfd = socket(AF_INET, SOCK_DGRAM, 0);
  if (g->sockfd < 0) goto err2;
  if (setsockopt(g->sockfd, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof tv) < 0) goto err3;
  if (bind(g->sockfd, (struct sockaddr*) &addr_init, sizeof addr_init) < 0) goto err3;
  if (getsockname(g->sockfd, (struct sockaddr*) &addr_fin, &addr_fin_len) < 0) goto err3;
  g->port = ntohs(addr_fin.sin_port);

  if (g->verbose) printf("GVSP: Socket created on %s:%d\n", ip_str, g->port);

  return Py_BuildValue("NN", PyCapsule_New(g, "gvsp", NULL), PyLong_FromLong(g->port));
#if defined IS_UNIX
  err3: close((int)g->sockfd);
#elif defined IS_WIN32
  err3: closesocket(g->sockfd);
#endif
err2: free(g);
err1: return handle_py_error();
}

static const char DOC_CLOSE_SOCKET[] = "Close the socket.\n\n"
":param g: GVSP instance\n"
":returns: None\n"
":raises ConnectionError: Socket has been closed already or receiving of frames is active\n";
static PyObject * close_socket(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  struct gvsp *g = get_gvsp(args, kwargs);
  if (g == NULL) goto err;

  // Check state of GVSP
  if (is_receiving(g)) goto err;
  if (has_no_socket(g)) goto err;

  // Close socket and delete instance
#if defined IS_UNIX
  if (close((int)g->sockfd) < 0) goto err;
#elif defined IS_WIN32
  if (closesocket(g->sockfd) < 0) goto err;
#endif
  g->sockfd = -1;
  if (g->verbose) printf("GVSP: Socket closed\n");
  free(g);

err: return handle_py_error();
}

static const char DOC_CREATE_BUFFER[] = "Create buffer to receive frames.\n\n"
":param g: GVSP instance\n"
":param payload_size: Payload size of one full frame + possible padding\n"
":param packet_size: Size of a single packet\n"
":returns: None\n"
":raises ConnectionError: GVSP is receiving frames, buffer must have been created already\n"
":raises MemoryError: Failed to allocate memory or buffer is created already\n"
":raises ValueError: Problem with payload size or packet size\n";
static PyObject * create_buffer(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  PyObject *g_caps;
  ulong payload_size = 0;
  ulong packet_size = 0;
  ulong packet_payload_size = 0;
  static char *kwlist[] = {"g", "payload_size", "packet_size", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Okk", kwlist, &g_caps, &payload_size, &packet_size)) goto err1;
  struct gvsp *g = PyCapsule_GetPointer(g_caps, "gvsp");
  if (g == NULL) goto err1;

  // Check state of GVSP
  if (is_receiving(g)) goto err1;
  if (has_buffer(g)) goto err1;

  // Create buffer to receive frames
  g->frame_buf = malloc(payload_size);
  if (g->frame_buf == NULL)
  {
    PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory for frame buffer");
    goto err1;
  }
  packet_payload_size = packet_size - GVSP_TOTAL_HEADER_SIZE;
  if (packet_payload_size <= 0)
  {
    PyErr_SetString(PyExc_ValueError, "Packet size must be greater than 0 (without headers)");
    goto err2;
  }
  if (payload_size % packet_payload_size != 0)
  {
    PyErr_SetString(PyExc_ValueError, "Payload size must be multiple of packet size");
    goto err2;
  }
  g->payload_size = payload_size;
  g->packet_size = packet_payload_size;
  g->packet_count = payload_size / g->packet_size;

  if (g->verbose)
  {
    printf("GVSP: Packet size: %ld, packet count: %ld\n", g->packet_size, g->packet_count);
    printf("GVSP: Frame buffer created, %ld bytes\n", payload_size);
  }
  return PyLong_FromLong(0);
err2: free(g->frame_buf);
err1: return handle_py_error();
}

static const char DOC_FREE_BUFFER[] = "Release the frame buffer.\n\n"
":param g: GVSP instance\n"
":returns: None\n"
":raises ConnectionError: GVSP is receiving frames, buffer cannot be freed\n"
":raises MemoryError: Buffer has already been freed\n";
static PyObject * free_buffer(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  struct gvsp *g = get_gvsp(args, kwargs);
  if (g == NULL) goto err;

  // Check state of GVSP
  if (is_receiving(g)) goto err;
  if (has_no_buffer(g)) goto err;

  // Free buffer and reset related values
  g->payload_size = 0;
  g->packet_size = 0;
  g->packet_count = 0;
  free(g->frame_buf);
  g->frame_buf = NULL;

  if (g->verbose) printf("GVSP: Frame buffer freed\n");
err: return handle_py_error();
}

static const char DOC_START_RECEIVE[] = "Start listening incoming GVSP packets.\n\n"
":param g: GVSP instance\n"
":param addr: IP address of the camera as string\n"
":returns: None\n"
":raises ConnectionError: GVSP is already receiving frames or there is no socket to receive frames\n"
":raises MemoryError: There is no buffer\n";
static PyObject * start_receive(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  PyObject *g_caps;
  char *ip_str;
  static char *kwlist[] = {"g", "addr", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os", kwlist, &g_caps, &ip_str)) goto err;
  struct gvsp *g = PyCapsule_GetPointer(g_caps, "gvsp");
  if (g == NULL) goto err;

  // Check state of GVSP
  if (is_receiving(g)) goto err;
  if (has_no_socket(g)) goto err;
  if (has_no_buffer(g)) goto err;

  // Send dummy packet to traverse firewall
  if (open_connection(g, ip_str) < 0) goto err;

  // Start listening for incoming packets
  g->recv_en = true;
  init_receive(g);

err: return handle_py_error();
}

static const char DOC_STOP_RECEIVE[] = "Stop listening packets.\n\n"
":param g: GVSP instance\n"
":returns: None\n"
":raises ConnectionError: Already stopped receiving frames\n";
static PyObject * stop_receive(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  struct gvsp *g = get_gvsp(args, kwargs);
  if (g == NULL) goto err;

  // Check state of GVSP
  if (is_not_receiving(g)) goto err;

  lock_mutex(&g->en_lock);
  g->recv_en = false;
  unlock_mutex(&g->en_lock);
  PyThreadState *tstate = PyEval_SaveThread();
#if defined IS_UNIX
  pthread_join(g->recv_thread, NULL);
#elif defined IS_WIN32
  WaitForSingleObject(g->recv_thread, INFINITE);
#endif
  PyEval_RestoreThread(tstate);
  // Only single thread should be running now

  if (g->verbose) printf("GVSP: Stopped listening incoming packets\n");
err: return handle_py_error();
}

static const char DOC_FRAME_CB[] = "Set a callback function to get frames.\n\n"
":param g: GVSP instance\n"
":param callback: Function to call when a frame is received or None\n"
":returns: None\n"
":raises TypeError: Callback is not a function or None\n";
static PyObject * set_frame_cb(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  PyObject *g_caps;
  PyObject *cb;
  static char *kwlist[] = {"g", "callback", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", kwlist, &g_caps, &cb)) goto err;
  struct gvsp *g = PyCapsule_GetPointer(g_caps, "gvsp");
  if (g == NULL) goto err;
  if (!PyCallable_Check(cb) && cb != NULL) {
    PyErr_SetString(PyExc_TypeError, "Callback function must be callable");
    goto err;
  }

  // Set callback function
  Py_XINCREF(cb);
  lock_mutex(&g->frame_lock);
  Py_XDECREF(g->frame_cb);
  g->frame_cb = cb;
  unlock_mutex(&g->frame_lock);

  if (g->verbose) printf("GVSP: Frame callback function set\n");
err: return handle_py_error();
}

static const char DOC_SET_VERBOSE[] = "Set verbose messages on or off.\n\n"
":param g: GVSP instance\n"
":param verbose: True to set verbose mode on, False to set it off\n"
":returns: None\n";
static PyObject * set_verbose(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  PyObject *g_caps;
  int verbose;
  static char *kwlist[] = {"g", "verbose", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Op", kwlist, &g_caps, &verbose)) goto err;
  struct gvsp *g = PyCapsule_GetPointer(g_caps, "gvsp");
  if (g == NULL) goto err;

  // Set verbose messages on/off
  g->verbose = verbose;

err: return handle_py_error();
}

static const char DOC_SET_WARNINGS[] = "Set warning messages on or off.\n\n"
":param g: GVSP instance\n"
":param warnings: True to set warnings on, False to set them off\n"
":returns: None\n";
static PyObject * set_warnings(PyObject *self, PyObject *args, PyObject *kwargs)
{
  errno = 0;

  // Parse arguments
  PyObject *g_caps;
  int warnings;
  static char *kwlist[] = {"g", "warnings", NULL};
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Op", kwlist, &g_caps, &warnings)) goto err;
  struct gvsp *g = PyCapsule_GetPointer(g_caps, "gvsp");
  if (g == NULL) goto err;

  // Set warning message on/off
  g->warnings = warnings;

err: return handle_py_error();
}

static PyMethodDef gvspmethods[] = {
  { "create_socket", (PyCFunction)create_socket, METH_VARARGS | METH_KEYWORDS, DOC_CREATE_SOCKET },
  { "close_socket", (PyCFunction)close_socket, METH_VARARGS | METH_KEYWORDS, DOC_CLOSE_SOCKET },
  { "create_buffer", (PyCFunction)create_buffer, METH_VARARGS | METH_KEYWORDS, DOC_CREATE_BUFFER },
  { "free_buffer", (PyCFunction)free_buffer, METH_VARARGS | METH_KEYWORDS, DOC_FREE_BUFFER },
  { "start_receive", (PyCFunction)start_receive, METH_VARARGS | METH_KEYWORDS, DOC_START_RECEIVE },
  { "stop_receive", (PyCFunction)stop_receive, METH_VARARGS | METH_KEYWORDS, DOC_STOP_RECEIVE },
  { "set_frame_cb", (PyCFunction)set_frame_cb, METH_VARARGS | METH_KEYWORDS, DOC_FRAME_CB },
  { "set_verbose", (PyCFunction)set_verbose, METH_VARARGS | METH_KEYWORDS, DOC_SET_VERBOSE },
  { "set_warnings", (PyCFunction)set_warnings, METH_VARARGS | METH_KEYWORDS, DOC_SET_WARNINGS },
  { NULL, NULL, 0, NULL }
};

static struct PyModuleDef gvspmodule = {
  PyModuleDef_HEAD_INIT, "gvsp", NULL, -1, gvspmethods
};

PyMODINIT_FUNC
PyInit_gvsp(void)
{
  import_array();
  return PyModule_Create(&gvspmodule);
}