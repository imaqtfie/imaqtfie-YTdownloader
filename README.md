# YouTube Downloader

A simple desktop application to download YouTube videos and playlists with a modern GUI.

## Features

- 🎥 Download YouTube videos in different qualities
- 📁 Download entire playlists
- 🎵 Extract audio only (M4A, MP3, Opus, AAC)
- 🎬 Multiple video containers (MP4, WebM)
- 🔄 Batch download mode
- 🍪 Cookie management for private videos
- 🎨 Modern PyQt6 interface
- 📱 Auto-paste from clipboard
- 📊 Download progress tracking
- 🔧 Auto-updater for dependencies
- ⚙️ Advanced format selection with quality options

## Requirements

- Python 3.7+
- PyQt6
- yt-dlp
- FFmpeg

## Quick Start

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Download required binaries:**
   - [FFmpeg](https://ffmpeg.org/download.html)
   - [yt-dlp](https://github.com/yt-dlp/yt-dlp/releases)
   
   Place them in the `bin/` folder

3. **Run the application:**
   ```bash
   python main.py
   ```

## Usage

1. **Single Video:** Paste YouTube URL and click Download
2. **Playlist:** Paste playlist URL and use Batch Mode
3. **Audio Only:** Check "Audio Only" option with format choice (M4A, MP3, Opus, AAC)
4. **Video Quality:** Choose from available resolutions (360p, 720p, 1080p, etc.)
5. **Advanced Format:** Use format selector for custom container and quality options

## Reminder

Always use cookies, to prevent interruption if detected by youtube's security. I
recommend use cookies browser extension to retrive cookies in youtube tab.
Cookies feature still being updated, so be patient.

## Supported Sites

- YouTube (videos, playlists, mix)

## License

Open source project 
