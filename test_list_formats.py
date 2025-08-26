#!/usr/bin/env python3
import os
from yt_dlp import YoutubeDL

URL = "https://www.youtube.com/watch?v=UpnSXZ08TOo"


def list_formats_default(url: str):
    print("\n=== Default extractor settings (no cookies) ===")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': False,
        'socket_timeout': 20,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        fmts = info.get('formats') or []
        title = info.get('title', 'Unknown')
        print(f"Title: {title}")
        print(f"Total formats: {len(fmts)}")
        fmts_sorted = sorted(fmts, key=lambda f: (f.get('height') or 0, f.get('fps') or 0, f.get('tbr') or 0))
        for f in fmts_sorted:
            print(f"itag={str(f.get('format_id')):>4} ext={str(f.get('ext')):<4} h={str(f.get('height')):>4} fps={str(f.get('fps')):>3} v={str(f.get('vcodec')):<12} a={str(f.get('acodec')):<8} tbr={str(f.get('tbr')):>6} note={(f.get('format_note') or '')}")


def list_formats_web(url: str):
    print("\n=== Explicit player_client=['web'] (no cookies) ===")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': False,
        'socket_timeout': 20,
        'extractor_args': {
            'youtube': {
                'player_client': ['web']
            }
        },
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        fmts = info.get('formats') or []
        title = info.get('title', 'Unknown')
        print(f"Title: {title}")
        print(f"Total formats: {len(fmts)}")
        fmts_sorted = sorted(fmts, key=lambda f: (f.get('height') or 0, f.get('fps') or 0, f.get('tbr') or 0))
        for f in fmts_sorted:
            print(f"itag={str(f.get('format_id')):>4} ext={str(f.get('ext')):<4} h={str(f.get('height')):>4} fps={str(f.get('fps')):>3} v={str(f.get('vcodec')):<12} a={str(f.get('acodec')):<8} tbr={str(f.get('tbr')):>6} note={(f.get('format_note') or '')}")


if __name__ == "__main__":
    try:
        list_formats_default(URL)
    except Exception as e:
        print(f"Default extractor failed: {e}")
    try:
        list_formats_web(URL)
    except Exception as e:
        print(f"Web client failed: {e}")
