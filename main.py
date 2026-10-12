import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime

HOST = "localhost"
PORT = 8000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOMS_FILE = os.path.join(BASE_DIR, "rooms.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")


def load_rooms() -> dict:
    if os.path.exists(ROOMS_FILE):
        with open(ROOMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_rooms(rooms: dict) -> None:
    with open(ROOMS_FILE, "w", encoding="utf-8") as f:
        json.dump(rooms, f, indent=4)


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def save_history(history: list) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)


class RoomTrackerHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {self.address_string()} {format % args}")

    def send_file(self, file_path: str, content_type: str):
        if not os.path.isfile(file_path):
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            data = f.read()
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(data)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def send_json(self, data: dict | list, status: int = 200):
        try:
            encoded = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/index.html":
            index_path = os.path.join(BASE_DIR, "templates", "index.html")
            self.send_file(index_path, "text/html; charset=utf-8")

        elif path == "/rooms" or path == "/rooms.html":
            rooms_path = os.path.join(BASE_DIR, "templates", "rooms.html")
            self.send_file(rooms_path, "text/html; charset=utf-8")

        elif path == "/static/style.css":
            css_path = os.path.join(BASE_DIR, "static", "style.css")
            self.send_file(css_path, "text/css")

        elif path == "/api/rooms":
            rooms = load_rooms()
            self.send_json(rooms)

        elif path == "/api/history":
            history = load_history()
            self.send_json(history)

        elif path == "/history.json":
            self.send_file(HISTORY_FILE, "application/json")

        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/occupy":
            body = self.read_json_body()
            room_name = body.get("room")
            instructor = body.get("instructor", "Unknown").strip()
            subject = body.get("subject", "Unknown").strip()

            if not room_name:
                self.send_json({"error": "Missing room name"}, 400)
                return

            rooms = load_rooms()
            if room_name not in rooms:
                self.send_json({"error": "Room not found"}, 404)
                return

            if rooms[room_name].get("status") == "OCCUPIED":
                self.send_json({"error": "Room is already occupied"}, 400)
                return

            
            if instructor and instructor.lower() != "unknown":
                for r_name, r_info in rooms.items():
                    if r_info.get("status") == "OCCUPIED":
                        existing_inst = r_info.get("instructor", "").strip().lower()
                        if existing_inst == instructor.lower():
                            self.send_json({
                                "error": f"Instructor '{r_info.get('instructor')}' is already occupying {r_name}. An instructor can only occupy 1 room at a time. Please vacate it first."
                            }, 400)
                            return

            timestamp_str = datetime.now().strftime("%I:%M %p")

            rooms[room_name]["status"] = "OCCUPIED"
            rooms[room_name]["instructor"] = instructor
            rooms[room_name]["subject"] = subject
            rooms[room_name]["time_in"] = timestamp_str
            save_rooms(rooms)

            self.send_json({"success": True, "rooms": rooms})

        elif path == "/api/vacate":
            body = self.read_json_body()
            room_name = body.get("room")

            if not room_name:
                self.send_json({"error": "Missing room name"}, 400)
                return

            rooms = load_rooms()
            if room_name not in rooms:
                self.send_json({"error": "Room not found"}, 404)
                return

            
            prev_occupant = rooms[room_name].get("instructor")
            if rooms[room_name].get("status") == "OCCUPIED" and prev_occupant and prev_occupant != "None":
                time_out_str = datetime.now().strftime("%I:%M %p")
                date_str = datetime.now().strftime("%Y-%m-%d")
                history_entry = {
                    "room": room_name,
                    "instructor": prev_occupant,
                    "subject": rooms[room_name].get("subject", "None"),
                    "time_in": rooms[room_name].get("time_in", "None"),
                    "time_out": time_out_str,
                    "date": date_str
                }
                history = load_history()
                history.insert(0, history_entry)
                save_history(history)

           
            rooms[room_name]["status"] = "VACANT"
            rooms[room_name]["instructor"] = "None"
            rooms[room_name]["subject"] = "None"
            rooms[room_name]["time_in"] = "None"
            save_rooms(rooms)

            self.send_json({"success": True, "rooms": rooms})

        else:
            self.send_error(404, "Endpoint Not Found")


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), RoomTrackerHandler)
    print("=" * 60)
    print("  UNIVERSITY ROOM TRACKER")
    print("=" * 60)
    print(f"  Backend Brain running at http://{HOST}:{PORT}")
    print("  Serving templates & static files")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
