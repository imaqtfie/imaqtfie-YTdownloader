#!/usr/bin/env python3
"""
Auto-updater for FFmpeg and yt-dlp with GUI
Enhanced with macOS support and crash-proof design
FIXED: Proper version checking to avoid unnecessary downloads
"""

import os
import sys
import subprocess
import requests
import zipfile
import tarfile
import shutil
import platform
import tempfile
import json
import re
from pathlib import Path
from packaging import version
import threading
import time
import traceback
from urllib.parse import urlparse

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QProgressBar, QPushButton, QTextEdit, QCheckBox,
                             QFrame, QApplication, QMessageBox, QGraphicsDropShadowEffect, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex
from PyQt6.QtGui import QFont, QPixmap, QIcon, QColor


class SafeUpdateManager:
    """Thread-safe manager for update operations with crash protection"""

    def __init__(self):
        self.mutex = QMutex()
        self.active_threads = []
        self.shutdown_requested = False

    def register_thread(self, thread):
        """Register a thread for safe shutdown"""
        try:
            self.mutex.lock()
            self.active_threads.append(thread)
        finally:
            self.mutex.unlock()

    def unregister_thread(self, thread):
        """Unregister a thread"""
        try:
            self.mutex.lock()
            if thread in self.active_threads:
                self.active_threads.remove(thread)
        finally:
            self.mutex.unlock()

    def safe_shutdown(self):
        """Safely shutdown all active threads"""
        self.shutdown_requested = True
        try:
            self.mutex.lock()
            threads_to_shutdown = self.active_threads.copy()
        finally:
            self.mutex.unlock()

        for thread in threads_to_shutdown:
            try:
                if hasattr(thread, 'cancel'):
                    thread.cancel()
                if thread.isRunning():
                    thread.quit()
                    thread.wait(3000)  # Wait up to 3 seconds
            except Exception as e:
                print(f"Warning: Error shutting down thread: {e}")


# Global instance for safe management
safe_manager = SafeUpdateManager()


class LogWindow(QDialog):
    """Separate small log window for displaying update progress"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        try:
            from theme import load_svg_icon
            self.setWindowIcon(load_svg_icon("assets/icons/updater-app-legacy.svg", None, 20))
        except Exception:
            pass

    def setup_ui(self):
        """Setup the log window UI"""
        self.setWindowTitle("Update Logs")
        self.setFixedSize(450, 300)  # Fixed small size
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)

        # Position relative to parent
        if self.parent():
            try:
                parent_geo = self.parent().geometry()
                self.move(parent_geo.x() + parent_geo.width() + 10, parent_geo.y())
            except:
                pass  # Fallback to default position

        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                           stop: 0 #1e1e1e, stop: 1 #2a2a2a);
                border: 2px solid #4f46e5;
                border-radius: 12px;
            }

            QLabel {
                color: #e2e8f0;
                font-weight: 600;
                font-size: 13px;
                background: transparent;
                padding: 8px;
            }

            QTextEdit {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 #0f0f0f, stop: 1 #1a1a1a);
                color: #e2e8f0;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                selection-background-color: #4f46e5;
            }

            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                           stop: 0 #4f46e5, stop: 1 #4338ca);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
                min-width: 60px;
            }

            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                           stop: 0 #6366f1, stop: 1 #4f46e5);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with icon + text
        header_row = QHBoxLayout()
        header_icon = QLabel()
        try:
            from theme import load_svg_icon
            # Try preferred name then fallbacks to match assets
            try:
                _hi = load_svg_icon("assets/icons/updater-view-logs.svg", None, 16)
            except Exception:
                _hi = load_svg_icon("assets/icons/updater-progress.svg", None, 16)
            header_icon.setPixmap(_hi.pixmap(16, 16))
        except Exception:
            pass
        header_label = QLabel("Update Progress")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 700;
            color: #a78bfa;
            padding: 4px;
        """)
        header_row.addStretch()
        header_row.addWidget(header_icon)
        header_row.addSpacing(6)
        header_row.addWidget(header_label)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        # Button layout
        button_layout = QHBoxLayout()

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.safe_clear)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.hide)

        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def safe_clear(self):
        """Safely clear the log area"""
        try:
            self.log_area.clear()
        except Exception as e:
            print(f"Warning: Error clearing logs: {e}")

    def add_log(self, message):
        """Add log message with enhanced formatting"""
        try:
            timestamp = time.strftime("%H:%M:%S")

            # Color coding based on message content
            if "✅" in message or "successfully" in message.lower():
                color = "#34d399"  # Green
            elif "❌" in message or "failed" in message.lower() or "error" in message.lower():
                color = "#f87171"  # Red
            elif "📦" in message or "📥" in message or "🎬" in message:
                color = "#60a5fa"  # Blue
            elif "🚀" in message or "starting" in message.lower():
                color = "#a78bfa"  # Purple
            elif "🛑" in message or "cancel" in message.lower():
                color = "#fb923c"  # Orange
            elif "ℹ️" in message or "already up to date" in message.lower():
                color = "#fbbf24"  # Yellow
            else:
                color = "#e2e8f0"  # Default light gray

            formatted_message = f'<span style="color: #64748b; font-weight: 500; font-size: 10px;">[{timestamp}]</span> <span style="color: {color}; font-weight: 500;">{message}</span>'
            self.log_area.append(formatted_message)

            # Auto-scroll to bottom
            cursor = self.log_area.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_area.setTextCursor(cursor)
        except Exception as e:
            print(f"Warning: Error adding log message: {e}")


class UpdaterThread(QThread):
    """Thread for handling updates without blocking the GUI - Enhanced with crash protection"""

    # Signals for GUI updates
    progress_updated = pyqtSignal(int)  # 0-100 progress
    status_updated = pyqtSignal(str)  # Status message
    log_updated = pyqtSignal(str)  # Log message
    update_completed = pyqtSignal(bool, str)  # success, message

    def __init__(self, install_dir="./bin", update_ffmpeg=True, update_ytdlp=True, update_browser_cookie3=True):
        super().__init__()
        self.install_dir = Path(install_dir)
        try:
            self.install_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create install directory: {e}")

        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.update_ffmpeg = update_ffmpeg
        self.update_ytdlp = update_ytdlp
        self.update_browser_cookie3 = update_browser_cookie3
        self.cancelled = False
        self.session = None

        # Register with safe manager
        safe_manager.register_thread(self)

    def __del__(self):
        """Cleanup on destruction"""
        try:
            safe_manager.unregister_thread(self)
            if self.session:
                self.session.close()
        except:
            pass

    def create_session(self):
        """Create a requests session with proper timeouts"""
        if not self.session:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
        return self.session

    def safe_emit(self, signal, *args):
        """Safely emit signals with error handling"""
        try:
            if not self.cancelled and not safe_manager.shutdown_requested:
                signal.emit(*args)
        except Exception as e:
            print(f"Warning: Error emitting signal: {e}")

    def run(self):
        """Main update process with comprehensive error handling"""
        try:
            self._run_internal()
        except Exception as e:
            error_msg = f"Critical error in updater: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            self.safe_emit(self.log_updated, f"{error_msg}")
            self.safe_emit(self.update_completed, False, f"Update failed: {str(e)}")
        finally:
            # Clean up
            try:
                if self.session:
                    self.session.close()
                safe_manager.unregister_thread(self)
            except:
                pass

    def _run_internal(self):
        """Internal run method with detailed error handling"""
        total_steps = 0
        if self.update_ytdlp:
            total_steps += 1
        if self.update_ffmpeg:
            total_steps += 1
        if self.update_browser_cookie3:
            total_steps += 1

        current_step = 0
        success_count = 0
        up_to_date_count = 0

        self.safe_emit(self.log_updated, "🚀 Starting update process...")
        self.safe_emit(self.status_updated, "Checking for updates...")

        # Create session for network requests
        self.create_session()

        # Update yt-dlp
        if self.update_ytdlp and not self.cancelled:
            try:
                self.safe_emit(self.log_updated, "📦 Checking yt-dlp updates...")
                self.safe_emit(self.status_updated, "Checking yt-dlp version...")

                result = self.update_ytdlp_internal()
                if result == "updated":
                    success_count += 1
                    self.safe_emit(self.log_updated, "✅ yt-dlp updated successfully!")
                elif result == "up_to_date":
                    up_to_date_count += 1
                    self.safe_emit(self.log_updated, "ℹ️ yt-dlp is already up to date")
                else:
                    self.safe_emit(self.log_updated, "❌ yt-dlp update failed")
            except Exception as e:
                self.safe_emit(self.log_updated, f"yt-dlp update error: {str(e)}")

            current_step += 1
            self.safe_emit(self.progress_updated, int((current_step / total_steps) * 100))

        # Update browser-cookie3
        if self.update_browser_cookie3 and not self.cancelled:
            try:
                self.safe_emit(self.log_updated, "🍪 Checking browser-cookie3 updates...")
                self.safe_emit(self.status_updated, "Checking browser-cookie3 version...")

                result = self.update_browser_cookie3_internal()
                if result == "updated":
                    success_count += 1
                    self.safe_emit(self.log_updated, "✅ browser-cookie3 updated successfully!")
                elif result == "up_to_date":
                    up_to_date_count += 1
                    self.safe_emit(self.log_updated, "ℹ️ browser-cookie3 is already up to date")
                else:
                    self.safe_emit(self.log_updated, "❌ browser-cookie3 update failed")
            except Exception as e:
                self.safe_emit(self.log_updated, f"browser-cookie3 update error: {str(e)}")

            current_step += 1
            self.safe_emit(self.progress_updated, int((current_step / total_steps) * 100))

        # Update FFmpeg
        if self.update_ffmpeg and not self.cancelled:
            try:
                self.safe_emit(self.log_updated, "🎬 Checking FFmpeg updates...")
                self.safe_emit(self.status_updated, "Checking FFmpeg version...")

                result = self.update_ffmpeg_internal()
                if result == "updated":
                    success_count += 1
                    self.safe_emit(self.log_updated, "✅ FFmpeg updated successfully!")
                elif result == "up_to_date":
                    up_to_date_count += 1
                    self.safe_emit(self.log_updated, "ℹ️ FFmpeg is already up to date")
                else:
                    self.safe_emit(self.log_updated, "❌ FFmpeg update failed")
            except Exception as e:
                self.safe_emit(self.log_updated, f"FFmpeg update error: {str(e)}")

            current_step += 1
            self.safe_emit(self.progress_updated, int((current_step / total_steps) * 100))

        # Final status
        if self.cancelled:
            self.safe_emit(self.update_completed, False, "Update cancelled by user")
        elif success_count + up_to_date_count == total_steps:
            if success_count > 0:
                if up_to_date_count > 0:
                    self.safe_emit(self.update_completed, True,
                                   f"{success_count} updated, {up_to_date_count} already current")
                else:
                    self.safe_emit(self.update_completed, True, f"All {total_steps} components updated successfully!")
            else:
                self.safe_emit(self.update_completed, True, f"All {total_steps} components are already up to date")
        elif success_count > 0 or up_to_date_count > 0:
            self.safe_emit(self.update_completed, True,
                           f"{success_count + up_to_date_count}/{total_steps} checks completed")
        else:
            self.safe_emit(self.update_completed, False, "No updates were successful")

    def cancel(self):
        """Cancel the update process"""
        self.cancelled = True
        self.safe_emit(self.log_updated, "🛑 Cancelling update...")

    def normalize_version(self, version_str):
        """Normalize version string for comparison"""
        if not version_str:
            return None

        # Remove common prefixes and suffixes
        version_str = str(version_str).strip()

        # Remove 'v' prefix if present
        if version_str.lower().startswith('v'):
            version_str = version_str[1:]

        # Remove 'n' prefix (common in FFmpeg builds)
        if version_str.startswith('n'):
            version_str = version_str[1:]

        # Split on various delimiters and take first part
        for delimiter in ['-', '_', '+', ' ']:
            if delimiter in version_str:
                version_str = version_str.split(delimiter)[0]
                break

        # Clean up any remaining non-version characters
        version_str = re.sub(r'[^0-9.]', '', version_str)

        return version_str

    def compare_versions(self, current, latest):
        """Compare two version strings - returns True if update needed"""
        try:
            current_normalized = self.normalize_version(current)
            latest_normalized = self.normalize_version(latest)

            if not current_normalized or not latest_normalized:
                return True  # Update if we can't determine versions

            # Use packaging.version for proper comparison
            current_version = version.parse(current_normalized)
            latest_version = version.parse(latest_normalized)

            return latest_version > current_version
        except Exception as e:
            self.safe_emit(self.log_updated, f"Version comparison error: {e}")
            return True  # Default to updating if comparison fails

    def get_current_version(self, program):
        """Get current version with enhanced error handling and better parsing"""
        try:
            # Handle Python packages differently from executables
            if program == "browser-cookie3":
                try:
                    import importlib.metadata
                    version_str = importlib.metadata.version('browser-cookie3')
                    self.safe_emit(self.log_updated, f"Found browser-cookie3 version: {version_str}")
                    return version_str
                except ImportError:
                    self.safe_emit(self.log_updated, "browser-cookie3 not installed")
                    return "not_installed"
                except Exception as e:
                    self.safe_emit(self.log_updated, f"Error getting browser-cookie3 version: {e}")
                    return "unknown"

            # Handle executables
            executable_name = program
            if self.system == "windows":
                executable_name += ".exe"

            executable_path = self.install_dir / executable_name

            # Check if file exists first
            if not executable_path.exists():
                self.safe_emit(self.log_updated, f"{program} executable not found at {executable_path}")
                return None

            if program == "ffmpeg":
                # Enhanced FFmpeg version detection
                result = subprocess.run([str(executable_path), "-version"],
                                        capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    output = result.stdout.lower()

                    # Look for version patterns
                    version_patterns = [
                        r'ffmpeg version ([n]?[\d\.]+)',
                        r'version ([n]?[\d\.]+)',
                        r'ffmpeg ([n]?[\d\.]+)',
                    ]

                    for pattern in version_patterns:
                        match = re.search(pattern, output)
                        if match:
                            version_str = match.group(1)
                            self.safe_emit(self.log_updated, f"Found FFmpeg version: {version_str}")
                            return version_str

                    # Fallback: try first line parsing
                    first_line = result.stdout.split('\n')[0] if result.stdout else ""
                    parts = first_line.split()
                    if len(parts) >= 3 and parts[0].lower() == 'ffmpeg':
                        version_str = parts[2] if len(parts) > 2 else parts[1]
                        self.safe_emit(self.log_updated, f"FFmpeg version (fallback): {version_str}")
                        return version_str

            elif program == "yt-dlp":
                result = subprocess.run([str(executable_path), "--version"],
                                        capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    version_str = result.stdout.strip()
                    # Clean up version string - remove 'yt-dlp' prefix if present
                    if version_str.lower().startswith('yt-dlp'):
                        version_str = version_str[6:].strip()
                    self.safe_emit(self.log_updated, f"Found yt-dlp version: {version_str}")
                    return version_str

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
            self.safe_emit(self.log_updated, f"Version check failed for {program}: {str(e)}")
        except Exception as e:
            self.safe_emit(self.log_updated, f"Unexpected error checking {program} version: {str(e)}")

        return None

    def get_latest_ytdlp_version(self):
        """Get latest yt-dlp version from GitHub API"""
        try:
            session = self.create_session()
            response = session.get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", timeout=10)
            response.raise_for_status()
            latest_version = response.json()["tag_name"]
            self.safe_emit(self.log_updated, f"Latest yt-dlp version available: {latest_version}")
            return latest_version
        except Exception as e:
            self.safe_emit(self.log_updated, f"Error fetching yt-dlp version: {e}")
            return None

    def get_latest_ffmpeg_version(self):
        """Get latest FFmpeg version - platform specific"""
        try:
            if self.system == "darwin":  # macOS
                return self.get_latest_ffmpeg_version_macos()
            else:
                # Use BtbN FFmpeg builds for Windows/Linux
                session = self.create_session()
                response = session.get("https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest", timeout=10)
                response.raise_for_status()
                tag = response.json()["tag_name"]
                self.safe_emit(self.log_updated, f"Latest FFmpeg version available: {tag}")
                return tag
        except Exception as e:
            self.safe_emit(self.log_updated, f"Error fetching FFmpeg version: {e}")
            return None

    def get_latest_ffmpeg_version_macos(self):
        """Get latest FFmpeg version for macOS from evermeet.cx"""
        try:
            session = self.create_session()
            # Get version info from evermeet.cx API
            response = session.get("https://evermeet.cx/ffmpeg/info/ffmpeg/release", timeout=10)
            response.raise_for_status()
            data = response.json()
            latest_version = data.get("version", "unknown")
            self.safe_emit(self.log_updated, f"Latest macOS FFmpeg version available: {latest_version}")
            return latest_version
        except Exception as e:
            self.safe_emit(self.log_updated, f"Error fetching macOS FFmpeg version: {e}")
            return None

    def get_latest_browser_cookie3_version(self):
        """Get latest browser-cookie3 version from PyPI"""
        try:
            session = self.create_session()
            response = session.get("https://pypi.org/pypi/browser-cookie3/json", timeout=10)
            response.raise_for_status()
            data = response.json()
            latest_version = data["info"]["version"]
            self.safe_emit(self.log_updated, f"Latest browser-cookie3 version available: {latest_version}")
            return latest_version
        except Exception as e:
            self.safe_emit(self.log_updated, f"Error fetching browser-cookie3 version: {e}")
            return None

    def safe_request(self, url, **kwargs):
        """Make a safe HTTP request with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            if self.cancelled:
                return None
            try:
                session = self.create_session()
                response = session.get(url, timeout=30, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt == max_retries - 1:
                    self.safe_emit(self.log_updated, f"Request failed after {max_retries} attempts: {e}")
                    raise
                time.sleep(1)  # Wait before retry
        return None

    def download_file_with_progress(self, url, filepath):
        """Download file with progress updates and enhanced error handling"""
        try:
            self.safe_emit(self.log_updated, f"📥 Downloading: {Path(filepath).name}")

            response = self.safe_request(url, stream=True)
            if not response:
                return False

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancelled:
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.safe_emit(self.status_updated, f"Downloading {Path(filepath).name}: {progress}%")

            return True
        except Exception as e:
            self.safe_emit(self.log_updated, f"Download failed: {e}")
            # Clean up partial download
            try:
                if Path(filepath).exists():
                    Path(filepath).unlink()
            except:
                pass
            return False

    def update_ytdlp_internal(self):
        """Internal yt-dlp update method with FIXED version checking"""
        try:
            # Get current and latest versions
            current_version = self.get_current_version("yt-dlp")
            latest_version = self.get_latest_ytdlp_version()

            if not latest_version:
                self.safe_emit(self.log_updated, "❌ Could not fetch latest yt-dlp version")
                return "failed"

            # FIXED: Proper version comparison
            if current_version:
                self.safe_emit(self.log_updated, f"Current yt-dlp: {current_version}")
                self.safe_emit(self.log_updated, f"Latest yt-dlp: {latest_version}")

                if not self.compare_versions(current_version, latest_version):
                    self.safe_emit(self.log_updated, f"ℹ️ yt-dlp is already up to date: {current_version}")
                    return "up_to_date"
                else:
                    self.safe_emit(self.log_updated, f"📦 Update needed: {current_version} → {latest_version}")
            else:
                self.safe_emit(self.log_updated, "📦 yt-dlp not found, downloading latest version...")

            # Proceed with download
            self.safe_emit(self.status_updated, "Downloading yt-dlp...")

            # Determine download URL based on platform
            if self.system == "windows":
                url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                filename = "yt-dlp.exe"
            else:
                url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                filename = "yt-dlp"

            filepath = self.install_dir / filename

            if self.download_file_with_progress(url, filepath):
                if self.system != "windows":
                    try:
                        os.chmod(filepath, 0o755)  # Make executable
                    except Exception as e:
                        self.safe_emit(self.log_updated, f"Warning: Could not set executable permissions: {e}")

                # Verify the download worked by checking version again
                new_version = self.get_current_version("yt-dlp")
                if new_version:
                    self.safe_emit(self.log_updated, f"✅ yt-dlp updated to version: {new_version}")
                    return "updated"
                else:
                    self.safe_emit(self.log_updated, "⚠️ Download completed but could not verify version")
                    return "updated"  # Assume success if download completed

            return "failed"

        except Exception as e:
            self.safe_emit(self.log_updated, f"yt-dlp update error: {e}")
            return "failed"

    def update_browser_cookie3_internal(self):
        """Internal browser-cookie3 update method"""
        try:
            # Get current and latest versions
            current_version = self.get_current_version("browser-cookie3")
            latest_version = self.get_latest_browser_cookie3_version()

            if not latest_version:
                self.safe_emit(self.log_updated, "❌ Could not fetch latest browser-cookie3 version")
                return "failed"

            # Log versions for debugging
            self.safe_emit(self.log_updated, f"Current browser-cookie3: {current_version}")
            self.safe_emit(self.log_updated, f"Latest browser-cookie3: {latest_version}")

            # Check if update is needed
            if current_version and current_version != "unknown" and current_version != "not_installed":
                if current_version == latest_version:
                    self.safe_emit(self.log_updated, f"ℹ️ browser-cookie3 is already up to date: {current_version}")
                    return "up_to_date"

            # Install/update browser-cookie3 using pip
            self.safe_emit(self.log_updated, "🍪 Installing/updating browser-cookie3...")
            self.safe_emit(self.status_updated, "Installing browser-cookie3...")

            try:
                # Use subprocess to run pip install
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "--upgrade", "browser-cookie3"
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    # Verify installation
                    new_version = self.get_current_version("browser-cookie3")
                    if new_version and new_version != "unknown" and new_version != "not_installed":
                        self.safe_emit(self.log_updated, f"✅ browser-cookie3 updated to version: {new_version}")
                        return "updated"
                    else:
                        self.safe_emit(self.log_updated, "❌ browser-cookie3 installation verification failed")
                        return "failed"
                else:
                    self.safe_emit(self.log_updated, f"❌ browser-cookie3 installation failed: {result.stderr}")
                    return "failed"
                    
            except subprocess.TimeoutExpired:
                self.safe_emit(self.log_updated, "❌ browser-cookie3 installation timed out")
                return "failed"
            except Exception as e:
                self.safe_emit(self.log_updated, f"❌ browser-cookie3 installation error: {e}")
                return "failed"

        except Exception as e:
            self.safe_emit(self.log_updated, f"browser-cookie3 update error: {e}")
            return "failed"

    def update_ffmpeg_internal(self):
        """Internal FFmpeg update method with FIXED version checking"""
        try:
            # Get current version first
            current_version = self.get_current_version("ffmpeg")

            # Check if FFmpeg exists at all
            ffmpeg_path = self.install_dir / ("ffmpeg.exe" if self.system == "windows" else "ffmpeg")
            if not ffmpeg_path.exists():
                self.safe_emit(self.log_updated, "🎬 FFmpeg not found, downloading latest version...")
            else:
                # Get latest version for comparison
                latest_version = self.get_latest_ffmpeg_version()

                if not latest_version:
                    self.safe_emit(self.log_updated, "❌ Could not fetch latest FFmpeg version")
                    return "failed"

                if current_version:
                    self.safe_emit(self.log_updated, f"Current FFmpeg: {current_version}")
                    self.safe_emit(self.log_updated, f"Latest FFmpeg: {latest_version}")

                    # FIXED: Check if update is actually needed
                    if not self.compare_versions(current_version, latest_version):
                        self.safe_emit(self.log_updated, f"ℹ️ FFmpeg is already up to date: {current_version}")
                        return "up_to_date"
                    else:
                        self.safe_emit(self.log_updated, f"🎬 Update needed: {current_version} → {latest_version}")

            # Proceed with update
            self.safe_emit(self.status_updated, "Downloading FFmpeg...")

            if self.system == "darwin":  # macOS
                result = self.update_ffmpeg_macos()
            else:
                result = self.update_ffmpeg_btbn()

            if result:
                # Verify the download worked
                new_version = self.get_current_version("ffmpeg")
                if new_version:
                    self.safe_emit(self.log_updated, f"✅ FFmpeg updated to version: {new_version}")
                return "updated" if result else "failed"
            else:
                return "failed"

        except Exception as e:
            self.safe_emit(self.log_updated, f"FFmpeg update error: {e}")
            return "failed"

    def update_ffmpeg_macos(self):
        """Update FFmpeg on macOS using evermeet.cx"""
        try:
            self.safe_emit(self.log_updated, "Using evermeet.cx for macOS FFmpeg...")

            # Download from evermeet.cx
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                archive_path = temp_path / "ffmpeg.zip"

                if not self.download_file_with_progress(url, archive_path):
                    return False

                if self.cancelled:
                    return False

                # Extract archive
                self.safe_emit(self.status_updated, "Extracting FFmpeg...")
                self.safe_emit(self.log_updated, "📦 Extracting FFmpeg archive...")

                try:
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_path)

                    # Find and copy executables
                    executables_found = 0
                    for root, dirs, files in os.walk(temp_path):
                        for file in files:
                            if file == 'ffmpeg' or (file.startswith('ffmpeg') and not file.endswith('.txt')):
                                src = Path(root) / file
                                dst = self.install_dir / 'ffmpeg'

                                # Copy and make executable
                                shutil.copy2(src, dst)
                                os.chmod(dst, 0o755)

                                self.safe_emit(self.log_updated, f"✅ Updated: {file} -> ffmpeg")
                                executables_found += 1
                                break  # Only need the main ffmpeg executable

                    return executables_found > 0

                except Exception as e:
                    self.safe_emit(self.log_updated, f"Error extracting FFmpeg: {e}")
                    return False

        except Exception as e:
            self.safe_emit(self.log_updated, f"macOS FFmpeg update error: {e}")
            return False

    def update_ffmpeg_btbn(self):
        """Update FFmpeg using BtbN builds (Windows/Linux)"""
        try:
            download_url = self.get_ffmpeg_download_url()
            if not download_url:
                self.safe_emit(self.log_updated, "Could not determine FFmpeg download URL for your platform")
                return False

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Download archive
                if download_url.endswith('.zip'):
                    archive_path = temp_path / "ffmpeg.zip"
                else:
                    archive_path = temp_path / "ffmpeg.tar.xz"

                if not self.download_file_with_progress(download_url, archive_path):
                    return False

                if self.cancelled:
                    return False

                # Extract archive
                self.safe_emit(self.status_updated, "Extracting FFmpeg...")
                self.safe_emit(self.log_updated, "📦 Extracting FFmpeg archive...")

                try:
                    if archive_path.suffix == '.zip':
                        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                            zip_ref.extractall(temp_path)
                    else:
                        with tarfile.open(archive_path, 'r:xz') as tar_ref:
                            tar_ref.extractall(temp_path)

                    # Find and copy executables
                    executables_found = 0
                    for root, dirs, files in os.walk(temp_path):
                        for file in files:
                            if file.startswith('ffmpeg') and (file.endswith('.exe') or file == 'ffmpeg'):
                                src = Path(root) / file
                                dst = self.install_dir / file
                                shutil.copy2(src, dst)
                                if self.system != "windows":
                                    os.chmod(dst, 0o755)
                                self.safe_emit(self.log_updated, f"✅ Updated: {file}")
                                executables_found += 1

                    return executables_found > 0

                except Exception as e:
                    self.safe_emit(self.log_updated, f"Error extracting FFmpeg: {e}")
                    return False

        except Exception as e:
            self.safe_emit(self.log_updated, f"BtbN FFmpeg update error: {e}")
            return False

    def get_ffmpeg_download_url(self):
        """Get FFmpeg download URL for Windows/Linux platforms"""
        try:
            session = self.create_session()
            response = session.get("https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest", timeout=10)
            response.raise_for_status()
            release_data = response.json()

            # Get list of available assets
            assets = [asset['name'] for asset in release_data.get('assets', [])]
            self.safe_emit(self.log_updated, f"Available FFmpeg builds: {len(assets)} found")

            # Determine the correct filename based on platform
            target_filename = None

            if self.system == "windows":
                if "64" in self.arch or "amd64" in self.arch or "x86_64" in self.arch:
                    target_filename = "ffmpeg-master-latest-win64-gpl.zip"
                else:
                    target_filename = "ffmpeg-master-latest-win32-gpl.zip"
            elif self.system == "linux":
                if "64" in self.arch or "x86_64" in self.arch:
                    target_filename = "ffmpeg-master-latest-linux64-gpl.tar.xz"

            if target_filename and target_filename in assets:
                download_url = f"https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/{target_filename}"
                self.safe_emit(self.log_updated, f"Selected FFmpeg build: {target_filename}")
                return download_url
            else:
                self.safe_emit(self.log_updated, f"No suitable FFmpeg build found for {self.system} {self.arch}")
                return None

        except Exception as e:
            self.safe_emit(self.log_updated, f"Error determining FFmpeg download URL: {e}")
            return None


class UpdaterDialog(QDialog):
    """GUI dialog for the updater with enhanced crash protection"""

    def __init__(self, parent=None, install_dir="./bin"):
        super().__init__(parent)
        self.install_dir = install_dir
        self.updater_thread = None
        self.log_window = None
        self._checked_once = False
        self.setup_ui()
        self.setup_connections()

    def __del__(self):
        """Cleanup on destruction"""
        try:
            self.cleanup()
        except:
            pass

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.updater_thread and self.updater_thread.isRunning():
                self.updater_thread.cancel()
                self.updater_thread.quit()
                self.updater_thread.wait(3000)

            if self.log_window:
                self.log_window.close()
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")

    def setup_ui(self):
        """Setup the user interface with improved design"""
        self.setWindowTitle("YouTube Downloader - Auto Updater")
        try:
            from theme import load_svg_icon
            # Prefer newly added autoupdater-updater.svg if available
            try:
                self.setWindowIcon(load_svg_icon("assets/icons/updater-app.svg", None, 24))
            except Exception:
                self.setWindowIcon(load_svg_icon("assets/icons/updater-app-legacy.svg", None, 24))
        except Exception:
            pass
        self.setMinimumSize(520, 420)
        self.resize(560, 460)  # Slightly larger to accommodate content
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowMinimizeButtonHint)

        # Enhanced styling with FIXED checkbox text visibility
        self.setStyleSheet("""
/* Main Dialog Background with matching gradient */
QDialog {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #f0f4f8, stop: 0.5 #e2e8f0, stop: 1 #f7fafc);
    font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', 'Arial', sans-serif;
}

/* Enhanced Labels */
QLabel {
    color: #1e293b;
    font-weight: 500;
    font-size: 14px;
}

/* Enhanced Main Buttons */
QPushButton {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #6366f1, stop: 0.5 #4f46e5, stop: 1 #4338ca);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.3px;
    min-height: 14px;
    min-width: 100px;
}

QPushButton:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #818cf8, stop: 0.5 #6366f1, stop: 1 #4f46e5);
}

QPushButton:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #4338ca, stop: 0.5 #3730a3, stop: 1 #312e81);
    padding: 13px 24px 11px 24px;
}

QPushButton:disabled {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #94a3b8, stop: 1 #64748b);
    color: rgba(255, 255, 255, 0.7);
}

/* Start Button - Success Green */
QPushButton[objectName="start_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #22c55e, stop: 0.5 #16a34a, stop: 1 #15803d);
    color: white;
}

QPushButton[objectName="start_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #4ade80, stop: 0.5 #22c55e, stop: 1 #16a34a);
}

QPushButton[objectName="start_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #15803d, stop: 0.5 #166534, stop: 1 #14532d);
    padding: 13px 24px 11px 24px;
}

/* Cancel Button - Red Gradient */
QPushButton[objectName="cancel_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #f87171, stop: 0.5 #ef4444, stop: 1 #dc2626);
}

QPushButton[objectName="cancel_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #fca5a5, stop: 0.5 #f87171, stop: 1 #ef4444);
}

QPushButton[objectName="cancel_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #dc2626, stop: 0.5 #b91c1c, stop: 1 #991b1b);
    padding: 13px 24px 11px 24px;
}

/* Close Button - Secondary Style */
QPushButton[objectName="close_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 rgba(255, 255, 255, 0.9),
                               stop: 1 rgba(255, 255, 255, 0.7));
    color: #4f46e5;
    border: 2px solid;
    border-image: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 100%) 1;
    font-weight: 600;
    font-size: 14px;
}

QPushButton[objectName="close_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #ede9fe, stop: 1 #ddd6fe);
    border-image: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%) 1;
    color: #6366f1;
}

QPushButton[objectName="close_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #c4b5fd, stop: 1 #a78bfa);
    padding: 13px 24px 11px 24px;
}

/* Logs Button - Info Style */
QPushButton[objectName="logs_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #0ea5e9, stop: 1 #0284c7);
    color: white;
    border: none;
    padding: 10px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    min-height: 12px;
    min-width: 80px;
}

QPushButton[objectName="logs_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #38bdf8, stop: 1 #0ea5e9);
}

QPushButton[objectName="logs_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #0284c7, stop: 1 #0369a1);
    padding: 11px 18px 9px 18px;
}

/* FIXED Enhanced Checkboxes - Ensured text visibility */
QCheckBox {
    color: #1e293b !important;  /* Force dark color for text */
    padding: 10px 8px;
    font-weight: 600 !important;
    font-size: 14px !important;
    spacing: 10px;
    border-radius: 6px;
    background: transparent;
    min-height: 20px;
}

QCheckBox:hover {
    background: rgba(199, 210, 254, 0.3);
    color: #1e293b !important;
}

QCheckBox:focus {
    outline: none;
    background: rgba(199, 210, 254, 0.4);
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #cbd5e1;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #ffffff, stop: 1 #f8fafc);
    margin-right: 8px;
}

QCheckBox::indicator:hover {
    border: 2px solid #8b5cf6;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #faf5ff, stop: 1 #f3e8ff);
}

QCheckBox::indicator:checked {
    border: 2px solid transparent;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #8b5cf6, stop: 1 #6366f1);
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC42IDEuNEw0LjIgNy44TDEuNCA1IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
}

QCheckBox::indicator:checked:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #a78bfa, stop: 1 #818cf8);
}

/* Enhanced Progress Bar */
QProgressBar {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #f1f5f9, stop: 1 #e2e8f0);
    border: 2px solid #cbd5e1;
    border-radius: 10px;
    text-align: center;
    font-weight: 600;
    font-size: 13px;
    color: #1e293b;
    padding: 2px;
    min-height: 18px;
    max-height: 22px;
}

QProgressBar::chunk {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                               stop: 0 #6366f1, stop: 0.3 #8b5cf6, 
                               stop: 0.7 #a855f7, stop: 1 #c084fc);
    border-radius: 8px;
    margin: 1px;
}

/* Enhanced Frames */
QFrame {
    background: rgba(255, 255, 255, 0.9);
    border-radius: 12px;
}

/* Header Frame Special Styling */
QFrame[objectName="header_frame"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #667eea, stop: 0.5 #764ba2, stop: 1 #6366f1);
    border: none;
    padding: 0px;
}

/* Options Frame Special Styling */
QFrame[objectName="options_frame"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 rgba(255, 255, 255, 0.95),
                               stop: 1 rgba(248, 250, 252, 0.9));
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    padding: 0px;
}

QFrame[objectName="options_frame"]:hover {
    border: 2px solid #c7d2fe;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 rgba(255, 255, 255, 1),
                               stop: 1 rgba(240, 249, 255, 0.95));
}

/* Success Status Styling */
QLabel[objectName="status_success"] {
    color: #166534;
    font-weight: 700;
    font-size: 14px;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #dcfce7, stop: 1 #bbf7d0);
    padding: 10px 14px;
    border-radius: 8px;
    border: 2px solid #86efac;
}

/* Error Status Styling */
QLabel[objectName="status_error"] {
    color: #dc2626;
    font-weight: 700;
    font-size: 14px;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 rgba(254, 242, 242, 0.95),
                               stop: 1 rgba(254, 226, 226, 0.9));
    padding: 10px 14px;
    border-radius: 8px;
    border: 2px solid #fca5a5;
}

/* Default Status Styling */
QLabel[objectName="status_default"] {
    color: #64748b;
    font-weight: 600;
    font-size: 13px;
    background: rgba(248, 250, 252, 0.8);
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
}
""")

        # Main layout with fixed spacing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with improved design
        header_frame = QFrame()
        header_frame.setObjectName("header_frame")
        header_frame.setFixedHeight(90)

        # Add shadow to header
        header_shadow = QGraphicsDropShadowEffect()
        header_shadow.setBlurRadius(20)
        header_shadow.setXOffset(0)
        header_shadow.setYOffset(6)
        header_shadow.setColor(QColor(102, 126, 234, 100))
        header_frame.setGraphicsEffect(header_shadow)

        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(25, 18, 25, 18)
        header_layout.setSpacing(6)

        # Title row with icon + text
        title_row = QHBoxLayout()
        title_icon = QLabel()
        try:
            from theme import load_svg_icon
            _ti = load_svg_icon("assets/icons/updater-app.svg", None, 22)
            title_icon.setPixmap(_ti.pixmap(22, 22))
        except Exception:
            pass
        title_label = QLabel("Auto Updater")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            color: white; 
            font-size: 24px; 
            font-weight: 700;
            background: transparent;
            letter-spacing: 0.5px;
            padding: 2px 0px;
        """)
        # Center icon and text together
        title_row.addStretch()
        title_row.addWidget(title_icon)
        title_row.addSpacing(8)
        title_row.addWidget(title_label)
        title_row.addStretch()

        subtitle_label = QLabel("Keep your components up to date for optimal performance")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9); 
            font-size: 14px;
            background: transparent;
            font-weight: 400;
            letter-spacing: 0.2px;
        """)

        header_layout.addLayout(title_row)
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header_frame)

        # Options frame with improved design
        options_frame = QFrame()
        options_frame.setObjectName("options_frame")
        options_frame.setMinimumHeight(160)  # Let layout grow; ensure comfortable minimum

        # Add shadow to options frame
        options_shadow = QGraphicsDropShadowEffect()
        options_shadow.setBlurRadius(15)
        options_shadow.setXOffset(0)
        options_shadow.setYOffset(3)
        options_shadow.setColor(QColor(0, 0, 0, 20))
        options_frame.setGraphicsEffect(options_shadow)

        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(20, 18, 20, 18)
        options_layout.setSpacing(10)

        # Section title with icon + text
        options_title_row = QHBoxLayout()
        options_icon = QLabel()
        try:
            from theme import load_svg_icon
            _oi = load_svg_icon("assets/icons/updater-settings.svg", None, 36)
            options_icon.setPixmap(_oi.pixmap(36, 36))
        except Exception:
            pass
        options_title = QLabel("Select Components to Update")
        options_title.setStyleSheet("""
            font-weight: 700;
            color: #1e293b;
            font-size: 16px;
            padding: 0px 0px 8px 0px;
            background: transparent;
        """)
        options_title_row.addWidget(options_icon)
        options_title_row.addSpacing(8)
        options_title_row.addWidget(options_title)
        options_title_row.addStretch()
        options_layout.addLayout(options_title_row)

        # Checkboxes for what to update with improved styling
        self.ffmpeg_checkbox = QCheckBox("Update FFmpeg (Video Processing)")
        self.ffmpeg_checkbox.setChecked(True)
        try:
            from theme import load_svg_icon
            self.ffmpeg_checkbox.setIcon(load_svg_icon("assets/icons/updater-downloading.svg", None, 18))
        except Exception:
            pass
        self.ffmpeg_checkbox.setStyleSheet("""
            QCheckBox {
                color: #1e293b;
                padding: 10px 8px;
                font-weight: 600;
                font-size: 14px;
                spacing: 10px;
                border-radius: 8px;
                background: transparent;
                min-height: 20px;
            }
            QCheckBox:hover {
                background: rgba(199, 210, 254, 0.25);
                color: #1e293b;
            }
        """)

        self.ytdlp_checkbox = QCheckBox("Update yt-dlp (Video Downloader)")
        self.ytdlp_checkbox.setChecked(True)
        try:
            from theme import load_svg_icon
            self.ytdlp_checkbox.setIcon(load_svg_icon("assets/icons/updater-package-ytdlp.svg", None, 18))
        except Exception:
            pass
        self.ytdlp_checkbox.setStyleSheet("""
            QCheckBox {
                color: #1e293b;
                padding: 10px 8px;
                font-weight: 600;
                font-size: 14px;
                spacing: 10px;
                border-radius: 8px;
                background: transparent;
                min-height: 20px;
            }
            QCheckBox:hover {
                background: rgba(199, 210, 254, 0.25);
                color: #1e293b;
            }
        """)

        self.browser_cookie3_checkbox = QCheckBox("Update browser-cookie3 (Cookie Management)")
        self.browser_cookie3_checkbox.setChecked(True)
        try:
            from theme import load_svg_icon
            self.browser_cookie3_checkbox.setIcon(load_svg_icon("assets/icons/updater-package-browser-cookie3.svg", None, 18))
        except Exception:
            pass
        self.browser_cookie3_checkbox.setStyleSheet("""
            QCheckBox {
                color: #1e293b;
                padding: 10px 8px;
                font-weight: 600;
                font-size: 14px;
                spacing: 10px;
                border-radius: 8px;
                background: transparent;
                min-height: 20px;
            }
            QCheckBox:hover {
                background: rgba(199, 210, 254, 0.25);
                color: #1e293b;
            }
        """)

        options_layout.addWidget(self.ffmpeg_checkbox)
        options_layout.addWidget(self.ytdlp_checkbox)
        options_layout.addWidget(self.browser_cookie3_checkbox)
        layout.addWidget(options_frame)

        # Status label with fixed height
        self.status_label = QLabel("Ready to check for updates")
        self.status_label.setObjectName("status_default")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(35)
        layout.addWidget(self.status_label)

        # Progress bar with fixed height
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(24)

        # Add subtle shadow to progress bar
        progress_shadow = QGraphicsDropShadowEffect()
        progress_shadow.setBlurRadius(8)
        progress_shadow.setXOffset(0)
        progress_shadow.setYOffset(2)
        progress_shadow.setColor(QColor(0, 0, 0, 15))
        self.progress_bar.setGraphicsEffect(progress_shadow)

        layout.addWidget(self.progress_bar)

        # Spacer to push buttons to bottom
        layout.addStretch()

        # Improved button layout with better organization
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(0, 10, 0, 0)

        # Left side - Logs button
        self.logs_button = QPushButton("View Logs")
        self.logs_button.setObjectName("logs_button")
        self.logs_button.setFixedSize(140, 40)
        try:
            from theme import button_style
            self.logs_button.setStyleSheet(button_style('info', radius=6, padding='10px 18px'))
        except Exception:
            pass
        try:
            from theme import load_svg_icon
            self.logs_button.setIcon(load_svg_icon("assets/icons/updater-view-logs.svg", None, 18))
        except Exception:
            pass

        # Add subtle shadow to logs button
        logs_shadow = QGraphicsDropShadowEffect()
        logs_shadow.setBlurRadius(8)
        logs_shadow.setXOffset(0)
        logs_shadow.setYOffset(2)
        logs_shadow.setColor(QColor(14, 165, 233, 60))
        self.logs_button.setGraphicsEffect(logs_shadow)

        # Center - Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.start_button = QPushButton("Check Updates")
        self.start_button.setObjectName("start_button")
        self.start_button.setFixedSize(200, 48)
        try:
            from theme import button_style
            self.start_button.setStyleSheet(button_style('success'))
        except Exception:
            pass
        try:
            from theme import load_svg_icon
            self.start_button.setIcon(load_svg_icon("assets/icons/updater-check.svg", None, 18))
        except Exception:
            pass

        # Add glow effect to start button
        start_shadow = QGraphicsDropShadowEffect()
        start_shadow.setBlurRadius(15)
        start_shadow.setXOffset(0)
        start_shadow.setYOffset(3)
        start_shadow.setColor(QColor(34, 197, 94, 80))
        self.start_button.setGraphicsEffect(start_shadow)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.setFixedSize(130, 45)
        self.cancel_button.setVisible(False)
        try:
            from theme import button_style
            self.cancel_button.setStyleSheet(button_style('danger'))
        except Exception:
            pass
        try:
            from theme import load_svg_icon
            self.cancel_button.setIcon(load_svg_icon("assets/icons/updater-cancelling.svg", None, 18))
        except Exception:
            pass

        # Add glow effect to cancel button
        cancel_shadow = QGraphicsDropShadowEffect()
        cancel_shadow.setBlurRadius(15)
        cancel_shadow.setXOffset(0)
        cancel_shadow.setYOffset(3)
        cancel_shadow.setColor(QColor(248, 113, 113, 80))
        self.cancel_button.setGraphicsEffect(cancel_shadow)

        # Right side - Close button
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedSize(120, 40)
        try:
            from theme import button_style
            self.close_button.setStyleSheet(button_style('primary', radius=6, padding='10px 18px'))
        except Exception:
            pass
        try:
            from theme import load_svg_icon
            self.close_button.setIcon(load_svg_icon("assets/icons/updater-close.svg", None, 18))
        except Exception:
            pass

        # Add subtle shadow to close button
        close_shadow = QGraphicsDropShadowEffect()
        close_shadow.setBlurRadius(12)
        close_shadow.setXOffset(0)
        close_shadow.setYOffset(2)
        close_shadow.setColor(QColor(139, 92, 246, 60))
        self.close_button.setGraphicsEffect(close_shadow)

        # Add buttons to layouts
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.cancel_button)

        button_layout.addWidget(self.logs_button)
        button_layout.addStretch()
        button_layout.addLayout(action_layout)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def setup_connections(self):
        """Setup signal connections with error handling"""
        try:
            self.start_button.clicked.connect(self.on_start_clicked)
            self.cancel_button.clicked.connect(self.safe_cancel_update)
            self.close_button.clicked.connect(self.safe_close)
            self.logs_button.clicked.connect(self.safe_show_logs)
        except Exception as e:
            print(f"Warning: Error setting up connections: {e}")

    def on_start_clicked(self):
        """First click: check only; afterwards: start update."""
        try:
            if not self._checked_once:
                self.check_only()
            else:
                self.safe_start_update()
        except Exception as e:
            try:
                QMessageBox.warning(self, "Updater", f"Action failed: {e}")
            except Exception:
                pass

    def check_only(self):
        """Perform a compare-only check and update UI; no downloads."""
        try:
            self.status_label.setObjectName("status_default")
            self.status_label.setText("Checking for updates…")
            self.progress_bar.setVisible(False)

            # Use helper instance to query versions without starting downloads
            helper = UpdaterThread(install_dir=self.install_dir,
                                   update_ffmpeg=False,
                                   update_ytdlp=False,
                                   update_browser_cookie3=False)

            curr_ytdlp = helper.get_current_version("yt-dlp")
            latest_ytdlp = helper.get_latest_ytdlp_version()
            curr_ffmpeg = helper.get_current_version("ffmpeg")
            latest_ffmpeg = helper.get_latest_ffmpeg_version()
            curr_bc3 = helper.get_current_version("browser-cookie3")
            latest_bc3 = helper.get_latest_browser_cookie3_version()

            updates = []
            def needs(curr, latest, label):
                if not latest:
                    return f"{label}: latest unknown"
                if not curr:
                    return f"{label}: not installed → {latest}"
                try:
                    if not helper.compare_versions(curr, latest):
                        return f"{label}: up to date ({curr})"
                except Exception:
                    pass
                return f"{label}: {curr} → {latest}"

            if latest_ytdlp:
                updates.append(needs(curr_ytdlp, latest_ytdlp, "yt-dlp"))
            if latest_ffmpeg:
                updates.append(needs(curr_ffmpeg, latest_ffmpeg, "FFmpeg"))
            if latest_bc3:
                updates.append(needs(curr_bc3, latest_bc3, "browser-cookie3"))

            summary = "\n".join(u for u in updates if u)

            any_needed = False
            try:
                # Determine if any line indicates an update is needed via →
                any_needed = any("→" in line for line in updates)
            except Exception:
                any_needed = False

            if any_needed:
                self.status_label.setObjectName("status_default")
                self.status_label.setText("Updates available. Review and press Start Update.")
            else:
                self.status_label.setObjectName("status_default")
                self.status_label.setText("All components are up to date. You can still start update.")

            # Show details in logs window for transparency
            self.safe_show_logs()
            self.safe_add_log("Check summary:\n" + (summary or "No details"))

            # Arm second click to start updating
            self._checked_once = True
            try:
                self.start_button.setText("Start Update")
                from theme import load_svg_icon
                self.start_button.setIcon(load_svg_icon("assets/icons/updater-start.svg", None, 18))
            except Exception:
                pass
        except Exception as e:
            try:
                QMessageBox.warning(self, "Update Check", f"Failed to check: {e}")
            except Exception:
                pass

    def safe_show_logs(self):
        """Safely show the separate log window"""
        try:
            if not self.log_window:
                self.log_window = LogWindow(self)

            if self.log_window.isVisible():
                self.log_window.raise_()
                self.log_window.activateWindow()
            else:
                self.log_window.show()
                # Position next to main dialog
                try:
                    main_geo = self.geometry()
                    self.log_window.move(main_geo.x() + main_geo.width() + 10, main_geo.y())
                except:
                    pass  # Use default position if positioning fails
        except Exception as e:
            print(f"Warning: Error showing logs: {e}")

    def safe_start_update(self):
        """Safely start the update process"""
        try:
            if not self.ffmpeg_checkbox.isChecked() and not self.ytdlp_checkbox.isChecked() and not self.browser_cookie3_checkbox.isChecked():
                QMessageBox.warning(self, "No Updates Selected",
                                    "Please select at least one component to update.")
                return

            # UI changes for update mode
            self.start_button.setVisible(False)
            self.cancel_button.setVisible(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # Update status label styling for updating state
            self.status_label.setObjectName("status_default")
            self.status_label.setStyleSheet("""
                color: #6366f1;
                font-weight: 600;
                font-size: 13px;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                           stop: 0 #ede9fe, stop: 1 #ddd6fe);
                padding: 8px 14px;
                border-radius: 8px;
                border: 2px solid #c4b5fd;
            """)

            # Show logs window automatically during update
            self.safe_show_logs()

            # Start updater thread with error protection
            try:
                self.updater_thread = UpdaterThread(
                    install_dir=self.install_dir,
                    update_ffmpeg=self.ffmpeg_checkbox.isChecked(),
                    update_ytdlp=self.ytdlp_checkbox.isChecked(),
                    update_browser_cookie3=self.browser_cookie3_checkbox.isChecked()
                )

                # Connect signals with error handling
                self.updater_thread.progress_updated.connect(self.safe_update_progress)
                self.updater_thread.status_updated.connect(self.safe_update_status)
                self.updater_thread.log_updated.connect(self.safe_add_log)
                self.updater_thread.update_completed.connect(self.safe_update_completed)

                self.updater_thread.start()

            except Exception as e:
                error_msg = f"Failed to start update thread: {str(e)}"
                print(error_msg)
                self.safe_add_log(f"{error_msg}")
                self.safe_update_completed(False, error_msg)

        except Exception as e:
            error_msg = f"Error starting update: {str(e)}"
            print(error_msg)
            try:
                QMessageBox.critical(self, "Update Error", error_msg)
            except:
                pass

    def safe_cancel_update(self):
        """Safely cancel the ongoing update"""
        try:
            if self.updater_thread and self.updater_thread.isRunning():
                self.updater_thread.cancel()
                self.cancel_button.setEnabled(False)
                self.cancel_button.setText("Cancelling...")
        except Exception as e:
            print(f"Warning: Error cancelling update: {e}")

    def safe_close(self):
        """Safely close the dialog"""
        try:
            self.cleanup()
            self.close()
        except Exception as e:
            print(f"Warning: Error closing dialog: {e}")
            try:
                self.close()
            except:
                pass

    def safe_update_progress(self, value):
        """Safely update progress bar"""
        try:
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setValue(value)
        except Exception as e:
            print(f"Warning: Error updating progress: {e}")

    def safe_update_status(self, text):
        """Safely update status label"""
        try:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.setText(text)
            # Update window icon based on status keywords
            try:
                from theme import load_svg_icon
                lowered = (text or '').lower()
                icon_path = None
                if any(k in lowered for k in ["starting", "checking", "version", "prepare", "select"]):
                    icon_path = "assets/icons/updater-settings.svg"
                if any(k in lowered for k in ["downloading", "extracting", "installing"]):
                    icon_path = "assets/icons/updater-downloading.svg"
                if any(k in lowered for k in ["failed", "error", "cancel"]):
                    icon_path = "assets/icons/updater-failure.svg"
                if any(k in lowered for k in ["updated", "up to date", "complete", "success"]):
                    icon_path = "assets/icons/updater-success.svg"
                if icon_path:
                    self.setWindowIcon(load_svg_icon(icon_path, None, 24))
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: Error updating status: {e}")

    def safe_add_log(self, message):
        """Safely add log message to the separate log window"""
        try:
            if self.log_window:
                self.log_window.add_log(message)
        except Exception as e:
            print(f"Warning: Error adding log: {e}")

    def safe_update_completed(self, success, message):
        """Safely handle update completion"""
        try:
            # Reset UI
            self.cancel_button.setVisible(False)
            self.start_button.setVisible(True)
            self.start_button.setEnabled(True)
            self.progress_bar.setValue(100 if success else 0)

            # Update status with appropriate styling
            if success:
                self.status_label.setObjectName("status_success")
                self.status_label.setText("✅ " + message)
                self.status_label.setStyleSheet("""
                    color: #166534;
                    font-weight: 700;
                    font-size: 14px;
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                               stop: 0 #dcfce7, stop: 1 #bbf7d0);
                    padding: 10px 14px;
                    border-radius: 8px;
                    border: 2px solid #86efac;
                """)
            else:
                self.status_label.setObjectName("status_error")
                self.status_label.setText("❌ " + message)
                self.status_label.setStyleSheet("""
                    color: #dc2626;
                    font-weight: 700;
                    font-size: 14px;
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                               stop: 0 rgba(254, 242, 242, 0.95),
                                               stop: 1 rgba(254, 226, 226, 0.9));
                    padding: 10px 14px;
                    border-radius: 8px;
                    border: 2px solid #fca5a5;
                """)

            # Show completion message
            self.show_completion_message(success, message)

            # Set final window icon
            try:
                from theme import load_svg_icon
                final_icon = "assets/icons/updater-success.svg" if success else "assets/icons/updater-failure.svg"
                self.setWindowIcon(load_svg_icon(final_icon, None, 24))
            except Exception:
                pass

        except Exception as e:
            print(f"Warning: Error in update completion: {e}")

    def show_completion_message(self, success, message):
        """Show completion message with error handling"""
        try:
            if success:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Update Complete")
                msg_box.setText("🎉 Update Successful!")
                msg_box.setInformativeText(message)
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setStyleSheet("""
                    QMessageBox {
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                   stop: 0 #f0f4f8, stop: 1 #e2e8f0);
                        font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    }
                    QMessageBox QLabel {
                        color: #1e293b;
                        font-size: 13px;
                        font-weight: 500;
                    }
                    QMessageBox QPushButton {
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                   stop: 0 #22c55e, stop: 1 #16a34a);
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        font-weight: 600;
                        min-width: 70px;
                    }
                """)
                msg_box.exec()
            else:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Update Failed")
                msg_box.setText("⚠️ Update Failed")
                msg_box.setInformativeText(message)
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setStyleSheet("""
                    QMessageBox {
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                   stop: 0 #f0f4f8, stop: 1 #e2e8f0);
                        font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    }
                    QMessageBox QLabel {
                        color: #1e293b;
                        font-size: 13px;
                        font-weight: 500;
                    }
                    QMessageBox QPushButton {
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                   stop: 0 #f87171, stop: 1 #ef4444);
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        font-weight: 600;
                        min-width: 70px;
                    }
                """)
                msg_box.exec()
        except Exception as e:
            print(f"Warning: Error showing completion message: {e}")

    def closeEvent(self, event):
        """Handle dialog close event with cleanup"""
        try:
            self.cleanup()
            super().closeEvent(event)
        except Exception as e:
            print(f"Warning: Error in close event: {e}")
            event.accept()  # Force close even if there's an error


def safe_show_updater_dialog(parent=None, install_dir="./bin"):
    """Safely show the updater dialog with comprehensive error handling"""
    dialog = None
    try:
        dialog = UpdaterDialog(parent, install_dir)
        return dialog.exec()
    except Exception as e:
        error_msg = f"Failed to create updater dialog: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())

        # Try to show a simple error message
        try:
            if parent:
                QMessageBox.critical(parent, "Updater Error",
                                     f"Could not start updater: {str(e)}")
            else:
                print(f"Updater Error: {error_msg}")
        except:
            print(f"Critical Error: {error_msg}")

        return QDialog.DialogCode.Rejected
    finally:
        # Ensure cleanup even if dialog creation failed
        try:
            if dialog:
                dialog.cleanup()
        except:
            pass


def show_updater_dialog(parent=None, install_dir="./bin"):
    """Show the updater dialog - maintained for compatibility"""
    return safe_show_updater_dialog(parent, install_dir)


def check_and_install_dependencies():
    """Install required packages if not present with enhanced error handling"""
    required_packages = ["requests", "packaging", "PyQt6"]
    missing_packages = []

    for package in required_packages:
        try:
            if package == "PyQt6":
                import PyQt6
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"Installing required packages: {', '.join(missing_packages)}")
        for package in missing_packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {package}: {e}")
                return False
            except Exception as e:
                print(f"❌ Unexpected error installing {package}: {e}")
                return False

    return True


def main():
    """Main function with comprehensive error handling"""
    try:
        # Install dependencies if running standalone
        if not check_and_install_dependencies():
            print("Failed to install required dependencies")
            return 1

        # Create application
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Set up global exception handler
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            error_msg = f"Uncaught exception: {exc_type.__name__}: {exc_value}"
            print(error_msg)
            print(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))

            # Try to show error dialog
            try:
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Critical)
                msg_box.setWindowTitle("Critical Error")
                msg_box.setText("An unexpected error occurred in the updater.")
                msg_box.setInformativeText(f"{exc_type.__name__}: {str(exc_value)}")
                msg_box.exec()
            except:
                pass

        sys.excepthook = handle_exception

        # Run the updater
        result = safe_show_updater_dialog()

        # Safe shutdown
        safe_manager.safe_shutdown()

        return result

    except Exception as e:
        error_msg = f"Critical error in main: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        return 1
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 1


if __name__ == "__main__":
    sys.exit(main())