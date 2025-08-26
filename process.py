import os
import glob
import subprocess
import shutil
from PyQt6.QtCore import QThread, pyqtSignal
from yt_dlp import YoutubeDL
from retry_handler import create_download_retry_handler, NetworkStatusChecker
from pathlib import Path
import platform
import random
from settings import AppSettings


def _ffmpeg_candidates():
    """Return a list of ffmpeg executable candidates to try, cross-platform."""
    candidates = []
    bin_dir = Path('./bin').resolve()
    system = platform.system().lower()

    # Prefer bundled ffmpeg in ./bin if present
    if system == 'windows':
        candidates.append(str(bin_dir / 'ffmpeg.exe'))
        candidates.append('ffmpeg.exe')
    else:
        candidates.append(str(bin_dir / 'ffmpeg'))
        candidates.append('ffmpeg')

    return candidates


def check_ffmpeg():
    """Check if FFmpeg is available on the system (try bundled then PATH)."""
    for exe in _ffmpeg_candidates():
        try:
            subprocess.run([exe, '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
            continue
    return False


def convert_to_m4a(file_path):
    """
    Converts an audio file to .m4a using FFmpeg and deletes the original file.
    """
    if not check_ffmpeg():
        print("FFmpeg not found. Skipping conversion to M4A.")
        return

    base, ext = os.path.splitext(file_path)
    output_path = f"{base}.m4a"

    # If already m4a, skip
    if ext.lower() == '.m4a':
        return

    # Use the first working ffmpeg candidate
    ffmpeg_exe = None
    for exe in _ffmpeg_candidates():
        try:
            subprocess.run([exe, '-version'], capture_output=True, check=True)
            ffmpeg_exe = exe
            break
        except Exception:
            continue

    if not ffmpeg_exe:
        print("FFmpeg not found. Skipping conversion to M4A.")
        return

    cmd = [
        ffmpeg_exe, '-y',
        '-i', file_path,
        '-c:a', 'aac',
        '-b:a', '192k',
        '-movflags', '+faststart',
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        os.remove(file_path)
        print(f"Converted to M4A and deleted original: {file_path}")
    except Exception as e:
        print(f"Failed to convert {file_path} to M4A: {e}")


class DownloadThread(QThread):
    progress = pyqtSignal(str)
    video_info = pyqtSignal(str, str)  # title, filesize
    download_progress = pyqtSignal(str, str)  # percentage, speed
    download_failed = pyqtSignal(str)  # error message
    finished = pyqtSignal()
    retry_info = pyqtSignal(str)  # retry status messages

    def __init__(self, url, resolution, download_subs, download_path=None, log_manager=None, preferred_container: str | None = None):
        super().__init__()
        self.url = url
        self.resolution = resolution
        self.download_subs = download_subs
        self._is_cancelled = False
        self.current_video_title = None  # Store current video title for error display
        self.ffmpeg_available = check_ffmpeg()
        self.download_success = False
        self.error_message = None
        self.log_manager = log_manager  # Optional logging integration
        self.app_settings = AppSettings()
        self.cookie_file = None  # Cookie file for authentication
        # Respect user preferences for formats
        try:
            self.preferred_video_format = self.app_settings.get_preferred_video_format().lower().strip()
        except Exception:
            self.preferred_video_format = "mp4"
        try:
            self.preferred_audio_format = self.app_settings.get_preferred_audio_format().lower().strip()
        except Exception:
            self.preferred_audio_format = "m4a"
        try:
            self.preferred_audio_quality = self.app_settings.get_audio_quality()
        except Exception:
            self.preferred_audio_quality = "192k"

        # Allow explicit override from UI selection (Choose Format)
        if isinstance(preferred_container, str) and preferred_container.strip():
            self.preferred_video_format = preferred_container.strip().lower()

        if download_path and download_path.strip():
            self.download_path = download_path.strip()
        else:
            # Choose a sensible fallback: settings default → ~/Downloads → CWD
            default_path = ""
            try:
                default_path = self.app_settings.get_default_download_path() or ""
            except Exception:
                default_path = ""
            candidates = []
            if default_path:
                candidates.append(default_path)
            candidates.append(str(Path.home() / "Downloads"))
            candidates.append(str(Path.cwd()))
            self.download_path = None
            for candidate in candidates:
                try:
                    if candidate:
                        Path(candidate).mkdir(parents=True, exist_ok=True)
                        self.download_path = candidate
                        break
                except Exception:
                    continue
            if not self.download_path:
                self.download_path = str(Path.cwd())

        # Initialize retry handler with custom delays: 30s, 1min, 3min
        self.retry_handler = create_download_retry_handler(
            max_retries=3,
            retry_delays=[30, 60, 180]  # 30 seconds, 1 minute, 3 minutes
        )

        # Connect retry signals
        self.retry_handler.retry_attempt.connect(self.on_retry_attempt)
        self.retry_handler.retry_success.connect(self.on_retry_success)
        self.retry_handler.retry_failed.connect(self.on_retry_failed)

    def run(self):
        os.makedirs(self.download_path, exist_ok=True)

        # Check FFmpeg availability at start
        if not self.ffmpeg_available:
            self.progress.emit("Warning: FFmpeg not found. Video/audio merging may not work properly.")

        try:
            # Use retry handler for the entire download process
            self.retry_handler.execute_with_retry(self._download_with_ytdl)
            self.download_success = True
        except Exception as e:
            self.download_success = False
            self.error_message = str(e)

            if not self._is_cancelled:
                # Emit failure signal with error details
                error_msg = f"Download failed: {str(e)}"
                if self.current_video_title:
                    error_msg = f"Error downloading {self.current_video_title}: {str(e)}"

                self.progress.emit(error_msg)
                self.download_failed.emit(error_msg)
        finally:
            if self._is_cancelled:
                self.cleanup_partial_files()
                self.progress.emit("Download cancelled.")
                if self.log_manager:
                    self.log_manager.complete_download_session(success=False, error_message="Cancelled by user")
            elif self.download_success:
                if self.log_manager:
                    self.log_manager.complete_download_session(success=True, download_path=self.download_path)
            else:
                if self.log_manager:
                    self.log_manager.complete_download_session(success=False, error_message=self.error_message)

            self.finished.emit()

    def get_format_selector(self):
        """Get the appropriate format selector based on resolution and FFmpeg availability"""
        # Log the resolution being used for debugging
        if hasattr(self, 'log_manager') and self.log_manager:
            self.log_manager.log("DEBUG", f"Format selector called with resolution: '{self.resolution}'")
        
        if self.resolution == "Audio":
            # Prefer audio ext based on user preference when possible; fall back gracefully
            if self.preferred_audio_format in ("m4a", "aac"):
                format_str = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
            elif self.preferred_audio_format in ("opus", "webm"):
                format_str = "bestaudio[ext=webm]/bestaudio[acodec*=opus]/bestaudio/best"
            elif self.preferred_audio_format == "mp3":
                # No native mp3 streams on YouTube; pick best and postprocess later
                format_str = "bestaudio/best"
            else:
                format_str = "bestaudio/best"
            
            if hasattr(self, 'log_manager') and self.log_manager:
                self.log_manager.log("DEBUG", f"Audio format selector: '{format_str}'")
            return format_str

        # For video downloads
        height = self.resolution[:-1]  # Remove 'p' from resolution (e.g., '1080p' -> '1080')
        
        # Log the height being used for format selection
        if hasattr(self, 'log_manager') and self.log_manager:
            self.log_manager.log("DEBUG", f"Video format selection: height={height}, resolution='{self.resolution}'")

        if self.ffmpeg_available:
            # With FFmpeg: Can merge video and audio streams, prefer streams that match target container
            if self.preferred_video_format == "mp4":
                format_str = (
                    f"bestvideo[height={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height={height}][ext=mp4]+bestaudio/"
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio/"
                    f"best[height={height}][ext=mp4]/"
                    f"best[height<={height}][ext=mp4]/"
                    f"best"
                )
            elif self.preferred_video_format == "webm":
                format_str = (
                    f"bestvideo[height={height}][ext=webm]+bestaudio[ext=webm]/"
                    f"bestvideo[height={height}][ext=webm]+bestaudio/"
                    f"bestvideo[height<={height}][ext=webm]+bestaudio[ext=webm]/"
                    f"bestvideo[height<={height}][ext=webm]+bestaudio/"
                    f"best[height={height}][ext=webm]/"
                    f"best[height<={height}][ext=webm]/"
                    f"best"
                )
            elif self.preferred_video_format == "mkv":
                # MKV is a container we can merge into; prefer any bestvideo+bestaudio, exact height first
                format_str = (
                    f"bestvideo[height={height}]+bestaudio/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"best[height={height}]/"
                    f"best[height<={height}]/"
                    f"best"
                )
            else:  # other containers: be flexible and let merger set container
                format_str = (
                    f"bestvideo[height={height}]+bestaudio/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"best[height={height}]/"
                    f"best[height<={height}]/"
                    f"best"
                )
        else:
            # Without FFmpeg: Can't merge, so prioritize single files
            # Prefer a single file in the user's chosen container, exact height first
            if self.preferred_video_format in ("mp4", "webm"):
                format_str = (
                    f"best[height={height}][ext={self.preferred_video_format}]/"
                    f"best[ext={self.preferred_video_format}]/"
                    f"best[height<={height}]/best"
                )
            # Generic fallback
            else:
                format_str = f"best[height={height}]/best[height<={height}]/best"
        
        # Log the final format string
        if hasattr(self, 'log_manager') and self.log_manager:
            self.log_manager.log("DEBUG", f"Video format selector: '{format_str}'")
        
        return format_str

    def get_single_video_info(self, video_url):
        """Get detailed info for a single video (PHASE 2)"""
        ydl_opts = {
            'extract_flat': False,  # NOW we get download URLs
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,  # Ensure single video, even if URL contains list=
            'format': self.get_format_selector(),
            'socket_timeout': 20,
        }

        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(video_url, download=False)

    def _download_with_ytdl(self):
        """The actual download logic wrapped for retry handling"""
        # Gentle pre-request sleep if enabled
        if self.app_settings.is_throttle_enabled():
            pre_min, pre_max = self.app_settings.get_pre_delay_range()
            try:
                _sleep = random.uniform(pre_min, pre_max)
            except Exception:
                _sleep = (pre_min + pre_max) / 2.0
            finally:
                import time as _t
                _t.sleep(max(0.0, _sleep))

        sleep_interval, max_sleep_interval, sleep_requests, max_sleep_requests, concurrent_fragments = self.app_settings.get_request_sleep()
        rate_limit = self.app_settings.get_rate_limit_bytes() if self.app_settings.is_throttle_enabled() else 0

        ydl_opts = {
            "outtmpl": os.path.join(self.download_path, "%(title)s.%(ext)s"),
            "progress_hooks": [self.progress_hook],
            "format": self.get_format_selector(),
            "noplaylist": True,  # Force single video downloads even when URL has list param
            # Merging options (only used if FFmpeg is available). Respect user preference.
            "merge_output_format": (self.preferred_video_format if (self.resolution != "Audio" and self.preferred_video_format in ("mp4", "webm", "mkv")) else None),

            # Robustness options
            "socket_timeout": 30,
            "retries": 1,  # yt-dlp internal retries (keep low since we handle retries)
            "fragment_retries": 3,
            "extractor_retries": 2,
            "no_warnings": True,

            # Error handling
            "ignoreerrors": False,

            # Skip existing files if enabled
            "skip_download": False,  # We want to download, just skip if exists
            "skip_existing": True,  # Always skip existing files to avoid duplicates

            # Throttling to be gentler with YouTube (configurable)
            "concurrent_fragments": max(1, concurrent_fragments),
            **({"ratelimit": int(rate_limit)} if rate_limit > 0 else {}),
            "sleep_interval": max(0, sleep_interval),
            "max_sleep_interval": max(0, max_sleep_interval),
            "sleep_requests": max(0, sleep_requests),
            "max_sleep_requests": max(0, max_sleep_requests),
        }

        # Log extractor client and format
        if hasattr(self, 'log_manager') and self.log_manager:
            try:
                self.log_manager.log("DEBUG", f"yt-dlp options: ffmpeg_available={self.ffmpeg_available}, merge_format='{ydl_opts.get('merge_output_format')}'")
                self.log_manager.log("DEBUG", f"yt-dlp format string: {ydl_opts.get('format')}")
            except Exception:
                pass

        # Add cookie file if available
        if self.cookie_file and os.path.exists(self.cookie_file):
            ydl_opts["cookiefile"] = self.cookie_file
            if self.log_manager:
                self.log_manager.log("INFO", f"Using cookies from: {self.cookie_file}")

        # Add subtitle options if requested
        if self.download_subs:
            ydl_opts.update({
                "writesubtitles": True,
                "subtitleslangs": ["en"],
                "subtitlesformat": "srt",
                "writeautomaticsub": True
            })

        # Add FFmpeg-specific options if available
        if self.ffmpeg_available:
            # Always prefer ffmpeg when available
            ydl_opts.update({"prefer_ffmpeg": True})
            # For mp4, optimize for streaming and ensure AAC compatibility
            if self.resolution != "Audio" and self.preferred_video_format == "mp4":
                ydl_opts.update({
                    "postprocessor_args": [
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-movflags", "+faststart"
                    ]
                })
            # For webm, keep stream copies when possible
        else:
            # If no FFmpeg, warn user about potential quality limitations
            self.progress.emit("Note: FFmpeg not available - downloading single stream files only")

        # Configure audio-only extraction to preferred format via postprocessor
        if self.resolution == "Audio" and self.ffmpeg_available:
            # yt-dlp expects quality without 'k'
            quality_num = ''.join(ch for ch in self.preferred_audio_quality if ch.isdigit()) or "192"
            # Normalize audio codec name for yt-dlp
            codec = self.preferred_audio_format
            if codec == 'm4a':
                codec = 'm4a'
            elif codec == 'mp3':
                codec = 'mp3'
            elif codec == 'opus':
                codec = 'opus'
            ydl_opts.update({
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": codec,
                        "preferredquality": quality_num,
                    }
                ]
            })

        with YoutubeDL(ydl_opts) as ydl:
            # Check if we're cancelled before starting
            if self._is_cancelled:
                raise Exception("Download cancelled by user")

            # First, extract video info
            self.progress.emit("Getting video information...")
            info = ydl.extract_info(self.url, download=False)

            # Log selected format from info
            try:
                fmt = info.get('format')
                height = info.get('height') or (info.get('requested_formats') or [{}])[0].get('height')
                self.log_manager.log("DEBUG", f"yt-dlp selected format in info: '{fmt}', height={height}")
                # Briefly log a couple of available formats for debugging
                fmts = info.get('formats') or []
                sample = []
                for f in fmts:
                    if isinstance(f, dict) and f.get('vcodec') != 'none':
                        sample.append(f"itag={f.get('format_id')} h={f.get('height')} ext={f.get('ext')}")
                    if len(sample) >= 5:
                        break
                if sample:
                    self.log_manager.log("DEBUG", "Available video formats (sample): " + ", ".join(sample))
            except Exception:
                pass

            if self._is_cancelled:
                raise Exception("Download cancelled by user")

            # Get video details and store title
            title = info.get('title', 'Unknown Title')
            self.current_video_title = title  # Store for potential error display
            filesize = self.format_filesize(info.get('filesize') or info.get('filesize_approx', 0))

            # Log video information
            if self.log_manager:
                self.log_manager.update_video_info(title, filesize)

            # Check what format will actually be downloaded
            format_info = info.get('format', 'Unknown format')
            if '+' in format_info and self.ffmpeg_available:
                self.progress.emit("Video and audio will be merged into single file")
            elif self.resolution != "Audio":
                self.progress.emit("Downloading single stream (video+audio combined)")

            # Send video info to UI
            self.video_info.emit(title, filesize)
            self.progress.emit("Starting download...")

            # Start actual download
            ydl.download([self.url])

            # Audio-only conversion now handled via yt-dlp postprocessor above

    def progress_hook(self, d):
        if self._is_cancelled:
            raise Exception("Download cancelled by user")

        if d["status"] == "downloading":
            # Extract progress information
            percent = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', '').strip()

            # Log progress to logging system
            if self.log_manager:
                # Only log every 10% to avoid spam
                try:
                    progress_num = float(percent.replace('%', ''))
                    if progress_num % 10 == 0:
                        self.log_manager.update_download_progress(percent, speed)
                except:
                    pass

            self.download_progress.emit(percent, speed)
            self.progress.emit(f"Downloading… {percent}")

        elif d["status"] == "finished":
            # Clear the speed when download finishes
            self.download_progress.emit("100%", "")
            self.progress.emit("Processing download…")

        elif d["status"] == "processing":
            self.progress.emit("Processing download…")

        elif d["status"] == "post_processing":
            self.progress.emit("Processing download…")

        elif d["status"] == "skipped":
            # File already exists, show appropriate message
            filename = d.get('filename', 'Unknown file')
            self.progress.emit(f"⏭️ File already exists: {filename}")

        elif d["status"] == "error":
            # Handle download errors
            error_msg = d.get('error', 'Unknown error')
            self.progress.emit(f"❌ Download error: {error_msg}")

    def on_retry_attempt(self, attempt, max_attempts, error_msg):
        """Handle retry attempt notifications"""
        # Get the delay for this attempt
        delay_map = {1: "30 seconds", 2: "1 minute", 3: "3 minutes"}
        delay_text = delay_map.get(attempt, f"{attempt} attempt")

        retry_message = f"Retry {attempt}/{max_attempts}"
        progress_message = f"Connection issue detected. Retrying in {delay_text}... (Attempt {attempt}/{max_attempts})"

        self.retry_info.emit(retry_message)
        self.progress.emit(progress_message)

        # Log retry attempt
        if self.log_manager:
            self.log_manager.log("WARNING", f"Retry attempt {attempt}/{max_attempts}: {error_msg}")

        # Check network connectivity and wait if needed
        if not NetworkStatusChecker.is_connected():
            network_msg = "Network disconnected. Waiting for connection..."
            self.progress.emit(network_msg)
            if self.log_manager:
                self.log_manager.log("WARNING", network_msg)

            if NetworkStatusChecker.wait_for_connection(max_wait_time=15):
                restore_msg = "Network connection restored. Resuming download..."
                self.progress.emit(restore_msg)
                if self.log_manager:
                    self.log_manager.log("INFO", restore_msg)
            else:
                continue_msg = "Network still unavailable. Continuing with retry..."
                self.progress.emit(continue_msg)
                if self.log_manager:
                    self.log_manager.log("WARNING", continue_msg)

    def on_retry_success(self, message):
        """Handle successful retry"""
        success_msg = "Connection restored! Download resumed successfully."
        self.progress.emit(success_msg)
        self.retry_info.emit("Download recovered")
        if self.log_manager:
            self.log_manager.log("SUCCESS", success_msg)

    def on_retry_failed(self, message):
        """Handle final retry failure"""
        # Display error message with filename as requested
        error_msg = "Error downloading"
        if self.current_video_title:
            error_msg += f" {self.current_video_title}"

        self.progress.emit(error_msg)
        self.retry_info.emit("Download failed")
        if self.log_manager:
            self.log_manager.log("ERROR", f"Final retry failed: {message}")

    def format_filesize(self, size_bytes):
        """Convert bytes to human readable format"""
        if size_bytes == 0:
            return "Unknown size"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                if unit == 'B':
                    return f"{int(size_bytes)} {unit}"
                else:
                    return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def cancel(self):
        """Cancel the download and any retry attempts"""
        self._is_cancelled = True
        self.retry_handler.cancel()
        if self.log_manager:
            self.log_manager.log("WARNING", "Download cancelled by user request")

    def cleanup_partial_files(self):
        """Clean up partial download files"""
        patterns = ['*.part', '*.temp', '*.ytdl', '*.f*']
        cleaned_files = []
        for pattern in patterns:
            for f in glob.glob(os.path.join(self.download_path, pattern)):
                try:
                    os.remove(f)
                    cleaned_files.append(f)
                except Exception:
                    pass

        if cleaned_files and self.log_manager:
            self.log_manager.log("INFO", f"Cleaned up {len(cleaned_files)} partial files")