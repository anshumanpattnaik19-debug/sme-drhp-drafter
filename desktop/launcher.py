"""DRHP Studio desktop launcher: starts the app on this computer and opens it in the browser.

Everything runs locally: the API, the UI, OCR and the rule-based extraction. Issuer files and project data stay in
the user's data folder (LOCALAPPDATA/DRHP Studio/workspace). The drafting model is optional: set a local
OpenAI-compatible server in Settings (the app works without one, using the offline drafter).
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORT = int(os.environ.get("DRHP_PORT", "8765"))


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "DRHP Studio"
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return root


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    root = data_dir()
    os.environ.setdefault("DRHP_WORKSPACE", str(root / "workspace"))
    os.environ.setdefault("DRHP_UI_DIST", str(base_dir() / "ui" / "dist"))
    if not port_free(PORT):
        # the app is already running: just open it
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
        return
    import uvicorn

    from serve.app import app

    def open_browser() -> None:
        for _ in range(60):
            if not port_free(PORT):
                break
            time.sleep(0.25)
        webbrowser.open(f"http://127.0.0.1:{PORT}/")

    threading.Thread(target=open_browser, daemon=True).start()
    log_cfg = None
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_config=log_cfg, log_level="warning")


if __name__ == "__main__":
    main()
