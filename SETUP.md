# Setup Guide

## Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/imaqtfie/imaqtfie-YTdownloader.git
cd imaqtfie-YTdownloader
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Download required binary files:
   - **ffmpeg**: Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
   - **yt-dlp**: Download from [https://github.com/yt-dlp/yt-dlp/releases](https://github.com/yt-dlp/yt-dlp/releases)

4. Place the downloaded binaries in the `bin/` directory:
```
bin/
├── ffmpeg
└── yt-dlp
```

5. Make the binaries executable (on macOS/Linux):
```bash
chmod +x bin/ffmpeg
chmod +x bin/yt-dlp
```

## Usage

Run the application:
```bash
python main.py
```

## Note

The binary files (ffmpeg and yt-dlp) are not included in this repository due to their large size. Users must download them separately and place them in the `bin/` directory.
