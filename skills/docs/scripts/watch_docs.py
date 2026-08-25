# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import time
import subprocess
import threading
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
import socketserver

# Global state to manage live reload signaling
reload_event = threading.Event()
watch_dir = "./docs"
compile_script_path = os.path.join(os.path.dirname(__file__), "compile_docs.py")

# ==============================================================================
# Live-Reload Request Handler
# ==============================================================================

class LiveReloadHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the watch_dir instead of active cwd
        super().__init__(*args, directory=watch_dir, **kwargs)

    def do_GET(self):
        # Expose live reload signal endpoint
        if self.path == "/live-reload":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            
            # Long-poll waiting for reload_event to be set (up to 15 seconds)
            reload_triggered = reload_event.wait(timeout=15.0)
            
            response = {"reload": reload_triggered}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return
            
        return super().do_GET()

# ==============================================================================
# File Watcher Thread
# ==============================================================================

def run_watcher():
    print(f"Monitoring folder: {watch_dir} for edits...")
    
    # Store initial modification times
    mtimes = {}
    
    # Initial compilation run to make sure everything is up to date on start
    print("Running initial compilation...")
    subprocess.run([sys.executable, compile_script_path, "--dir", watch_dir, "--watch"])

    while True:
        try:
            time.sleep(1.0)
            
            # Check for edits or additions
            changed = False
            if os.path.exists(watch_dir):
                for filename in os.listdir(watch_dir):
                    if filename.endswith(".md"):
                        full_path = os.path.join(watch_dir, filename)
                        mtime = os.path.getmtime(full_path)
                        
                        if full_path not in mtimes:
                            mtimes[full_path] = mtime
                            changed = True
                        elif mtimes[full_path] < mtime:
                            mtimes[full_path] = mtime
                            changed = True
            
            if changed:
                print(f"[{time.strftime('%H:%M:%S')}] Edit detected in markdown files. Re-compiling...")
                # Re-run compiler with watch flag set (to inject checkReload JS snippet)
                subprocess.run([sys.executable, compile_script_path, "--dir", watch_dir, "--watch"])
                
                # Signal reload_event to release long polls
                reload_event.set()
                # Briefly sleep to allow endpoints to consume the event, then clear
                time.sleep(0.5)
                reload_event.clear()
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in watcher thread: {e}")

# ==============================================================================
# Main Bootstrapper
# ==============================================================================

def main():
    global watch_dir
    
    # Parse watch directory argument if any
    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]):
            watch_dir = sys.argv[1]
        else:
            print(f"Warning: Directory '{sys.argv[1]}' not found. Defaulting to: {watch_dir}")
            
    os.makedirs(watch_dir, exist_ok=True)
    watch_dir = os.path.abspath(watch_dir)

    # Start watcher thread
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()

    # Launch local HTTP Server
    PORT = 8000
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer(("", PORT), LiveReloadHTTPHandler) as httpd:
            print(f"\n=========================================================")
            print(f"  Live Documentation server launched at: http://localhost:{PORT}")
            print(f"  Modify your docs/*.md files to auto-compile and refresh.")
            print(f"  Press Ctrl+C to terminate.")
            print(f"=========================================================\n")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        sys.exit(0)
    except Exception as e:
        print(f"Server crash error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
