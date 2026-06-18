import os
import sys
import threading
import time
import webbrowser
import requests
from pathlib import Path

MODEL_CONFIG = {
    "text": {
        "filename": "gemma-2-2b-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "size_mb": 1500,
    },
    "vision": {
        "filename": "moondream2-int4.gguf",
        "url": "https://huggingface.co/vikhyatk/moondream2-GGUF/resolve/main/moondream2-int4.gguf",
        "size_mb": 1800,
    },
    "vision_proj": {
        "filename": "mmproj-model-f16.gguf",
        "url": "https://huggingface.co/vikhyatk/moondream2-GGUF/resolve/main/mmproj-model-f16.gguf",
        "size_mb": 400,
    }
}

APP_PORT = 7860
BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).parent.resolve()))
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)


def download_file(url, dest, progress_cb, stop_event):
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if stop_event.is_set():
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            progress_cb(downloaded / total * 100)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def run_model_downloader_gui(missing_models):
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("ERROR: Tkinter not found.")
        sys.exit(1)
    root = tk.Tk()
    root.title("DocIntel - First Time Setup")
    root.geometry("580x400")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')
    ttk.Label(root, text="DocIntel: Model Download Required",
              font=("Segoe UI", 14, "bold")).pack(pady=(20, 5))
    ttk.Label(root, text="Runs 100% locally. Downloads ~3.7GB AI models once.",
              wraplength=520, justify="center").pack(pady=(0, 15))
    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="x")
    pv = tk.DoubleVar()
    ttk.Progressbar(frm, variable=pv, maximum=100, length=500).pack(fill="x", pady=5)
    lbl = ttk.Label(frm, text="Initializing...", font=("Segoe UI", 9))
    lbl.pack(anchor="w")
    bf = ttk.Frame(root)
    bf.pack(pady=20)
    stop_event = threading.Event()

    def upd(key, pct):
        root.after(0, lambda: [pv.set(pct), lbl.config(text=f"Downloading: {key} ({pct:.1f}%)")])

    def worker():
        total = sum(MODEL_CONFIG[k]['size_mb'] for k in missing_models)
        dt = 0
        for key in missing_models:
            if stop_event.is_set():
                break
            cfg = MODEL_CONFIG[key]
            dest = MODELS_DIR / cfg['filename']
            if dest.exists():
                dest.unlink()
            def prog(p, k=key, d=dt):
                upd(k, ((d + cfg['size_mb'] * (p / 100)) / total) * 100)
            if not download_file(cfg['url'], dest, prog, stop_event):
                root.after(0, lambda: lbl.config(text="Failed"))
                return
            dt += cfg['size_mb']
        root.after(0, done)

    def done():
        pv.set(100)
        lbl.config(text="All Models Ready!")
        btn.config(text="Launch",
                   command=lambda: [root.destroy(), start_backend_and_ui()],
                   state="normal")

    def cancel():
        stop_event.set()
        sys.exit(0)

    btn = ttk.Button(bf, text="Cancel", command=cancel)
    btn.pack()
    threading.Thread(target=worker, daemon=True).start()
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()


def start_backend_and_ui():
    import main
    t = threading.Thread(
        target=lambda: main.demo.launch(
            server_name="127.0.0.1",
            server_port=APP_PORT,
            prevent_thread_lock=True,
            show_api=False,
            quiet=True,
        ), daemon=True)
    t.start()
    url = f"http://127.0.0.1:{APP_PORT}"
    for _ in range(30):
        try:
            requests.get(url, timeout=0.5)
            break
        except Exception:
            time.sleep(1)
    else:
        print("ERROR: Backend failed to start.")
        sys.exit(1)
    webbrowser.open(url)
    print(f"DocIntel running at {url}. Press Ctrl+C to exit.")
    try:
        while t.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        sys.exit(0)


def check_models():
    return [k for k, v in MODEL_CONFIG.items()
            if not (MODELS_DIR / v['filename']).exists()]


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    missing = check_models()
    if missing:
        run_model_downloader_gui(missing)
    else:
        start_backend_and_ui()
