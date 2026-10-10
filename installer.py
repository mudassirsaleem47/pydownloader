import os
import sys
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import winreg
import ctypes
import subprocess


def get_desktop_dir():
    # Works with OneDrive-redirected and localized Desktop folders
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def run_uninstall():
    # Create background Tk window for dialogs
    root = tk.Tk()
    root.withdraw()
    confirm = messagebox.askyesno(
        "Uninstall YouTubeDownloader", 
        "Are you sure you want to completely remove YouTubeDownloader and all of its components?"
    )
    if not confirm:
        sys.exit(0)
        
    try:
        # 1. Delete Custom Protocol Registry Keys
        for subkey in [
            r"Software\Classes\youtubedownloader\shell\open\command",
            r"Software\Classes\youtubedownloader\shell\open",
            r"Software\Classes\youtubedownloader\shell",
            r"Software\Classes\youtubedownloader"
        ]:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
            except Exception:
                pass
            
        # 2. Delete Chrome Extension Keys
        try:
            ext_id = "pehlpehlpehlpehlpehlpehlpehlpehl"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, fr"Software\Google\Chrome\Extensions\{ext_id}")
        except Exception:
            pass
            
        # 3. Delete Edge Extension Keys
        try:
            ext_id = "pehlpehlpehlpehlpehlpehlpehlpehl"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, fr"Software\Microsoft\Edge\Extensions\{ext_id}")
        except Exception:
            pass
            
        # 4. Delete Windows Uninstall Keys
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeDownloader")
        except Exception:
            pass
            
        # 5. Delete Desktop Shortcut
        try:
            shortcut_path = os.path.join(get_desktop_dir(), "YouTubeDownloader.lnk")
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
        except Exception:
            pass
            
        # Get target installation directory from current setup path
        dest_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        messagebox.showinfo("Uninstall Complete", "YouTubeDownloader has been successfully removed from your computer.")
        
        # Self-deletion batch: removes only our own files, never the whole folder
        batch_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "uninstall_cleanup.bat")
        with open(batch_path, "w") as f:
            f.write("@echo off\n")
            f.write("ping 127.0.0.1 -n 3 > nul\n")
            for name in ["youtubedownloader.exe", "youtubedownloader_setup.exe",
                         "ffmpeg.exe", "ffprobe.exe", "icon.ico"]:
                f.write(f'del /f /q "{os.path.join(dest_dir, name)}"\n')
            f.write(f'rmdir /s /q "{os.path.join(dest_dir, "extension")}"\n')
            f.write(f'rmdir "{dest_dir}"\n')  # only succeeds if the folder is now empty
            f.write('del "%~f0"\n')

        subprocess.Popen(["cmd.exe", "/c", batch_path], creationflags=subprocess.CREATE_NO_WINDOW)

    except Exception as e:
        messagebox.showerror("Error", f"Uninstall failed:\n{e}")
    sys.exit(0)


def find_browser(name):
    """Return the path of chrome.exe / msedge.exe from the App Paths registry, or None."""
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{name}") as key:
                path = winreg.QueryValue(key, None)
                if path and os.path.exists(path):
                    return path
        except OSError:
            pass
    return None


def open_extension_setup(ext_dir):
    """Open the browser's extensions page and the extension folder for a one-time 'Load unpacked'."""
    browser = find_browser("chrome.exe")
    page = "chrome://extensions"
    if not browser:
        browser = find_browser("msedge.exe")
        page = "edge://extensions"
    if browser:
        subprocess.Popen([browser, page])
    os.startfile(ext_dir)


class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTubeDownloader Setup")
        self.geometry("450x260")
        self.resizable(False, False)

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
        
        # Default destination path
        default_dir = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "Programs", "YouTubeDownloader")
        self.dest_dir = tk.StringVar(value=default_dir)
        
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        title_lbl = ttk.Label(main_frame, text="YouTubeDownloader Setup Wizard", font=("Arial", 14, "bold"))
        title_lbl.pack(anchor="w", pady=(0, 10))
        
        desc_lbl = ttk.Label(main_frame, text="This will install YouTubeDownloader and register the browser extension.\nChoose the installation directory:", justify="left")
        desc_lbl.pack(anchor="w", pady=(0, 15))
        
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill="x", pady=(0, 15))
        
        self.path_entry = ttk.Entry(path_frame, textvariable=self.dest_dir, width=40)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        browse_btn = ttk.Button(path_frame, text="Browse...", command=self.browse_dest)
        browse_btn.pack(side="right")
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side="bottom")
        
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        self.cancel_btn.pack(side="left")
        
        self.install_btn = ttk.Button(btn_frame, text="Install", command=self.run_installation)
        self.install_btn.pack(side="right")

    def browse_dest(self):
        folder = filedialog.askdirectory(initialdir=self.dest_dir.get())
        if folder:
            self.dest_dir.set(os.path.normpath(folder))

    def run_installation(self):
        dest = self.dest_dir.get().strip()
        if not dest:
            return
            
        self.install_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self.path_entry.configure(state="disabled")
        
        try:
            # 1. Get source directory
            source_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            exe_src = os.path.join(source_dir, "youtubedownloader.exe")
            ext_src = os.path.join(source_dir, "extension")
            icon_src = os.path.join(source_dir, "icon.ico")
            ffmpeg_src = os.path.join(source_dir, "ffmpeg.exe")
            ffprobe_src = os.path.join(source_dir, "ffprobe.exe")
            
            # Fallback for local testing
            if not os.path.exists(exe_src):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                exe_src = os.path.join(base_dir, "dist", "youtubedownloader.exe")
                ext_src = os.path.join(base_dir, "extension")
                icon_src = os.path.join(base_dir, "icon.ico")
                ffmpeg_src = os.path.join(base_dir, "ffmpeg.exe")
                ffprobe_src = os.path.join(base_dir, "ffprobe.exe")
            
            if not os.path.exists(exe_src):
                raise FileNotFoundError(f"Could not locate youtubedownloader.exe (looked at {exe_src}).")
                
            # Create destination folder
            os.makedirs(dest, exist_ok=True)
            
            # 2. Copy main executable
            exe_dest = os.path.join(dest, "youtubedownloader.exe")
            shutil.copy2(exe_src, exe_dest)
            
            # Copy FFmpeg and FFprobe binaries if present
            if os.path.exists(ffmpeg_src):
                shutil.copy2(ffmpeg_src, os.path.join(dest, "ffmpeg.exe"))
            if os.path.exists(ffprobe_src):
                shutil.copy2(ffprobe_src, os.path.join(dest, "ffprobe.exe"))
            
            # 3. Copy extension folder
            ext_dest = os.path.join(dest, "extension")
            if os.path.exists(ext_dest):
                shutil.rmtree(ext_dest)
            shutil.copytree(ext_src, ext_dest)
            
            # Copy icon file
            if os.path.exists(icon_src):
                shutil.copy2(icon_src, os.path.join(dest, "icon.ico"))
                
            # Copy setup installer itself for uninstall support
            setup_src = sys.executable
            if setup_src.endswith(".exe") and "python" not in os.path.basename(setup_src).lower():
                setup_dest = os.path.join(dest, "youtubedownloader_setup.exe")
                shutil.copy2(setup_src, setup_dest)
            
            # 4. Write Registry Entries
            # Custom protocol
            key_path = r"Software\Classes\youtubedownloader"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "URL:YouTubeDownloader Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                
            cmd_key_path = r"Software\Classes\youtubedownloader\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_dest}" "%1"')
                
            # Chrome Extension
            ext_id = "pehlpehlpehlpehlpehlpehlpehlpehl"
            chrome_key_path = fr"Software\Google\Chrome\Extensions\{ext_id}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chrome_key_path) as key:
                winreg.SetValueEx(key, "path", 0, winreg.REG_SZ, ext_dest)
                winreg.SetValueEx(key, "version", 0, winreg.REG_SZ, "1.0")
                
            # Edge Extension
            edge_key_path = fr"Software\Microsoft\Edge\Extensions\{ext_id}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, edge_key_path) as key:
                winreg.SetValueEx(key, "path", 0, winreg.REG_SZ, ext_dest)
                winreg.SetValueEx(key, "version", 0, winreg.REG_SZ, "1.0")
                
            # Add/Remove Programs registry registration entries
            uninstall_key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeDownloader"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_key_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "YouTubeDownloader")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{os.path.join(dest, "youtubedownloader_setup.exe")}" --uninstall')
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f'"{exe_dest}"')
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "mudassir developer")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0")
                
            # 5. Create Desktop shortcut
            self.create_shortcut(exe_dest)
            
            messagebox.showinfo("Success", "YouTubeDownloader installed successfully!")
            if messagebox.askyesno(
                "Browser extension",
                "Browsers don't allow silent extension installs, so one quick step is needed:\n\n"
                "1. Turn ON 'Developer mode' (top-right) on the extensions page that opens.\n"
                "2. Click 'Load unpacked' and select the 'extension' folder that opens next to it "
                "(or drag the folder onto the page).\n\n"
                "Open the extensions page now?"
            ):
                open_extension_setup(ext_dest)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Installation failed:\n{e}")
            self.install_btn.configure(state="normal")
            self.cancel_btn.configure(state="normal")
            self.path_entry.configure(state="normal")

    def create_shortcut(self, target_exe):
        try:
            shortcut_path = os.path.join(get_desktop_dir(), "YouTubeDownloader.lnk")
            vbs_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "create_shortcut.vbs")
            with open(vbs_path, "w", encoding="utf-16") as f:  # UTF-16 keeps non-ASCII paths intact
                f.write('Set oWS = WScript.CreateObject("WScript.Shell")\n')
                f.write(f'Set oLink = oWS.CreateShortcut("{shortcut_path}")\n')
                f.write(f'oLink.TargetPath = "{target_exe}"\n')
                f.write(f'oLink.WorkingDirectory = "{os.path.dirname(target_exe)}"\n')
                f.write(f'oLink.IconLocation = "{target_exe}"\n')
                f.write('oLink.Save\n')
            subprocess.run(["cscript", "//nologo", vbs_path], creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            os.remove(vbs_path)
        except Exception:
            pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        run_uninstall()
    else:
        app = SetupWizard()
        app.mainloop()
