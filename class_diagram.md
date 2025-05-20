```mermaid
classDiagram

class main {
    +main()
}

class enums {
    class Enums {
        
    }
}

class event-handler {

}

class models {

}

class pca {

}

class settings {

}

class app {
    +run_app()
    +message_box()
    +set_connection_status()
    -camera_data
    -Tkinter GUI
    -WebSocketServer server
}

class WebSocketServer {
    +start()
    +onClientConnect()
    +onMessage()
    +sendToWemos()
}

class FX10Connector {
    +connect()
    +quick_init_camera()
    +stop_data()
    +save_data()
    +get_settings()
    +get_info()
    +close()
}

class FX10 {
    +set_defaults()
    +open_stream()
    +start_acquire()
    +stop_acquire()
    +close_stream()
}

main --> app
app --> WebSocketServer : hosts
app --> FX10Connector
FX10Connector --> FX10
```