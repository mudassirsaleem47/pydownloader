# YouTubeDownloader

A lightweight, premium, and fully standalone Windows desktop application for downloading YouTube videos, featuring a traditional Windows native theme. It includes a native **Chrome/Edge browser extension** that integrates a download overlay directly into the YouTube video player, supporting automatic background launching, multiple concurrent downloads, and Windows taskbar progress overlays.

Developed by **mudassir developer**.

---

## Key Features

- **Traditional Windows UI**: Clean, native Tkinter layout styled to look like a traditional Windows desktop application.
- **Multiple Concurrent Downloads**: Download multiple videos at the same time. Each active download has its own row in a scrollable panel with speed, ETA, and a dedicated **Cancel** button.
- **Windows Taskbar Progress**: Displays a green progress bar directly on the application's taskbar icon, showing the average progress of all active downloads.
- **In-Player Browser Integration**: Adds a sleek overlay (`[ Download: MP4 | MOV | MP3 ]`) to the top-right corner of the YouTube video player that auto-fades with the native player controls.
- **Auto-Launch via Protocol**: Clicking a format in the browser launches the YouTubeDownloader application in the background (using the `youtubedownloader://` custom protocol handler) if it isn't already running.
- **Single-Instance Enforcement**: If the app is already open, new browser requests are forwarded to the active window instead of opening duplicate windows.
- **FFmpeg Bundled**: The setup installer automatically packs `ffmpeg.exe` and `ffprobe.exe` inside the installation folder so the app is completely self-contained on any PC.
- **Windows Apps & Features Integration**: Standard installation registry setup that lists **YouTubeDownloader** in Windows "Installed Programs" with full uninstall support.

---

## Installation & Usage

### 1. Installation
1. Locate **`youtubedownloader_setup.exe`** (available on your Desktop or in the build output).
2. Run the installer and choose your installation directory (defaults to your local user directory, so **no Administrator privileges** are required).
3. Click **Install**. The wizard will copy the application, bundled extensions, icon, and FFmpeg resources. It will also register the custom protocol handler and shortcut icons.

### 2. Browser Extension Integration
1. Restart Google Chrome or Microsoft Edge.
2. The browser will prompt: `"New extension added (YouTubeDownloader)"`. Click **Enable extension**.
3. If the prompt does not appear, navigate to `chrome://extensions/` or `edge://extensions/` and toggle the **YouTubeDownloader** extension **ON**.

### 3. Downloading Videos
1. Go to any YouTube watch page (e.g., `https://www.youtube.com/watch?v=...`).
2. Hover over the video player. You will see the download menu overlay in the top-right corner.
3. Click **MP4**, **MOV**, or **MP3**. 
4. The system will handle the request, launch the downloader if closed, and start downloading the stream.

---

## Developer Guide

If you want to modify or compile the project from source:

### Prerequisites
- Python 3.10+
- PyInstaller (`pip install pyinstaller`)
- Pillow (`pip install Pillow`)

### Compilation Commands

If you make modifications to the code, compile the application using PyInstaller. 

> [!NOTE]
> Since PyInstaller builds temporary files in your workspace, ensure you have sufficient disk space. If building on a drive with limited space, use the `--distpath` and `--workpath` arguments to route compilation to another partition (like `C:`).

#### 1. Compile the Main Application
Generates the core background downloader without a console prompt:
```bash
python -m PyInstaller --noconsole --onefile --icon=icon.ico --add-data "icon.ico;." --name=youtubedownloader app.py
```

#### 2. Compile the Setup Wizard
Bundles the core executable, the extension assets, the icon, and the FFmpeg files into a single installer:
```bash
python -m PyInstaller --onefile --noconsole --name=youtubedownloader_setup --icon=icon.ico --add-data "dist/youtubedownloader.exe;." --add-data "extension;extension" --add-data "icon.ico;." --add-data "ffmpeg.exe;." --add-data "ffprobe.exe;." installer.py
```

---

## File Structure

```text
├── app.py                     # Main downloader Tkinter application and local server
├── installer.py               # Setup Wizard installation and uninstallation UI
├── icon.png                   # Image asset for the app icon
├── icon.ico                   # Converted Windows icon format
├── ffmpeg.exe                 # Local FFmpeg binary (bundled during install)
├── ffprobe.exe                # Local FFprobe binary (bundled during install)
├── extension/                 # Chrome & Edge unpacked Extension folder
│   ├── manifest.json          # Manifest V3 extension configuration
│   ├── content.js             # YouTube video overlay inject script
│   └── icon.png               # Extension icon
└── README.md                  # Project documentation
```

---

## License

This project is created for personal and educational use. Merging is powered by the FFmpeg build, and stream extraction is powered by the [yt-dlp](https://github.com/yt-dlp/yt-dlp) library.
