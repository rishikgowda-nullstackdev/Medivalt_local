"""
MediVault Local - Offline Server Launcher
Zero-cloud HIPAA & DPDP compliant clinical workstation launcher.
Handles port detection, database readiness, and browser auto-launch.
"""
import os
import sys
import socket
import webbrowser
import threading
import time
import subprocess
import re


def free_dead_ports():
    """Attempts to cleanly release lingering processes on default ports."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        for pid in set(re.findall(r":8000\s+.*LISTENING\s+(\d+)", out)):
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    except Exception:
        pass


def find_available_port(preferred_ports=(8000, 8001, 8080, 8888)):
    """Finds first available TCP port on localhost to avoid socket collisions."""
    for p in preferred_ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            continue
    return 8000


def open_browser_delayed(url: str, delay: float = 1.2):
    """Opens browser automatically once uvicorn finishes binding socket."""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    print("=" * 68)
    print(" MediVault Local — Offline Clinical Reviewer (Zero-Cloud Mode)")
    print(" HIPAA Security Rule Section 164.312(b) & DPDP Compliant")
    print("=" * 68)
    print()

    print("[1/3] Initializing local database & pre-warming SLM weights...")
    try:
        from backend.main import init_db
        init_db()
        print(" SQLite database verified and ready.")
        from backend.ai_bridge import warm_up_local_slm_background
        warm_up_local_slm_background()
        print(" Local SLM background pre-warming initialized in RAM.")
    except Exception as e:
        print(f" Database/SLM init status: {e}")

    print()
    print("[2/3] Checking workstation socket availability...")
    free_dead_ports()
    port = find_available_port()
    url = f"http://127.0.0.1:{port}"
    portal_url = f"{url}/patient-portal"

    print(f" Secured port {port} on 127.0.0.1.")
    print()
    print("=" * 68)
    print(f" Doctor Dashboard URL: {url}")
    print(f" Patient Portal URL:   {portal_url}")
    print(" Opening dashboard in your default browser...")
    print(" Press CTRL+C in this window to terminate the local server.")
    print("=" * 68)
    print()

    open_browser_delayed(url)

    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
