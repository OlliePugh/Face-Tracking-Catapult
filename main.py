import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server
import numpy as np
import cv2
from catapult import Catapult, clamp

face_cascade = cv2.CascadeClassifier('facial.xml')  # load the cascade
cam_resolution = (320,240)

consec_recog = 0

def get_center(x,y,w,h):
    x_center = x+(w/2)
    y_center = y+(h/2)
    return (x_center, y_center)

def get_distance(width):
    width_at_1m = 50
    return width_at_1m/width  # returns the distance in meters

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global consec_recog
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    frame = output.frame  # get the current frame

                    npframe = np.frombuffer(frame, dtype=np.uint8)
                    image = cv2.imdecode(npframe, cv2.IMREAD_COLOR)

                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                    # Draw rectangle around the faces

                    for (x, y, w, h) in faces:
                        cv2.rectangle(image, (x, y), (x+w, y+h), (255, 0, 0), 2)
                        center = get_center(x, y, w, h)

                        if catapult.tracking:
                            catapult.set_pos(((center[0] / cam_resolution[0]) * 2) - 1)
                            catapult.height = clamp(get_distance(w)-1, 0, 1)

                            consec_recog += 1

                            if consec_recog >= 5:
                                catapult.firing = True
                                catapult.firing_enabled = False
                                catapult.tracking = False
                        else:
                            consec_recog = 0

                    if len(faces) < 0:
                        consec_recog = 0

                    print(consec_recog)


                    is_success, frame = cv2.imencode(".jpg", image)
                    with output.condition:
                        output.condition.wait()

                        self.wfile.write(b'--FRAME\r\n')
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(frame))
                        self.end_headers()
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
            except Exception as e:  # on disconnect
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length"))
        post_body = self.rfile.read(content_len)
        if (self.parse_POST(post_body)):
            self.send_response(200)  # say accepted
        else:
            self.send_response(400)
        self.end_headers()
        return


    def parse_POST(self, data):
        data = str(data, "utf-8")
        print("Recieved: ", data)
        decoded = data.split(" ")

        type, value = decoded[0], decoded[1]

        if len(decoded) < 2:  # make sure has packet type and data
            print("Insufficient arguments provided in post request: " + data)
            return False

        if type == "x_damp":
            catapult.x_damp = int(value)/100
            return True

        elif type == "x-offset":
            catapult.x_offset = (int(value)-100)/100
            return True

        elif type == "set-pos":
            catapult.set_pos((int(value)-100)/100)
            return True

        elif type == "fire":
            if value == "true":
                catapult.firing = True
                return True
            else:
                print("Boolean expected with fire position request not: '" + value + "'")
                return False

        elif type == "firing":
            if value == "true":
                catapult.firing_enabled = True
                return True
            elif value == "false":
                catapult.firing_enabled = False
                return True
            else:
                print("Boolean expected with firing request not: '" + value + "'")
                return False

        elif type == "tracking":
            if value == "true":
                catapult.tracking = True
                return True
            elif value == "false":
                catapult.tracking = False
                return True
            else:
                print("Boolean expected with tracking request not: '" + value + "'")
                return False
        else:
            print("Unkown post request with body: '" + data + "'")
            return False


    def log_message(self, format, *args):
        pass

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

with open(r"page_contents.html", "r") as f:  # get the html contents to display
    PAGE = f.read()

catapult = Catapult(17, 27, 22, x_invert=True)

with picamera.PiCamera(resolution=str(cam_resolution[0])+"x"+str(cam_resolution[1]), framerate=16) as camera:
    output = StreamingOutput()
    camera.rotation = 180
    camera.start_recording(output, format='mjpeg')
    try:
        print("Starting Server")
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()
