#!/usr/bin/env python3
from yt_dlp import YoutubeDL
from process import DownloadThread

URL = "https://www.youtube.com/watch?v=UpnSXZ08TOo"


def run_selection(url: str, resolution: str = "1080p"):
    # Create a thread instance to reuse format selector logic
    dt = DownloadThread(url, resolution, download_subs=False, download_path=".")
    fmt = dt.get_format_selector()
    print(f"Format selector for {resolution}:\n{fmt}\n")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': False,
        'socket_timeout': 20,
        'format': fmt,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        fmt_label = info.get('format')
        height = info.get('height') or (info.get('requested_formats') or [{}])[0].get('height')
        print(f"Selected by yt-dlp: format='{fmt_label}', height={height}")
        fmts = info.get('formats') or []
        sample = []
        for f in fmts:
            if isinstance(f, dict) and f.get('vcodec') != 'none':
                sample.append(f"itag={f.get('format_id')} h={f.get('height')} ext={f.get('ext')}")
            if len(sample) >= 8:
                break
        print("Sample available video formats:")
        print("\n".join(sample))


if __name__ == "__main__":
    run_selection(URL, "1080p")
