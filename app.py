import os
import sys
import shutil
import re
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yt_dlp
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import winreg
import ctypes
from ctypes import HRESULT, POINTER, c_void_p, c_int, c_ulonglong

# --- Taskbar Progress Integration ---
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]

CLSID_TaskbarList = GUID(0x56FDF344, 0xFD6D, 0x11D0, (ctypes.c_ubyte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90))
IID_ITaskbarList3 = GUID(0xEA1AFB91, 0x9C28, 0x4B86, (ctypes.c_ubyte * 8)(0xA6, 0xE9, 0x95, 0xC6, 0x4A, 0x0B, 0x7C, 0x6E))

class ITaskbarList3Vtbl(ctypes.Structure):
    pass

class ITaskbarList3(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(ITaskbarList3Vtbl))]

QueryInterface_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), POINTER(GUID), POINTER(c_void_p))
AddRef_Proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, POINTER(ITaskbarList3))
Release_Proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, POINTER(ITaskbarList3))
HrInit_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3))
AddTab_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p)
DeleteTab_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p)
ActivateTab_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p)
SetActiveAlt_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p)
MarkFullscreenWindow_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p, c_int)
SetProgressValue_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p, c_ulonglong, c_ulonglong)
SetProgressState_Proto = ctypes.WINFUNCTYPE(HRESULT, POINTER(ITaskbarList3), c_void_p, c_int)

ITaskbarList3Vtbl._fields_ = [
    ("QueryInterface", QueryInterface_Proto),
    ("AddRef", AddRef_Proto),
    ("Release", Release_Proto),
    ("HrInit", HrInit_Proto),
    ("AddTab", AddTab_Proto),
    ("DeleteTab", DeleteTab_Proto),
    ("ActivateTab", ActivateTab_Proto),
    ("SetActiveAlt", SetActiveAlt_Proto),
    ("MarkFullscreenWindow", MarkFullscreenWindow_Proto),
    ("SetProgressValue", SetProgressValue_Proto),
    ("SetProgressState", SetProgressState_Proto)
]

_taskbar = None

def init_taskbar():
    global _taskbar
    if _taskbar is not None:
        return _taskbar
    try:
        ctypes.windll.ole32.CoInitialize(None)
        tb = POINTER(ITaskbarList3)()
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_TaskbarList),
            None,
            1,
            ctypes.byref(IID_ITaskbarList3),
            ctypes.byref(tb)
        )
        if hr == 0:
            tb.contents.lpVtbl.contents.HrInit(tb)
            _taskbar = tb
            return _taskbar
    except Exception:
        pass
    return None

def set_taskbar_progress(hwnd, current, total):
    tb = init_taskbar()
    if tb and hwnd:
        try:
            tb.contents.lpVtbl.contents.SetProgressState(tb, hwnd, 2)  # Normal (Green)
            tb.contents.lpVtbl.contents.SetProgressValue(tb, hwnd, int(current), int(total))
        except Exception:
            pass

def set_taskbar_progress_state(hwnd, state):
    tb = init_taskbar()
    if tb and hwnd:
        try:
            tb.contents.lpVtbl.contents.SetProgressState(tb, hwnd, state)
        except Exception:
            pass


# --- Background HTTP Server for Chrome/Edge integration ---
class DownloadRequestHandler(BaseHTTPRequestHandler):
    app_ref = None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/download':
            query = urllib.parse.parse_qs(parsed.query)
            url_list = query.get('url')
            quality_list = query.get('quality')
            
            if url_list:
                url = url_list[0]
                quality = quality_list[0] if quality_list else "Best Quality (MP4)"
                
                if self.app_ref:
                    self.app_ref.trigger_remote_download(url, quality)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
                return
                
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b'{"status": "error", "message": "Invalid request"}')
        
    def log_message(self, format, *args):
        pass


# --- Helper to Locate local FFmpeg ---
def get_ffmpeg_path():
    # 1. Check in the current executable directory
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    local_ffmpeg = os.path.join(base_dir, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return os.path.normpath(local_ffmpeg)

    # 2. Check if ffmpeg is in system PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
        
    # 3. Check in winget packages directories under Local AppData
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        winget_pkgs = os.path.join(appdata, "Microsoft", "WinGet", "Packages")
        if os.path.exists(winget_pkgs):
            for root, dirs, files in os.walk(winget_pkgs):
                if "ffmpeg.exe" in files:
                    return os.path.normpath(os.path.join(root, "ffmpeg.exe"))

    # 4. Bundled binary from the imageio-ffmpeg package (pip install imageio-ffmpeg)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return os.path.normpath(exe)
    except Exception:
        pass

    return None


class DownloadCancelled(Exception):
    pass


class QuietLogger:
    """yt-dlp logger that swallows output (stdout/stderr are None in --noconsole builds)."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def clean_error(e):
    msg = ANSI_RE.sub('', str(e)).strip()
    msg = msg.split('\n')[0]
    if msg.startswith('ERROR:'):
        msg = msg[len('ERROR:'):].strip()
    return msg or "Unknown error"


def get_hwnd(widget):
    # winfo_id() is the inner child window; the taskbar needs the top-level window
    try:
        return ctypes.windll.user32.GetParent(widget.winfo_id()) or widget.winfo_id()
    except Exception:
        return widget.winfo_id()


# --- Scrollable Frame Helper for Multiple Downloads List ---
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, height=180)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        if self.scrollable_frame.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


# --- Download Progress Row Widget ---
class DownloadProgressRow(ttk.Frame):
    def __init__(self, parent, title, on_cancel_callback):
        super().__init__(parent, padding=5)
        
        self.title = title
        self.on_cancel_callback = on_cancel_callback
        self.should_cancel = False
        self.percent = 0
        self.files = set()
        self.title_set = False

        # Grid setup
        self.columnconfigure(0, weight=1)
        
        # Truncated title label
        display_title = title[:50] + "..." if len(title) > 53 else title
        self.title_label = ttk.Label(self, text=display_title, font=("Arial", 9, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(2, 2))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="we", columnspan=2, pady=(0, 2))
        
        # Stats & Cancel button row
        self.stats_label = ttk.Label(self, text="Fetching details...", font=("Arial", 8), wraplength=400, justify="left")
        self.stats_label.grid(row=2, column=0, sticky="w")
        
        self.cancel_btn = ttk.Button(self, text="Cancel", width=8, command=self.cancel)
        self.cancel_btn.grid(row=2, column=1, sticky="e")
        
        # Separator line
        self.sep = ttk.Separator(self, orient="horizontal")
        self.sep.grid(row=3, column=0, columnspan=2, sticky="we", pady=(6, 2))

    def update_progress(self, percent, stats_text):
        self.percent = percent
        self.progress_bar['value'] = percent
        self.stats_label.configure(text=stats_text)
        
    def cancel(self):
        self.should_cancel = True
        self.cancel_btn.configure(state="disabled")
        self.stats_label.configure(text="Cancelling...")
        if self.on_cancel_callback:
            self.on_cancel_callback()


# --- Main Application ---
class YoutubeDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("YouTubeDownloader - by mudassir developer")
        self.geometry("560x470")
        self.minsize(560, 470)

        # Set window icon safely
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_path, "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # Style sheet
        self.style = ttk.Style()
        self.style.theme_use('vista' if 'vista' in self.style.theme_names() else 'winnative')

        # Variables
        self.download_dir = tk.StringVar(value=os.path.join(os.path.expanduser('~'), 'Downloads'))
        self.quality_var = tk.StringVar(value="Best Quality (MP4)")
        
        # Thread -> UI call queue (Tkinter is not thread-safe)
        self.ui_queue = queue.Queue()

        # Multiple downloads tracking
        self.download_counter = 0
        self.active_downloads = {}

        self.create_widgets()

        # Startup auto-paste
        self.after(100, self.auto_paste_clipboard)

        self.after(50, self.process_ui_queue)

        # Start HTTP Server thread
        threading.Thread(target=self.start_http_server, daemon=True).start()

    def call_ui(self, fn, *args):
        self.ui_queue.put((fn, args))

    def process_ui_queue(self):
        try:
            while True:
                fn, args = self.ui_queue.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.after(50, self.process_ui_queue)

    def register_system_settings(self):
        # 1. Register custom youtubedownloader:// protocol
        try:
            exe_path = os.path.abspath(sys.argv[0])
            if not exe_path.endswith('.exe'):
                cmd_value = f'"{sys.executable}" "{exe_path}" "%1"'
            else:
                cmd_value = f'"{exe_path}" "%1"'

            key_path = r"Software\Classes\youtubedownloader"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "URL:YouTubeDownloader Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                
            cmd_key_path = r"Software\Classes\youtubedownloader\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, cmd_value)
            print("Protocol registered successfully.")
        except Exception as e:
            print(f"Error registering protocol: {e}")

        # 2. Register Chrome & Edge Extensions (External Extensions from Registry)
        try:
            ext_id = "pehlpehlpehlpehlpehlpehlpehlpehl"
            
            # Find extension path relative to script/exe
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                
            ext_dir = os.path.normpath(os.path.join(base_dir, 'extension'))
            if not os.path.exists(ext_dir):
                ext_dir = os.path.normpath(os.path.join(base_dir, '..', 'extension'))

            if os.path.exists(ext_dir):
                # Write Google Chrome Extension Registry Key
                chrome_key = fr"Software\Google\Chrome\Extensions\{ext_id}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chrome_key) as key:
                    winreg.SetValueEx(key, "path", 0, winreg.REG_SZ, ext_dir)
                    winreg.SetValueEx(key, "version", 0, winreg.REG_SZ, "1.0")
                print("Registered extension in Google Chrome.")

                # Write Microsoft Edge Extension Registry Key
                edge_key = fr"Software\Microsoft\Edge\Extensions\{ext_id}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, edge_key) as key:
                    winreg.SetValueEx(key, "path", 0, winreg.REG_SZ, ext_dir)
                    winreg.SetValueEx(key, "version", 0, winreg.REG_SZ, "1.0")
                print("Registered extension in Microsoft Edge.")
            else:
                print(f"Extension directory not found at: {ext_dir}")
        except Exception as e:
            print(f"Error registering browser extension: {e}")

    def start_http_server(self):
        try:
            DownloadRequestHandler.app_ref = self
            server_address = ('127.0.0.1', 30121)
            self.httpd = HTTPServer(server_address, DownloadRequestHandler)
            self.httpd.serve_forever()
        except Exception as e:
            print(f"Error starting local HTTP server: {e}")
            self.call_ui(
                messagebox.showwarning,
                "Browser integration unavailable",
                "Could not start the local server on port 30121 (another program may be using it).\n"
                "Downloads from the app window still work, but the browser extension buttons won't."
            )

    def trigger_remote_download(self, url, quality):
        self.call_ui(self.process_remote_download, url, quality)

    def process_remote_download(self, url, quality):
        # Focus window
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes('-topmost', True)
        self.after(1000, lambda: self.attributes('-topmost', False))
        
        # Set values
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, url)
        
        available_values = list(self.quality_menu['values'])
        if quality in available_values:
            self.quality_var.set(quality)
        else:
            matched = False
            for val in available_values:
                if quality.lower() in val.lower() or val.lower() in quality.lower():
                    self.quality_var.set(val)
                    matched = True
                    break
            if not matched:
                self.quality_var.set("Best Quality (MP4)")
                
        # Run download
        self.start_download()

    def create_widgets(self):
        # Main top configuration panel
        config_frame = ttk.Frame(self, padding="15")
        config_frame.pack(fill="x")

        # 1. URL Row
        url_label = ttk.Label(config_frame, text="YouTube URL:")
        url_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.url_entry = ttk.Entry(config_frame, width=55)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 10))

        paste_btn = ttk.Button(config_frame, text="Paste", width=8, command=self.paste_url)
        paste_btn.grid(row=1, column=2, padx=(5, 0), pady=(0, 10))

        # 2. Quality Dropdown
        quality_label = ttk.Label(config_frame, text="Quality / Format:")
        quality_label.grid(row=2, column=0, sticky="w", pady=(0, 5))

        self.quality_menu = ttk.Combobox(
            config_frame, 
            textvariable=self.quality_var, 
            values=[
                "Best Quality (MP4)", 
                "Best Quality (MOV)", 
                "1080p (MP4)", 
                "720p (MP4)", 
                "Audio Only (MP3)"
            ],
            state="readonly",
            width=25
        )
        self.quality_menu.grid(row=3, column=0, sticky="w", pady=(0, 10))

        # 3. Output Folder Path
        path_label = ttk.Label(config_frame, text="Save Location:")
        path_label.grid(row=4, column=0, sticky="w", pady=(0, 5))

        self.path_entry = ttk.Entry(config_frame, textvariable=self.download_dir, width=40)
        self.path_entry.grid(row=5, column=0, columnspan=2, sticky="we", pady=(0, 10))

        browse_btn = ttk.Button(config_frame, text="Browse...", width=10, command=self.browse_folder)
        browse_btn.grid(row=5, column=2, padx=(5, 0), pady=(0, 10))

        # 4. Action triggers
        action_btn_frame = ttk.Frame(config_frame)
        action_btn_frame.grid(row=6, column=0, columnspan=3, sticky="we", pady=(10, 0))

        open_folder_btn = ttk.Button(action_btn_frame, text="Open Downloads Folder", command=self.open_downloads_folder)
        open_folder_btn.pack(side="left")

        self.download_btn = ttk.Button(action_btn_frame, text="Download Video", command=self.start_download)
        self.download_btn.pack(side="right")

        # Dynamic scrollable container area for multiple downloads progress rows
        divider = ttk.Separator(self, orient="horizontal")
        divider.pack(fill="x", padx=15, pady=(5, 5))
        
        lbl = ttk.Label(self, text="Active Downloads:", font=("Arial", 9, "bold"))
        lbl.pack(anchor="w", padx=15, pady=(2, 2))

        self.scroll_container = ScrollableFrame(self)
        self.scroll_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def paste_url(self):
        try:
            clipboard = self.clipboard_get().strip()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, clipboard)
        except tk.TclError:
            pass

    def auto_paste_clipboard(self):
        try:
            clipboard = self.clipboard_get().strip()
            if clipboard.startswith("http://") or clipboard.startswith("https://"):
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, clipboard)
        except Exception:
            pass

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_dir.get())
        if folder:
            self.download_dir.set(os.path.normpath(folder))

    def open_downloads_folder(self):
        folder = self.download_dir.get()
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showerror("Error", "The save directory does not exist yet.")

    def request_cancel(self, download_id):
        if download_id in self.active_downloads:
            row = self.active_downloads[download_id]
            row.should_cancel = True

    # --- Downloading Logic ---
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a YouTube video URL.")
            return

        outdir = self.download_dir.get().strip()
        if not os.path.exists(outdir):
            try:
                os.makedirs(outdir)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create output directory:\n{e}")
                return

        # Prepare new download ID & progress row
        self.download_counter += 1
        download_id = self.download_counter
        
        quality = self.quality_var.get()
        
        # Add dynamic row to the scrollable container frame
        row = DownloadProgressRow(self.scroll_container.scrollable_frame, f"Loading: {url[:30]}...", lambda: self.request_cancel(download_id))
        row.pack(fill="x", expand=True)
        self.active_downloads[download_id] = row
        
        # Clear URL field for convenience
        self.url_entry.delete(0, tk.END)
        
        # Start download thread
        threading.Thread(target=self.bg_download_thread, args=(download_id, url, outdir, quality, row), daemon=True).start()

    def bg_download_thread(self, download_id, url, outdir, quality, row):
        ydl_opts = {
            'outtmpl': os.path.join(outdir, '%(title)s.%(ext)s'),
            'progress_hooks': [lambda d: self.yt_progress_hook(d, row)],
            'logger': QuietLogger(),
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'noplaylist': True,
            'windowsfilenames': True,
            'retries': 10,
            'fragment_retries': 10,
            'extractor_retries': 3,
            'concurrent_fragment_downloads': 4,
            'rm_cache_dir': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }

        # Auto-configure FFmpeg location
        ffmpeg_bin = get_ffmpeg_path()
        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = ffmpeg_bin

        try:
            if not ffmpeg_bin and quality == "Audio Only (MP3)":
                raise Exception("FFmpeg not found - it is required for MP3 conversion")

            if not ffmpeg_bin:
                # Without FFmpeg streams can't be merged: fall back to single-file formats
                ydl_opts['format'] = 'b[height<=720][ext=mp4]/b[height<=720]/b'
            elif quality == "Best Quality (MP4)":
                # Highest resolution available, preferring MP4/M4A-compatible streams
                ydl_opts['format'] = 'bv*+ba/b'
                ydl_opts['format_sort'] = ['res', 'ext:mp4:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
            elif quality == "Best Quality (MOV)":
                # H.264/AAC keeps MOV files widely playable
                ydl_opts['format'] = 'bv*[vcodec^=avc]+ba[ext=m4a]/bv*+ba/b'
                ydl_opts['format_sort'] = ['res', 'vcodec:h264', 'acodec:aac']
                ydl_opts['merge_output_format'] = 'mov'
            elif quality == "1080p (MP4)":
                ydl_opts['format'] = 'bv*[height<=1080]+ba/b[height<=1080]/b'
                ydl_opts['format_sort'] = ['res', 'ext:mp4:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
            elif quality == "720p (MP4)":
                ydl_opts['format'] = 'bv*[height<=720]+ba/b[height<=720]/b'
                ydl_opts['format_sort'] = ['res', 'ext:mp4:m4a']
                ydl_opts['merge_output_format'] = 'mp4'
            elif quality == "Audio Only (MP3)":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)
            except Exception as first_err:
                # Merging unavailable (broken/missing FFmpeg): retry with a single-file format
                if 'merg' in str(first_err).lower() and quality != "Audio Only (MP3)" and not row.should_cancel:
                    for key in ('format_sort', 'merge_output_format'):
                        ydl_opts.pop(key, None)
                    ydl_opts['format'] = 'b[height<=720][ext=mp4]/b[height<=720]/b'
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(url, download=True)
                else:
                    raise

            if row.should_cancel:
                raise DownloadCancelled()

            self.call_ui(self.on_download_row_success, download_id, row)
        except Exception as e:
            if row.should_cancel or isinstance(e, DownloadCancelled):
                self.cleanup_partial_files(row)
                self.call_ui(self.on_download_row_error, download_id, row, "CANCEL_SIGNAL")
            else:
                self.call_ui(self.on_download_row_error, download_id, row, clean_error(e))

    def cleanup_partial_files(self, row):
        for path in list(row.files):
            for suffix in (".part", ".ytdl"):
                try:
                    f = path + suffix
                    if os.path.isfile(f):
                        os.remove(f)
                except OSError:
                    pass
            if path.endswith(".part") and os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def update_row_title(self, row, title):
        display_title = title[:50] + "..." if len(title) > 53 else title
        row.title_label.configure(text=display_title)

    def yt_progress_hook(self, d, row):
        if row.should_cancel:
            raise DownloadCancelled()

        filename = d.get('filename') or d.get('tmpfilename')
        if filename:
            row.files.add(filename)

        if not row.title_set:
            title = (d.get('info_dict') or {}).get('title')
            if title:
                row.title_set = True
                self.call_ui(self.update_row_title, row, title)

        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes') or 0
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0

            percent = 0.0
            if total > 0:
                percent = min(downloaded / total, 1.0)

            # Format speed
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"

            # Format ETA
            if eta:
                mins, secs = divmod(int(eta), 60)
                eta_str = f"{mins:02d}:{secs:02d}"
            else:
                eta_str = "--:--"

            percent_display = int(percent * 100)
            stats_text = f"{percent_display}% • {speed_str} • {eta_str}"

            self.call_ui(self.update_row_progress_ui, row, percent_display, stats_text)

        elif d['status'] == 'finished':
            self.call_ui(self.update_row_progress_ui, row, 100, "Processing...")

    def update_row_progress_ui(self, row, percent, stats_text):
        row.update_progress(percent, stats_text)
        self.update_taskbar_overall()

    def update_taskbar_overall(self):
        if not self.active_downloads:
            set_taskbar_progress_state(get_hwnd(self), 0) # Clear
            return
            
        total_percent = sum(row.percent for row in self.active_downloads.values())
        avg_percent = total_percent / len(self.active_downloads)
        
        set_taskbar_progress(get_hwnd(self), int(avg_percent), 100)

    def on_download_row_success(self, download_id, row):
        row.update_progress(100, "Completed!")
        row.cancel_btn.configure(text="Dismiss", command=lambda: self.dismiss_row(download_id, row), state="normal")
        
        # Remove from active list to exclude from average taskbar calculations
        if download_id in self.active_downloads:
            del self.active_downloads[download_id]
        self.update_taskbar_overall()

    def on_download_row_error(self, download_id, row, err_msg):
        if err_msg == "CANCEL_SIGNAL":
            row.update_progress(0, "Cancelled")
        else:
            row.update_progress(0, f"Error: {err_msg[:150]}")
            
        row.cancel_btn.configure(text="Dismiss", command=lambda: self.dismiss_row(download_id, row), state="normal")
        
        if download_id in self.active_downloads:
            del self.active_downloads[download_id]
        self.update_taskbar_overall()

    def dismiss_row(self, download_id, row):
        # Destroy and remove progress widget
        row.pack_forget()
        row.destroy()
        if download_id in self.active_downloads:
            del self.active_downloads[download_id]
        self.update_taskbar_overall()


# --- Single Instance Handler Functions ---
def check_single_instance_and_send(url, quality):
    import urllib.request
    import urllib.parse
    try:
        req_url = f"http://127.0.0.1:30121/download?url={urllib.parse.quote(url)}&quality={urllib.parse.quote(quality)}"
        with urllib.request.urlopen(req_url, timeout=2) as response:
            if response.status == 200:
                return True
    except Exception:
        pass
    return False

def parse_protocol_args(arg):
    # Tolerates variants like youtubedownloader://download?url=..., youtubedownloader://download/?url=...
    try:
        arg = arg.strip().strip('"')
        if arg.lower().startswith("youtubedownloader:"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(arg).query)
            url = (query.get('url') or [None])[0]
            quality = (query.get('quality') or [None])[0]
            return url, quality
    except Exception:
        pass
    return None, None


if __name__ == "__main__":
    url_to_download = None
    quality_to_download = None
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        url, quality = parse_protocol_args(arg)
        if url:
            if check_single_instance_and_send(url, quality or "Best Quality (MP4)"):
                sys.exit(0)
            else:
                url_to_download = url
                quality_to_download = quality

    app = YoutubeDownloaderApp()
    
    # Run auto-registration check
    app.register_system_settings()
    
    if url_to_download:
        app.after(1500, lambda: app.process_remote_download(url_to_download, quality_to_download or "Best Quality (MP4)"))
        
    app.mainloop()