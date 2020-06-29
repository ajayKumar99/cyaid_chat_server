from server import app as application
from server import socketio

if __name__ == "__main__":
    socketio.run(application, port=3010, debug=True)