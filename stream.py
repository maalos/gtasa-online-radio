import http.server
import socketserver
import subprocess
import time
import os

# === CONFIGURATION ===
RADIO_DIR = "."  # directory containing MP3s
PORT = 8000
HOST = "0.0.0.0"

RADIO_FILES = {
    "BounceFM": "BounceFM.mp3",
    "CSR": "CSR.mp3",
    "KDST": "KDST.mp3",
    "KJAH": "KJAH.mp3",
    "KRose": "KRose.mp3",
    "MasterSounds": "MasterSounds.mp3",
    "PlaybackFM": "PlaybackFM.mp3",
    "RadioLosSantos": "RadioLosSantos.mp3",
    "RadioX": "RadioX.mp3",
    "SFUR": "SFUR.mp3",
}

# === PRECOMPUTE DURATIONS AND START TIMES ===
durations = {}
start_times = {}

print("Analyzing MP3 files...")
for name, filename in RADIO_FILES.items():
    path = os.path.join(RADIO_DIR, filename)
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        durations[name] = float(result.stdout.strip())
        start_times[name] = time.time()
        print(f"Loaded {name}: {durations[name]/60:.1f} min")
    except Exception as e:
        print(f"Failed to load {name}: {e}")
        durations[name] = 0.0
        start_times[name] = time.time()

# === STREAM GENERATOR ===
def generate_stream(station):
    file_path = os.path.join(RADIO_DIR, RADIO_FILES[station])
    duration = durations[station]

    while True:
        elapsed = (time.time() - start_times[station]) % duration

        cmd = [
            "ffmpeg",
            "-ss", str(elapsed),
            "-i", file_path,
            "-vn",
            "-map", "0:a:0",
            "-f", "mp3",
            "-"
        ]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        except GeneratorExit:
            break
        finally:
            if proc.poll() is None:
                proc.terminate()
                time.sleep(0.1)
                if proc.poll() is None:
                    proc.kill()
            if proc.stdout:
                proc.stdout.close()

# === HTTP HANDLER ===
class RadioHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        station = self.path.strip('/')

        if not station or station not in RADIO_FILES:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'<html><head><title>GTA SA Radio</title></head><body>')
            self.wfile.write(b'<h1>GTA San Andreas Radio Stations</h1><ul>')
            for s in RADIO_FILES:
                url = '/' + s
                self.wfile.write(('<li><a href="' + url + '">' + s + '</a></li>').encode('ascii', 'ignore'))
            self.wfile.write(b'</ul></body></html>')
            return

        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        print('Client connected to', station)
        try:
            for chunk in generate_stream(station):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print('Client disconnected from', station)
        finally:
            del chunk

# === RUN SERVER ===
with socketserver.ThreadingTCPServer((HOST, PORT), RadioHandler) as httpd:
    print('Starting GTA SA radio server on http://{}:{}/'.format(HOST, PORT))
    print('Stations:')
    for name in RADIO_FILES:
        print('  - http://{}:{}/{}'.format(HOST, PORT, name))
    httpd.serve_forever()