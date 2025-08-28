import sys
import os
import platform
import random
from pathlib import Path

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QCheckBox, QMessageBox, QLabel, \
    QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QStandardPaths, QPropertyAnimation, QEasingCurve, QSize
from ui import MainUI
from settings import SettingsDialog, AppSettings, InformationDialog
from process import DownloadThread
from batchmode import BatchModeManager, BatchModeUI
from autopaste import AutoPasteManager
from log import LogManager, LogDialog
from cookie_manager import show_cookie_detection_dialog, show_cookie_help_dialog, auto_detect_cookies, test_cookies
from format_dialog import FormatChooserDialog

# Auto-updater import
try:
    from autoupdate import show_updater_dialog, check_and_install_dependencies, UpdaterDialog
    UPDATER_AVAILABLE = True
except ImportError:
    UPDATER_AVAILABLE = False
    print("Auto-updater not available. Please ensure autoupdate.py is in the same directory.")


class EnhancedController:
    def __init__(self):
        self.ui = MainUI()
        self.settings = AppSettings()

        # Dialog state guards
        self._format_dialog_active = False
        self._deferred_playlist_info_prompt = None
        self._block_batch_after_cancel = False
        self._updates_ready = False
        self._can_open_updater_manually = False

        # Add bin directory to PATH for yt-dlp/FFmpeg
        try:
            bin_dir = Path("./bin")
            bin_dir.mkdir(exist_ok=True)
            bin_path = str(bin_dir.resolve())
            if bin_path not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{bin_path}{os.pathsep}{os.environ.get('PATH', '')}"
        except Exception:
            # Keep running even if PATH update fails
            pass

        # Set default download path
        self.set_default_download_path()

        # Setup auto-updater
        if UPDATER_AVAILABLE:
            try:
                self.ui.update_button.clicked.connect(self.on_update_button_clicked)
                self.ui.update_button.setToolTip("Check for updates")
                
                # Pre-create updater dialog
                try:
                    self._updater_dialog = UpdaterDialog(self.ui, install_dir="./bin")
                    self._updater_dialog.hide()
                except Exception:
                    self._updater_dialog = None
            except Exception:
                pass
        else:
            self.ui.update_button.setEnabled(False)
            self.ui.update_button.setToolTip("Auto-updater not available")
        
        # Initialize logging
        self.log_manager = LogManager(max_realtime_logs=200, max_history_entries=30)
        self.log_dialog = LogDialog(self.log_manager, self.ui, on_retry=self._retry_from_history)
        
        # Check for updates on startup
        self.check_and_show_update_warning()

        # Connect UI buttons
        self.ui.logs_button.clicked.connect(self.show_logs)
        if hasattr(self.ui, 'shutdown_button'):
            self._init_shutdown_menu()
        if hasattr(self.ui, 'settings_button'):
            self.ui.settings_button.clicked.connect(self.show_settings)
            
        # Connect test cookies button
        if hasattr(self.ui, 'test_cookies_button'):
            self.ui.test_cookies_button.clicked.connect(self.test_current_cookies)
            
        # Connect refresh cookies button
        if hasattr(self.ui, 'refresh_cookies_button'):
            self.ui.refresh_cookies_button.clicked.connect(self.refresh_cookie_status)
            # UI sets refresh icon and size


        # Initialize batch mode and autopaste managers
        self.batch_manager = BatchModeManager()
        self.autopaste_manager = AutoPasteManager()

        # Connect UI signals
        self.ui.download_button.clicked.connect(self.start_download)
        self.ui.cancel_button.clicked.connect(self.cancel_download)
        self.setup_enhanced_ui()

        # Connect batch mode signals
        self.batch_manager.batch_status_changed.connect(self.on_batch_status_changed)
        self.batch_manager.batch_progress_updated.connect(self.on_batch_progress_updated)
        self.batch_manager.queue_limit_reached.connect(self.on_queue_limit_reached)
        self.batch_manager.queue_limit_warning.connect(self.on_queue_limit_warning)
        self.batch_manager.playlist_detected.connect(self.on_playlist_detected)
        self.batch_manager.playlist_loading.connect(self.on_playlist_loading)

        # Connect autopaste signals
        self.autopaste_manager.url_detected.connect(self.on_url_detected)

        # Check for updates on startup
        self.check_for_updates_on_startup()

        # Load default settings
        self.ui.load_default_settings(self.settings)

        # Initialize state variables
        self.is_downloading = False
        self.total_file_size = 0
        self.downloaded_size = 0
        self._dl_glow_effect = None
        self._dl_glow_anim = None

        # Initialize logging
        self.log_manager.log("INFO", "YouTube Downloader started")

    def set_default_download_path(self):
        """Set default download path to user's Downloads folder."""
        try:
            default_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)

            # Fallbacks if Qt doesn't return a path
            if not default_path:
                home_dir = Path.home()
                default_path = str(home_dir / "Downloads")

            downloads_folder = Path(default_path)
            downloads_folder.mkdir(parents=True, exist_ok=True)
            self.ui.path_input.setText(str(downloads_folder))
        except Exception:
            # Last resort: current working directory
            self.ui.path_input.setText(str(Path.cwd()))

    def check_for_updates_on_startup(self):
        """Check for updates on startup."""
        if UPDATER_AVAILABLE:
            # Check for updates after a short delay (reduced from 2000ms to 500ms)
            QTimer.singleShot(500, lambda: self.check_and_show_update_warning(arm_button=True))

    def check_and_show_update_warning(self, arm_button: bool = True):
        """Check for available updates and update button display."""
        try:
            if UPDATER_AVAILABLE:
                # Show checking state
                self.ui.set_update_button_state("checking")
                try:
                    self._apply_update_button_style('checking')
                except Exception:
                    pass

                # Create updater instance
                from autoupdate import UpdaterThread
                updater = UpdaterThread(install_dir="./bin")

                updates_needed = False
                update_details = []

                # Check yt-dlp with better error handling
                try:
                    current_ytdlp = updater.get_current_version("yt-dlp")
                    latest_ytdlp = updater.get_latest_ytdlp_version()

                    self.log_manager.log("DEBUG", f"yt-dlp versions - Current: {current_ytdlp}, Latest: {latest_ytdlp}")

                    if latest_ytdlp:
                        if not current_ytdlp:
                            updates_needed = True
                            update_details.append("yt-dlp: Not installed")
                        elif current_ytdlp != latest_ytdlp:
                            # Additional check: only show warning if versions are significantly different
                            try:
                                from packaging import version
                                if version.parse(current_ytdlp) < version.parse(latest_ytdlp):
                                    updates_needed = True
                                    update_details.append(f"yt-dlp: {current_ytdlp} → {latest_ytdlp}")
                            except:
                                # Fallback to string comparison if version parsing fails
                                if current_ytdlp != latest_ytdlp:
                                    updates_needed = True
                                    update_details.append(f"yt-dlp: {current_ytdlp} → {latest_ytdlp}")
                    else:
                        self.log_manager.log("DEBUG", "Could not fetch latest yt-dlp version")
                except Exception as e:
                    self.log_manager.log("DEBUG", f"yt-dlp version check failed: {str(e)}")

                # Check ffmpeg with better handling
                try:
                    current_ffmpeg = updater.get_current_version("ffmpeg")
                    self.log_manager.log("DEBUG", f"FFmpeg version check - Current: {current_ffmpeg}")

                    if not current_ffmpeg:
                        # Only show warning if FFmpeg executable doesn't exist
                        ffmpeg_path = Path("./bin") / (
                            "ffmpeg.exe" if platform.system().lower() == "windows" else "ffmpeg")
                        if not ffmpeg_path.exists():
                            updates_needed = True
                            update_details.append("FFmpeg: Not installed")
                        else:
                            self.log_manager.log("DEBUG", "FFmpeg exists but version check failed")
                    else:
                        self.log_manager.log("DEBUG", f"FFmpeg found: {current_ffmpeg}")
                except Exception as e:
                    self.log_manager.log("DEBUG", f"FFmpeg version check failed: {str(e)}")

                # Update UI based on results
                # Only arm the button for starting updates if explicitly requested
                if arm_button:
                    self._updates_ready = bool(updates_needed)
                if updates_needed:
                    self.ui.set_update_button_state("update_available")
                    try:
                        self._apply_update_button_style('update_available')
                    except Exception:
                        pass
                    detail_msg = "; ".join(update_details)
                    self.log_manager.log("INFO", f"Updates needed: {detail_msg}")

                    # Set tooltip with details
                    self.ui.update_button.setToolTip(
                        f"Updates available:\n{chr(10).join(update_details)}\n\nClick to update")
                    # Allow opening updater on second click only if armed
                    if arm_button:
                        self._can_open_updater_manually = True
                else:
                    # Keep same visuals as Default/YouTube regardless of theme
                    self.ui.set_update_button_state("up_to_date")
                    try:
                        self._apply_update_button_style('up_to_date')
                    except Exception:
                        pass
                    self.log_manager.log("DEBUG", "All components up to date")
                    # When not arming, keep first click as a check; otherwise allow opening
                    if arm_button:
                        self._can_open_updater_manually = True
                        self.ui.update_button.setToolTip("All components are up to date — click again to open updater")
                    else:
                        self._can_open_updater_manually = False
                        self.ui.update_button.setToolTip("All components are up to date — click to recheck")

        except Exception as e:
            self.log_manager.log("DEBUG", f"Update check failed: {str(e)}")
            # On error, show default state but require a check on next click
            self.ui.set_update_button_state("default")
            self._updates_ready = False
            self._can_open_updater_manually = False
            self.ui.update_button.setToolTip("Update check failed — click to recheck")

    def on_update_button_clicked(self):
        """Single-button two-step updater: first click checks, second click starts updater if available."""
        try:
            if not UPDATER_AVAILABLE:
                return
            if self._updates_ready or self._can_open_updater_manually:
                # Start updater dialog
                self.start_update_dialog()
            else:
                # Perform a check
                self.check_and_show_update_warning()
        except Exception as e:
            try:
                QMessageBox.warning(self.ui, "Updates", f"Update action failed: {e}")
            except Exception:
                pass

    def show_logs(self):
        """Show the logs dialog"""
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def _init_shutdown_menu(self):
        try:
            from PyQt6.QtWidgets import QMenu
            from theme import get_palette
            p = get_palette()
            menu = QMenu(self.ui)
            act_restart = menu.addAction("Restart App")
            act_force_kill = menu.addAction("Force Kill")
            # Themed menu styling
            menu.setStyleSheet(f"""
                QMenu {{
                    background: {p['surface']};
                    color: {p['text']};
                    border: 1px solid {p['border']};
                    padding: 6px;
                    border-radius: 8px;
                }}
                QMenu::item {{
                    padding: 6px 12px;
                    border-radius: 6px;
                    color: {p['text']};
                }}
                QMenu::item:selected {{
                    background: rgba(67, 241, 250, 0.15);
                }}
            """)
            def _on_click():
                pos = self.ui.shutdown_button.mapToGlobal(self.ui.shutdown_button.rect().bottomRight())
                menu.exec(pos)
            self.ui.shutdown_button.clicked.connect(_on_click)
            def _restart():
                try:
                    import sys, os
                    python = sys.executable
                    os.execl(python, python, *sys.argv)
                except Exception:
                    pass
            def _force_kill():
                try:
                    import os
                    os._exit(1)
                except Exception:
                    pass
            act_restart.triggered.connect(_restart)
            act_force_kill.triggered.connect(_force_kill)
        except Exception:
            pass

    def _retry_from_history(self, entry):
        try:
            url = entry.get('url')
            resolution = entry.get('resolution') or self.ui.resolution_box.currentText()
            download_subs = bool(entry.get('download_subs', False))
            download_path = entry.get('download_path') or self.ui.path_input.text().strip()
            is_batch = bool(entry.get('batch_mode', False))
            if url:
                # Populate the link box similar to paste behavior
                self.ui.link_input.setText(url)
                # If batch entry, ensure batch mode and queue it
                if is_batch:
                    if hasattr(self, 'batch_checkbox') and not self.batch_checkbox.isChecked():
                        self.batch_checkbox.setChecked(True)
                    queue_limit = self.settings.get_max_concurrent_downloads()
                    # Add to batch queue and start batch processing
                    if self.batch_manager.add_to_batch(url, queue_limit):
                        self.start_batch_download()
                else:
                    # Single retry
                    self.start_download_with_settings(url, resolution, download_subs, download_path)
        except Exception as e:
            self.log_manager.log("ERROR", f"Retry from history failed: {e}")

    def show_settings(self):
        dlg = SettingsDialog(self.ui)
        if dlg.exec():
            # Settings were saved, refresh cookie status and other UI elements
            self.log_manager.log("INFO", "Settings updated")
            
            # Sync main window resolution dropdown with settings
            default_res = self.settings.get_default_resolution()
            if hasattr(self.ui, 'resolution_box'):
                self.ui.resolution_box.setCurrentText(default_res)
            
            # Sync main window subtitle checkbox with settings
            auto_subs = self.settings.get_auto_download_subs()
            if hasattr(self.ui, 'subtitle_checkbox'):
                self.ui.subtitle_checkbox.setChecked(auto_subs)
            
            # Sync main window download path with settings
            default_path = self.settings.get_default_download_path()
            if hasattr(self.ui, 'path_input') and default_path:
                self.ui.path_input.setText(default_path)
            
            # Update batch mode settings if active
            if self.batch_manager.is_batch_mode:
                self.update_batch_mode_from_ui()

            
            # Refresh cookie status after settings change
            self.refresh_cookie_status()
            # Re-apply themed styles on main UI and log dialog
            try:
                if hasattr(self.ui, 'apply_theme_styles'):
                    self.ui.apply_theme_styles()
            except Exception:
                pass
            try:
                if hasattr(self, 'log_dialog') and hasattr(self.log_dialog, 'apply_theme_styles'):
                    self.log_dialog.apply_theme_styles()
            except Exception:
                pass


    def on_playlist_detected(self, playlist_info):
        """Handle playlist detection and optionally prompt about limits"""
        # If batch checkbox is not enabled anymore, ignore late signals
        try:
            if hasattr(self, 'batch_checkbox') and not self.batch_checkbox.isChecked():
                return
        except Exception:
            pass
        # Defer prompt if a format chooser is currently open
        try:
            if getattr(self, '_format_dialog_active', False):
                self._deferred_playlist_info_prompt = playlist_info
                return
        except Exception:
            pass
        try:
            title = playlist_info.get('title', 'Playlist')
            count = int(playlist_info.get('video_count', 0))
            is_mix = bool(playlist_info.get('is_mix', False))
        except Exception:
            title, count = 'Playlist', 0
            is_mix = False
        # Update status
        base_msg = f"Playlist detected: '{title}' ({count} videos)"
        try:
            if not self.is_downloading:
                self.ui.status_label.setText(base_msg + " — Press Download to start")
            else:
                self.ui.status_label.setText(base_msg)
        except Exception:
            self.ui.status_label.setText(base_msg)
        # Ensure batch mode is visually and functionally enabled
        try:
            if hasattr(self, 'batch_checkbox') and not self.batch_checkbox.isChecked():
                self.batch_checkbox.setChecked(True)
        except Exception:
            pass
        # If a limit is set and exceeded, prompt the user
        try:
            limit = self.settings.get_max_concurrent_downloads()
        except Exception:
            limit = None
        # Show 3-option dialog when:
        # - playlist exceeds limit, or
        # - it's a Mix (unbounded/auto-generated), or
        # - count is unknown/non-positive but limit exists
        should_prompt = False
        if isinstance(limit, int) and limit > 0:
            if is_mix:
                should_prompt = True
            elif isinstance(count, int) and count > limit:
                should_prompt = True
            elif not isinstance(count, int) or count <= 0:
                should_prompt = True
        if should_prompt:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self.ui)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Batch Limit Exceeded")
            msg.setText(
                f"This playlist has {count} videos, but your batch limit is {limit}.\n\n"
                f"Choose an option:\n"
                f"• Trim queue to first {limit} videos\n"
                f"• Open Settings to adjust the limit"
            )
            trim_btn = msg.addButton(f"Trim to {limit}", QMessageBox.ButtonRole.AcceptRole)
            settings_btn = msg.addButton("Open Settings", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            # Theme-aware styling for dialog and buttons
            try:
                from theme import get_palette, button_style
                _p = get_palette()
                msg.setStyleSheet(f"""
                    QMessageBox {{
                        background-color: {_p['surface']};
                        color: {_p['text']};
                    }}
                    QMessageBox QLabel {{
                        color: {_p['text']};
                        font-size: 12px;
                        line-height: 1.4;
                    }}
                """)
                # Style buttons by role for visibility
                trim_btn.setStyleSheet(button_style('primary', radius=6, padding='8px 16px'))
                settings_btn.setStyleSheet(button_style('info', radius=6, padding='8px 16px'))
                cancel_btn.setStyleSheet(button_style('danger', radius=6, padding='8px 16px'))
                trim_btn.setMinimumWidth(100)
                settings_btn.setMinimumWidth(120)
                cancel_btn.setMinimumWidth(90)
            except Exception:
                # Fallback light style
                msg.setStyleSheet("""
                    QMessageBox { background-color: #f8fafc; color: #1e293b; }
                    QMessageBox QLabel { color: #1e293b; font-size: 12px; }
                """)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == trim_btn:
                try:
                    # Persist and enforce the cap for this playlist and queue
                    self.batch_manager.enforce_playlist_limit(limit)
                    self.ui.status_label.setText(f"Trimmed queue to {limit} items for '{title}' — Press Download to start")
                except Exception:
                    pass
            elif clicked == settings_btn:
                try:
                    self.show_settings()
                except Exception:
                    pass
            else:
                # Cancel: abort playlist processing and return to main
                try:
                    self.batch_manager.clear_batch_queue()
                    self.batch_manager.current_playlist_info = None
                    self.batch_manager.playlist_current_index = 0
                    if hasattr(self, 'batch_checkbox') and self.batch_checkbox.isChecked():
                        self.batch_checkbox.setChecked(False)
                    self.ui.status_label.setText("Playlist processing cancelled")
                    self._block_batch_after_cancel = True
                    # Clear link box and reset video details immediately
                    try:
                        if hasattr(self.ui, 'link_input'):
                            self.ui.link_input.clear()
                    except Exception:
                        pass
                    try:
                        self.reset_ui()
                    except Exception:
                        pass
                except Exception:
                    pass
                return
        # Clear the input to avoid re-adding the playlist URL later
        try:
            if hasattr(self.ui, 'link_input'):
                self.ui.link_input.clear()
        except Exception:
            pass

    def on_playlist_loading(self, message):
        """Handle playlist loading status"""
        # If the user cancelled a playlist flow, ignore late updates from extractor
        try:
            if getattr(self, '_block_batch_after_cancel', False):
                try:
                    self.batch_manager.clear_batch_queue()
                except Exception:
                    pass
                return
        except Exception:
            pass
        # If batch checkbox is off, ignore late loading updates
        try:
            if hasattr(self, 'batch_checkbox') and not self.batch_checkbox.isChecked():
                return
        except Exception:
            pass
        # Include an action hint when ready
        try:
            status = self.batch_manager.get_batch_status()
            if status.get('is_active') and status.get('queue_size', 0) > 0 and not self.is_downloading:
                self.ui.status_label.setText(f"{message} — Press Download to start")
            else:
                self.ui.status_label.setText(f"{message}")
        except Exception:
            self.ui.status_label.setText(f"{message}")
        self.log_manager.log("INFO", f"Playlist loading: {message}")
        # If playlist is ready and not currently downloading, highlight Download button
        try:
            status = self.batch_manager.get_batch_status()
            if status.get('is_active') and status.get('queue_size', 0) > 0 and not self.is_downloading:
                self._start_download_button_glow()
        except Exception:
            pass

    def setup_enhanced_ui(self):
        """Add batch mode and autopaste controls to the existing UI"""
        # Find the subtitle layout to add batch mode and autopaste checkboxes
        subtitle_layout = None
        buttons_layout = None

        for i in range(self.ui.layout().count()):
            item = self.ui.layout().itemAt(i)

            if hasattr(item, 'widget') and item.widget():
                widget = item.widget()
                # Look for the splitter
                if hasattr(widget, 'widget') and widget.widget(0):
                    top_frame = widget.widget(0)
                    if hasattr(top_frame, 'layout'):
                        top_layout = top_frame.layout()

                        # Find subtitle layout and buttons layout
                        for j in range(top_layout.count()):
                            layout_item = top_layout.itemAt(j)
                            if hasattr(layout_item, 'layout') and layout_item.layout():
                                layout = layout_item.layout()

                                # Check for subtitle checkbox in this layout
                                for k in range(layout.count()):
                                    widget_item = layout.itemAt(k)
                                    if hasattr(widget_item, 'widget') and isinstance(widget_item.widget(), QCheckBox):
                                        if "English Subtitles" in widget_item.widget().text():
                                            subtitle_layout = layout
                                            break

                                # Check for download button in this layout
                                for k in range(layout.count()):
                                    widget_item = layout.itemAt(k)
                                    if hasattr(widget_item, 'widget') and isinstance(widget_item.widget(), QPushButton):
                                        if widget_item.widget().text() == "Download":
                                            buttons_layout = layout
                                            break

                                if subtitle_layout and buttons_layout:
                                    break
                        break

        # Connect to existing checkboxes in the UI
        if hasattr(self.ui, 'batch_checkbox'):
            self.batch_checkbox = self.ui.batch_checkbox
            self.batch_checkbox.stateChanged.connect(self.toggle_batch_mode)
        
        if hasattr(self.ui, 'autopaste_checkbox'):
            self.autopaste_checkbox = self.ui.autopaste_checkbox
            self.autopaste_checkbox.stateChanged.connect(self.toggle_autopaste)

        # Connect resolution box changes to update batch mode settings
        if hasattr(self.ui, 'resolution_box'):
            self.ui.resolution_box.currentTextChanged.connect(self.on_resolution_changed)
            # Also connect to the activated signal for when user selects from dropdown
            self.ui.resolution_box.activated.connect(self.on_resolution_activated)
            
        # Connect subtitle checkbox changes to update batch mode settings
        if hasattr(self.ui, 'subtitle_checkbox'):
            self.ui.subtitle_checkbox.stateChanged.connect(self.on_subtitle_changed)
            
        # Connect download path changes to update batch mode settings
        if hasattr(self.ui, 'path_input'):
            self.ui.path_input.textChanged.connect(self.on_download_path_changed)

        # Add clear queue button to buttons layout
        if buttons_layout:
            # Create clear queue button with same styling as download/cancel buttons
            self.clear_queue_button = QPushButton("Clear Queue")
            self.clear_queue_button.setObjectName("clear_queue_button")
            self.clear_queue_button.setMinimumHeight(45)  # Match Download/Cancel button height
            self.clear_queue_button.setFixedWidth(160)  # Wider to prevent text clipping with padding
            self.clear_queue_button.clicked.connect(self.clear_batch_queue)

            # Apply the same shadow effect as download and cancel buttons
            clear_queue_shadow = QGraphicsDropShadowEffect()
            clear_queue_shadow.setBlurRadius(15)
            clear_queue_shadow.setXOffset(0)
            clear_queue_shadow.setYOffset(3)
            clear_queue_shadow.setColor(QColor(245, 158, 11, 80))  # Amber color for queue button
            self.clear_queue_button.setGraphicsEffect(clear_queue_shadow)

            self.clear_queue_button.hide()  # Initially hidden - only show when batch mode is enabled

            # Find the position of the cancel button and insert clear queue button before it
            cancel_button_index = -1
            for i in range(buttons_layout.count()):
                item = buttons_layout.itemAt(i)
                if hasattr(item, 'widget') and isinstance(item.widget(), QPushButton):
                    if item.widget().text() == "Cancel":
                        cancel_button_index = i
                        break

            if cancel_button_index != -1:
                buttons_layout.insertWidget(cancel_button_index, self.clear_queue_button)

    def manual_updater(self):
        """Manually launch the updater"""
        if UPDATER_AVAILABLE:
            try:
                # Remove the problematic line that calls non-existent method
                # self.ui.hide_update_warning()  # REMOVED - method doesn't exist

                # Reset update button to default state when starting update
                self.ui.set_update_button_state("default")
                try:
                    self._apply_update_button_style('default')
                except Exception:
                    pass

                # Ensure bin directory exists
                bin_dir = Path("./bin")
                bin_dir.mkdir(exist_ok=True)

                # Add bin directory to PATH
                bin_path = str(bin_dir.absolute())
                if bin_path not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{bin_path}{os.pathsep}{os.environ.get('PATH', '')}"

                result = show_updater_dialog(parent=self.ui, install_dir="./bin")
                if result:
                    self.log_manager.log("SUCCESS", "Manual update completed successfully")
                    # Check status again after successful update (reduced from 1000ms to 200ms)
                    QTimer.singleShot(200, self.check_and_show_update_warning)
                else:
                    self.log_manager.log("INFO", "Manual update cancelled")
                    # Check again for updates after cancellation
                    self.check_and_show_update_warning()
            except Exception as e:
                self.log_manager.log("ERROR", f"Manual updater failed: {str(e)}")
                QMessageBox.critical(
                    self.ui,
                    "Updater Error",
                    f"Manual updater failed:\n{str(e)}"
                )

    def _apply_update_button_style(self, state: str):
        """Force update button styling to be fully transparent (no background) across themes."""
        if not hasattr(self.ui, 'update_button') or not self.ui.update_button:
            return
        # Transparent, icon-only button; no background in any state
        qss = """
        QPushButton {
            background: transparent;
            color: inherit;
            border: none;
            border-radius: 8px;
            padding: 0px;
        }
        QPushButton:hover {
            background: transparent;
        }
        QPushButton:disabled {
            background: transparent;
            color: inherit;
        }
        """
        try:
            self.ui.update_button.setStyleSheet(qss)
        except Exception:
            pass

    def toggle_batch_mode(self, state):
        """Toggle batch mode on/off"""
        if state == 2:  # Checked
            # Get current settings
            resolution = self.ui.resolution_box.currentText()
            download_subs = self.ui.subtitle_checkbox.isChecked()
            download_path = self.ui.path_input.text().strip()

            # Disable any format selection controls in batch mode
            try:
                if hasattr(self.ui, 'choose_format_checkbox'):
                    self.ui.choose_format_checkbox.setChecked(False)
                    self.ui.choose_format_checkbox.setEnabled(False)
                if hasattr(self.ui, 'format_box'):
                    self.ui.format_box.setEnabled(False)
                if hasattr(self.ui, 'audio_format_box'):
                    self.ui.audio_format_box.setEnabled(False)
            except Exception:
                pass

            # Enable batch mode (no format chooser in batch)
            container_override = None
            audio_override = None
            self.batch_manager.enable_batch_mode(resolution, download_subs, download_path, container_override, audio_override)
            self.clear_queue_button.show()
            
            # Log the batch mode settings for debugging
            self.log_manager.log("INFO", f"Batch mode enabled with settings: resolution='{resolution}', subs={download_subs}, path='{download_path}'")

            # Disable resolution and subtitle controls (use batch settings)
            self.ui.resolution_box.setEnabled(False)
            self.ui.subtitle_checkbox.setEnabled(False)
            self.ui.path_input.setEnabled(False)
            self.ui.browse_button.setEnabled(False)
            self.log_manager.log("INFO", f"Batch mode enabled - Resolution: {resolution}, Subtitles: {download_subs}")

            # If a playlist prompt was deferred while the dialog was open, show it now
            try:
                if self._deferred_playlist_info_prompt:
                    pi = self._deferred_playlist_info_prompt
                    self._deferred_playlist_info_prompt = None
                    self.on_playlist_detected(pi)
            except Exception:
                pass

        else:  # Unchecked
            self.batch_manager.disable_batch_mode()
            self.clear_queue_button.hide()
            # Re-enable controls
            self.ui.resolution_box.setEnabled(True)
            self.ui.subtitle_checkbox.setEnabled(True)
            self.ui.path_input.setEnabled(True)
            self.ui.browse_button.setEnabled(True)
            # Re-enable format selection controls for single downloads
            try:
                if hasattr(self.ui, 'choose_format_checkbox'):
                    self.ui.choose_format_checkbox.setEnabled(True)
                if hasattr(self.ui, 'format_box'):
                    self.ui.format_box.setEnabled(True)
                if hasattr(self.ui, 'audio_format_box'):
                    self.ui.audio_format_box.setEnabled(True)
            except Exception:
                pass

            # Stop readiness glow when batch mode is disabled
            try:
                self._stop_download_button_glow()
            except Exception:
                pass

            # Reset status to reflect non-batch state
            try:
                self.reset_ui()
            except Exception:
                pass
            self.log_manager.log("INFO", "Batch mode disabled")

    def toggle_autopaste(self, state):
        """Toggle autopaste on/off"""
        if state == 2:  # Checked
            self.autopaste_manager.enable_autopaste()
            self.log_manager.log("INFO", "Auto-paste enabled")
        else:  # Unchecked
            self.autopaste_manager.disable_autopaste()
            self.log_manager.log("INFO", "Auto-paste disabled")

    def on_resolution_changed(self, new_resolution):
        """Handle resolution changes and update batch mode settings if needed"""
        self.log_manager.log("DEBUG", f"Resolution changed to: '{new_resolution}'")
        
        if self.batch_manager.is_batch_mode:
            # Update batch mode settings with new resolution
            old_resolution = self.batch_manager.batch_settings.get('resolution', 'Unknown')
            self.batch_manager.update_batch_settings(resolution=new_resolution)
            self.log_manager.log("INFO", f"Batch mode resolution updated from '{old_resolution}' to '{new_resolution}'")
            
            # Update status to show the change
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            if status['queue_size'] > 0:
                self.ui.status_label.setText(f"Resolution updated to {new_resolution} - Queue: {status['queue_size']}/{queue_limit} items")
        else:
            self.log_manager.log("DEBUG", f"Resolution changed but batch mode not active")

    def on_resolution_activated(self, index):
        """Handle resolution selection from dropdown"""
        new_resolution = self.ui.resolution_box.currentText()
        self.log_manager.log("DEBUG", f"Resolution activated: '{new_resolution}' at index {index}")
        
        # Call the same handler as text change
        self.on_resolution_changed(new_resolution)

    def on_subtitle_changed(self, state):
        """Handle subtitle checkbox changes and update batch mode settings if needed"""
        if self.batch_manager.is_batch_mode:
            # Update batch mode settings with new subtitle preference
            self.batch_manager.update_batch_settings(download_subs=state == 2) # 2 means checked
            self.log_manager.log("INFO", f"Batch mode subtitle preference updated to: {state == 2}")
            
            # Update status to show the change
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            if status['queue_size'] > 0:
                self.ui.status_label.setText(f"Subtitle preference updated - Queue: {status['queue_size']}/{queue_limit} items")

    def clear_batch_queue(self):
        """Clear the batch queue and show notification"""
        self.batch_manager.clear_batch_queue()
        queue_limit = self.settings.get_max_concurrent_downloads()
        
        # Show notification that queue is cleared and space is available
        self.show_queue_space_available_notification(0, queue_limit)
        
        # Stop readiness glow if active
        try:
            self._stop_download_button_glow()
        except Exception:
            pass
        self.log_manager.log("INFO", "Batch queue cleared - space available for new URLs")

    def on_batch_status_changed(self, is_active):
        """Handle batch mode status changes"""
        if is_active:
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            
            if 'playlist' in status:
                playlist_title = status['playlist']['title']
                self.ui.status_label.setText(f"Batch mode: {playlist_title} - Queue: {status['queue_size']}/{queue_limit} items")
            else:
                self.ui.status_label.setText(f"Batch mode enabled - Queue: {status['queue_size']}/{queue_limit} items")
        else:
            # Ensure we show non-batch ready state
            try:
                self.reset_ui()
            except Exception:
                self.ui.status_label.setText("Batch mode disabled")

    def on_batch_progress_updated(self, current, total):
        """Handle batch progress updates"""
        self.ui.status_label.setText(f"Batch: Processing {current}/{total}")
        self.log_manager.log("PROGRESS", f"Batch progress: {current}/{total}")

    def on_queue_limit_reached(self, queue_size):
        """Handle queue limit reached with concise alert"""
        limit = self.settings.get_max_concurrent_downloads()
        
        # Create concise message box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Queue Limit Reached")
        
        # Create short, informative message
        message = f"""<b>Queue Limit Reached!</b>

You have reached the maximum number of items ({limit}) allowed in your batch queue.

<b>Options:</b>
• Start downloading to process the queue
• Clear some items to make space
• Increase the limit in Settings → Download Behavior

<b>Current: {queue_size}/{limit} items</b>"""
        
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add custom styling
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8fafc;
                color: #1e293b;
            }
            QMessageBox QLabel {
                color: #1e293b;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        
        # Show the message box
        msg_box.exec()
        
        # Update status with specific information
        self.ui.status_label.setText(f"Queue limit reached ({queue_size}/{limit}) - Check alert for options")
        self.log_manager.log("WARNING", f"Queue limit reached ({queue_size}/{limit}). User notified with options.")

    def on_queue_limit_warning(self, queue_size, limit):
        """Handle queue limit warning with concise information"""
        # Create concise warning message box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Queue Limit Warning")
        
        # Calculate remaining slots
        remaining = limit - queue_size
        
        # Create short, informative message
        message = f"""<b>Queue Limit Approaching</b>

You're getting close to your batch queue limit.

<b>Status:</b> {queue_size}/{limit} items ({remaining} slot{'s' if remaining > 1 else ''} remaining)

<b>Tip:</b> You can increase the limit in Settings → Download Behavior if needed."""
        
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add custom styling
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8fafc;
                color: #1e293b;
            }
            QMessageBox QLabel {
                color: #1e293b;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        
        # Show the message box
        msg_box.exec()
        
        # Update status with specific information
        self.ui.status_label.setText(f"Queue limit approaching: {queue_size}/{limit} items ({remaining} slots remaining)")
        self.log_manager.log("WARNING", f"Queue limit approaching: {queue_size}/{limit} items. User notified.")

    def show_queue_addition_notification(self, current_queue_size, queue_limit):
        """Shows a quick notification for successful URL addition to the queue."""
        # Calculate usage percentage
        usage_percent = int((current_queue_size / queue_limit) * 100)
        
        # Determine notification type based on usage
        if usage_percent >= 100:
            notification_text = f"Queue full! ({current_queue_size}/{queue_limit})"
        elif usage_percent >= 80:
            notification_text = f"URL added! Queue: {current_queue_size}/{queue_limit} (80% full)"
        else:
            notification_text = f"URL added! Queue: {current_queue_size}/{queue_limit}"
        
        # Log the addition
        self.log_manager.log("INFO", f"URL successfully added to batch queue. Status: {current_queue_size}/{queue_limit}")
        
        # Show a brief status update (the main status will be updated by the calling method)
        # This provides immediate feedback to the user

    def show_queue_space_available_notification(self, current_queue_size, queue_limit):
        """Shows a notification when queue space becomes available."""
        remaining_slots = queue_limit - current_queue_size
        
        if remaining_slots > 0:
            notification_text = f"Queue space available! ({remaining_slots} slot{'s' if remaining_slots > 1 else ''} free)"
            self.log_manager.log("INFO", f"Queue space available: {remaining_slots} slots free")
            
            # Update status to show available space
            self.ui.status_label.setText(f"Ready for more URLs - Queue: {current_queue_size}/{queue_limit} ({remaining_slots} free)")
        else:
            # Queue is full
            self.ui.status_label.setText(f"Queue full ({current_queue_size}/{queue_limit}) - Start downloads to free space")

    def on_url_detected(self, url):
        """Handle detected YouTube URL from autopaste"""
        self.log_manager.log("INFO", f"Auto-paste detected URL: {url[:50]}...")

        # Check if it's a playlist URL
        if self.batch_manager.is_playlist_url(url):
            # For playlists, always enable batch mode
            if not self.batch_checkbox.isChecked():
                self.batch_checkbox.setChecked(True)

            # Set the URL and let user decide when to process it
            self.ui.link_input.setText(url)
            self.ui.status_label.setText("Playlist URL detected - Click Download to process")
            # Emphasize readiness
            try:
                self._start_download_button_glow()
            except Exception:
                pass
            return

        # Handle regular video URLs as before
        if self.batch_manager.is_batch_mode:
            # Add to batch queue with limit checking
            queue_limit = self.settings.get_max_concurrent_downloads()
            if self.batch_manager.add_to_batch(url, queue_limit):
                status = self.batch_manager.get_batch_status()
                
                # Just update status without popup notification
                self.ui.status_label.setText(f"URL added to batch - Queue: {status['queue_size']}/{queue_limit}")
                self.ui.link_input.clear()  # Clear input for next URL

                # Auto-start if not currently downloading
                if not self.is_downloading:
                    self.start_batch_download()
            else:
                self.ui.status_label.setText("URL already in queue or invalid")
        else:
            # Normal mode - just paste the URL
            self.ui.link_input.setText(url)
            self.ui.status_label.setText("YouTube URL detected and pasted")

    def cancel_download(self):
        if hasattr(self, "thread") and self.thread.isRunning():
            self.ui.status_label.setText("Cancelling download...")
            try:
                if hasattr(self.ui, 'set_activity_state'):
                    self.ui.set_activity_state('idle')
            except Exception:
                pass
            self.log_manager.log("WARNING", "Download cancelled by user")
            self.thread.cancel()
            self.is_downloading = False
            # Clear top-right speed
            if hasattr(self.ui, 'set_speed_text'):
                self.ui.set_speed_text("")

    def start_download(self):
        """Start download - handles single videos, playlists, and batch mode"""
        url = self.ui.link_input.text().strip()

        # Check if it's a playlist URL first
        if url and self.batch_manager.is_playlist_url(url):
            # Ensure batch mode is enabled in UI before handling
            try:
                if hasattr(self, 'batch_checkbox') and not self.batch_checkbox.isChecked():
                    self.batch_checkbox.setChecked(True)
            except Exception:
                pass
            # Determine queue limit now
            try:
                queue_limit = self.settings.get_max_concurrent_downloads()
            except Exception:
                queue_limit = None
            # Handle playlist - this will auto-enable batch mode and add videos to queue
            if self.batch_manager.handle_playlist_url(url, queue_limit):
                return  # Playlist processing started, UI will be updated via signals
            else:
                self.ui.status_label.setText("Failed to process playlist URL")
                self.log_manager.log("ERROR", f"Failed to process playlist URL: {url}")
                return

        # Regular batch mode or single download logic
        if self.batch_manager.is_batch_mode:
            self.start_batch_download()
        else:
            self.start_single_download()

    def start_single_download(self):
        """Start a single download (normal mode)"""
        if self.is_downloading:
            return
        url = self.ui.link_input.text().strip()
        resolution = self.ui.resolution_box.currentText()
        download_subs = self.ui.subtitle_checkbox.isChecked()
        download_path = self.ui.path_input.text().strip()
        
        # Debug logging for resolution
        self.log_manager.log("DEBUG", f"Single download - UI resolution: '{resolution}', URL: {url[:50]}...")
        
        chosen_container = None
        chosen_audio = None
        try:
            if hasattr(self.ui, 'format_box') and self.ui.format_box.isVisible():
                chosen_container = self.ui.format_box.currentText().lower().strip()
            if hasattr(self.ui, 'audio_format_box') and self.ui.audio_format_box.isVisible():
                chosen_audio = self.ui.audio_format_box.currentText().lower().strip()
        except Exception:
            pass

        if not url:
            self.ui.status_label.setText("Please enter a link.")
            self.log_manager.log("WARNING", "Download attempted without URL")
            return

        # Disable the Download button during single-link download; keep Cancel enabled
        try:
            if hasattr(self.ui, 'download_button'):
                self.ui.download_button.setEnabled(False)
        except Exception:
            pass

        # Optional format chooser if enabled
        try:
            if hasattr(self.ui, 'choose_format_checkbox') and self.ui.choose_format_checkbox.isChecked():
                self.log_manager.log("DEBUG", f"Format chooser enabled, current resolution: '{resolution}'")
                # Pass active cookie file explicitly so chooser lists formats under same auth as downloads
                active_cookie = None
                try:
                    active_cookie = getattr(self, 'current_cookie_file', None)
                except Exception:
                    active_cookie = None
                dlg = FormatChooserDialog(url, self.ui, cookiefile=active_cookie)
                result = dlg.exec()
                if result:
                    chosen_res, chosen_container, chosen_audio = dlg.get_selection()
                    self.log_manager.log("DEBUG", f"Format chooser result: resolution='{chosen_res}', container='{chosen_container}', audio='{chosen_audio}'")
                    
                    # Accept any resolution like "<digits>p" (e.g., 2160p, 1440p, 240p) or the special "Audio"
                    try:
                        import re
                        is_audio = (chosen_res == "Audio")
                        is_height = isinstance(chosen_res, str) and re.match(r"^\d+p$", chosen_res or "") is not None
                    except Exception:
                        is_audio = (chosen_res == "Audio")
                        is_height = False

                    if chosen_res and (is_audio or is_height):
                        if chosen_res != resolution:
                            self.log_manager.log("INFO", f"Resolution changed from '{resolution}' to '{chosen_res}' via format chooser")
                        else:
                            self.log_manager.log("DEBUG", f"Resolution unchanged: '{resolution}'")
                        resolution = chosen_res
                    else:
                        self.log_manager.log("WARNING", f"Format chooser returned unrecognized resolution: '{chosen_res}', keeping original: '{resolution}'")
                    
                    # If proceed_with_defaults is True, we intentionally keep current settings
                else:
                    # Back pressed: abort starting download; wait for user
                    self.log_manager.log("DEBUG", "Format chooser cancelled by user")
                    try:
                        if hasattr(self.ui, 'download_button'):
                            self.ui.download_button.setEnabled(True)
                    except Exception:
                        pass
                    return
        except Exception as e:
            self.log_manager.log("DEBUG", f"Format chooser unavailable: {e}")

        # Log the final resolution being used
        self.log_manager.log("INFO", f"Starting download with resolution: '{resolution}'")

        # Store chosen_container (if any) for the next thread start
        self._chosen_container_override = chosen_container
        self._chosen_audio_override = chosen_audio
        self._start_download_with_settings(url, resolution, download_subs, download_path)

    def start_batch_download(self):
        """Start next item in batch queue"""
        if self.is_downloading:
            return
        # Hard guard: if user cancelled the playlist flow, do nothing until next explicit action
        if getattr(self, '_block_batch_after_cancel', False):
            self._block_batch_after_cancel = False
            return
        if not self.batch_manager.is_batch_mode:
            return

        # Add current URL to batch if there's one in the input
        current_url = self.ui.link_input.text().strip()
        # Avoid re-adding playlist URLs (prevents re-triggering extraction)
        if current_url and not self.batch_manager.is_playlist_url(current_url):
            queue_limit = self.settings.get_max_concurrent_downloads()
            if self.batch_manager.add_to_batch(current_url, queue_limit):
                self.ui.link_input.clear()

        # Get next item from batch
        next_item = self.batch_manager.get_next_batch_item()
        if next_item:
            # Stop glow since we are starting
            try:
                self._stop_download_button_glow()
            except Exception:
                pass
                
            # Log the batch item details for debugging
            self.log_manager.log("DEBUG", f"Batch download item: resolution='{next_item['resolution']}', subs={next_item['download_subs']}, path='{next_item['download_path']}'")
            
            # If choose-format is enabled, respect it only for manual single downloads; batch uses queued settings
            self._start_download_with_settings(
                next_item['url'],
                next_item['resolution'],
                next_item['download_subs'],
                next_item['download_path'],
                container_override=next_item.get('container_override'),
                audio_override=next_item.get('audio_override'),
            )
        else:
            # No more items in queue
            if self.batch_manager.is_batch_complete():
                self.complete_batch()
            else:
                status = self.batch_manager.get_batch_status()
                queue_limit = self.settings.get_max_concurrent_downloads()
                self.ui.status_label.setText(f"Batch ready - Queue: {status['queue_size']}/{queue_limit} items — Press Download to start")
                # Show readiness cue when items are queued but idle
                try:
                    if status.get('queue_size', 0) > 0 and not self.is_downloading:
                        self._start_download_button_glow()
                except Exception:
                    pass

    def _start_download_with_settings(self, url, resolution, download_subs, download_path, container_override=None, audio_override=None):
        """Start download with current settings"""
        # Get retry settings
        retry_count = self.settings.get_retry_attempts()
        retry_delay = self.settings.get_retry_delay()
        skip_existing = self.settings.get_skip_existing_files()
        auto_resume = self.settings.get_auto_resume_downloads()
        
        # Log download settings
        self.log_manager.log("INFO", f"Download settings - Retry: {retry_count}, Delay: {retry_delay}s, Skip existing: {skip_existing}, Auto-resume: {auto_resume}")
        
        # Start a new download session for history tracking
        try:
            self.log_manager.start_download_session(
                url=url,
                resolution=resolution,
                download_subs=download_subs,
                batch_mode=self.batch_manager.is_batch_mode
            )
        except Exception:
            pass
        
        # Create download thread
        self.thread = DownloadThread(
            url=url,
            resolution=resolution,
            download_subs=download_subs,
            download_path=download_path,
            log_manager=self.log_manager,
            preferred_container=(container_override or getattr(self, '_chosen_container_override', None))
        )
        
        # Log the thread creation for debugging
        self.log_manager.log("DEBUG", f"Download thread created with resolution: '{resolution}', subs: {download_subs}, path: '{download_path}'")
        
        # Clear single-download override after use
        if hasattr(self, '_chosen_container_override'):
            self._chosen_container_override = None
        # If audio-only selection carries a preferred audio format, update thread
        try:
            if resolution == "Audio":
                if audio_override:
                    self.thread.preferred_audio_format = str(audio_override).lower()
                elif getattr(self, '_chosen_audio_override', None):
                    self.thread.preferred_audio_format = str(self._chosen_audio_override).lower()
        except Exception:
            pass
        if hasattr(self, '_chosen_audio_override'):
            self._chosen_audio_override = None
        
        # Pass cookie file only if cookies are not disabled
        if not self.settings.get_disable_cookies() and self.current_cookie_file:
            cookie_path_to_use = None
            try:
                data = (self.current_cookie_file or "").strip()
                # If it's JSON data (pasted), convert to a temp netscape file
                if data.startswith('{') or data.startswith('['):
                    try:
                        from cookie_manager import CookieManager
                        cm = CookieManager()
                        temp_path = cm.convert_json_string_to_yt_dlp_format(data)
                        if temp_path and os.path.exists(temp_path):
                            cookie_path_to_use = temp_path
                    except Exception:
                        cookie_path_to_use = None
                # Otherwise, treat as file path
                else:
                    if os.path.exists(self.current_cookie_file):
                        cookie_path_to_use = self.current_cookie_file
            except Exception:
                cookie_path_to_use = None

            if cookie_path_to_use and os.path.exists(cookie_path_to_use):
                self.thread.cookie_file = cookie_path_to_use
                self.log_manager.log("INFO", f"Passing cookies to download thread: {cookie_path_to_use}")
            else:
                self.log_manager.log("INFO", f"Cookies disabled or not available. Disabled: {self.settings.get_disable_cookies()}, Cookie file: {self.current_cookie_file}")
        else:
            self.log_manager.log("INFO", f"Cookies disabled or not available. Disabled: {self.settings.get_disable_cookies()}, Cookie file: {self.current_cookie_file}")

        # Connect logging to thread signals
        self.thread.progress.connect(self.update_status_with_logging)
        self.thread.video_info.connect(self.update_video_info_with_logging)
        self.thread.download_progress.connect(self.update_download_progress)
        self.thread.retry_info.connect(self.update_retry_info)
        self.thread.download_failed.connect(self.on_download_failed)  # Handle failures
        self.thread.finished.connect(self.on_download_finished)
        
        # Connect progress signal to handle file already exists
        self.thread.progress.connect(self.handle_progress_status)

        # Use settings for pre-download delay instead of hardcoded values
        if self.settings.is_throttle_enabled():
            pre_min, pre_max = self.settings.get_pre_delay_range()
            pre_delay_ms = int(random.uniform(pre_min, pre_max) * 1000)
        else:
            pre_delay_ms = 1000  # Default 1 second if throttling disabled
            
        # Mark as downloading to prevent concurrent starts during pre-delay
        self.is_downloading = True
        
        # Set downloading animation state
        try:
            if hasattr(self.ui, 'set_activity_state'):
                self.ui.set_activity_state('downloading')
        except Exception:
            pass
        
        QTimer.singleShot(pre_delay_ms, self.thread.start)

    def update_status_with_logging(self, msg):
        """Update status with logging integration"""
        # Log the status update
        if "failed" in msg.lower() or "error" in msg.lower():
            self.log_manager.log("ERROR", msg)
        elif "complete" in msg.lower() or "finished" in msg.lower():
            self.log_manager.log("SUCCESS", msg)
        elif "downloading" in msg.lower() or "progress" in msg.lower():
            self.log_manager.log("PROGRESS", msg)
        else:
            self.log_manager.log("INFO", msg)

        # Update UI status
        self.update_status(msg)

    def update_video_info_with_logging(self, title, filesize):
        """Update video info with logging"""
        # Update log manager with video info
        self.log_manager.update_video_info(title, filesize)

        # Call original method
        self.update_video_info(title, filesize)

    def on_download_failed(self, error_message):
        """Handle download failure"""
        self.is_downloading = False
        try:
            if hasattr(self.ui, 'set_activity_state'):
                # If network-related, show retry animation briefly
                if any(k in (error_message or '').lower() for k in ['network', 'timeout', 'connection', 'temporarily unavailable']):
                    self.ui.set_activity_state('retrying')
                else:
                    self.ui.set_activity_state('idle')
        except Exception:
            pass
        # Re-enable Download button on failure in single mode
        try:
            if not self.batch_manager.is_batch_mode and hasattr(self.ui, 'download_button'):
                self.ui.download_button.setEnabled(True)
        except Exception:
            pass

        # Check if it's an authentication error
        if "Sign in to confirm you're not a bot" in error_message:
            self.handle_authentication_error()
            return

        if self.batch_manager.is_batch_mode:
            # Mark download as failed in batch mode
            self.batch_manager.mark_download_completed(success=False)

            # Use settings for failure delay instead of hardcoded values
            if self.settings.is_throttle_enabled():
                fail_min, fail_max = self.settings.get_between_failure_range()
                fail_delay_ms = int(random.uniform(fail_min, fail_max) * 1000)
            else:
                fail_delay_ms = 5000  # Default 5 seconds if throttling disabled
                
            # Continue with next item after delay
            if not self.batch_manager.is_batch_complete():
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(fail_delay_ms, self.start_batch_download)
            else:
                self.complete_batch()
        else:
            # Single download failed
            self.update_status(f"Download failed: {error_message}")
            self.reset_ui()

    def handle_authentication_error(self):
        """Handle YouTube authentication errors by prompting for cookies"""
        self.log_manager.log("DEBUG", "Authentication error handler triggered")
        
        # Check if cookies are disabled
        if self.settings.get_disable_cookies():
            self.log_manager.log("WARNING", "Authentication required but cookies are disabled")
            if self.batch_manager.is_batch_mode:
                # Mark as failed and continue with next item
                self.batch_manager.mark_download_completed(success=False)
                if not self.batch_manager.is_batch_complete():
                    from PyQt6.QtCore import QTimer
                    try:
                        if hasattr(self.ui, 'set_activity_state'):
                            self.ui.set_activity_state('retrying')
                    except Exception:
                        pass
                    QTimer.singleShot(5000, self.start_batch_download)
                else:
                    self.complete_batch()
            else:
                self.update_status("Download failed - authentication required (cookies disabled)")
                self.reset_ui()
                try:
                    if hasattr(self.ui, 'set_activity_state'):
                        self.ui.set_activity_state('retrying')
                except Exception:
                    pass
            return
        
        self.log_manager.log("WARNING", "YouTube authentication required - prompting for cookies")
        
        # Show cookie detection dialog
        cookie_file, browser_name = show_cookie_detection_dialog(self.ui)
        
        if cookie_file:
            self.log_manager.log("INFO", f"Cookies provided from {browser_name}")
            
            # Store cookie file for future downloads
            self.current_cookie_file = cookie_file
            self.current_cookie_browser = browser_name
            
            # Update UI to show cookies are active
            self.ui.update_cookie_status(True, browser_name, "User provided")
            
            # Retry the download with cookies
            if self.batch_manager.is_batch_mode:
                # Continue batch download with cookies
                self.start_batch_download()
            else:
                # Retry single download with cookies
                self.retry_download_with_cookies()
        else:
            # User cancelled cookie setup
            self.log_manager.log("INFO", "Cookie setup cancelled by user")
            if self.batch_manager.is_batch_mode:
                # Mark as failed and continue with next item
                self.batch_manager.mark_download_completed(success=False)
                if not self.batch_manager.is_batch_complete():
                    from PyQt6.QtCore import QTimer
                    try:
                        if hasattr(self.ui, 'set_activity_state'):
                            self.ui.set_activity_state('retrying')
                    except Exception:
                        pass
                    QTimer.singleShot(5000, self.start_batch_download)
                else:
                    self.complete_batch()
            else:
                self.update_status("Download cancelled - authentication required")
                self.reset_ui()

    def retry_download_with_cookies(self):
        """Retry the current download with cookies"""
        url = self.ui.link_input.text().strip()
        resolution = self.ui.resolution_box.currentText()
        download_subs = self.ui.subtitle_checkbox.isChecked()
        download_path = self.ui.path_input.text().strip()
        
        self._start_download_with_settings(url, resolution, download_subs, download_path)

    def on_download_finished(self):
        """Handle download completion with logging"""
        self.is_downloading = False
        try:
            if hasattr(self.ui, 'set_activity_state'):
                self.ui.set_activity_state('idle')
        except Exception:
            pass
        # Re-enable Download button on finish in single mode
        try:
            if not self.batch_manager.is_batch_mode and hasattr(self.ui, 'download_button'):
                self.ui.download_button.setEnabled(True)
        except Exception:
            pass

        # Complete the logging session (assuming success if we get here)
        download_path = getattr(self.thread, 'download_path', None)
        self.log_manager.complete_download_session(success=True, download_path=download_path)

        if self.batch_manager.is_batch_mode:
            # Mark download as completed (assume success if we get here)
            self.batch_manager.mark_download_completed(success=True)

            # Check if there are more items in batch
            if not self.batch_manager.is_batch_complete():
                # Use settings for success delay instead of hardcoded values
                if self.settings.is_throttle_enabled():
                    success_min, success_max = self.settings.get_between_success_range()
                    success_delay_ms = int(random.uniform(success_min, success_max) * 1000)
                else:
                    success_delay_ms = 3000  # Default 3 seconds if throttling disabled
                    
                # Show completion status before continuing
                self.ui.status_label.setText("Download completed successfully! Starting next item...")
                
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(success_delay_ms, self.start_batch_download)
            else:
                self.complete_batch()
        else:
            # Normal single download completion - show success message for a moment
            self.ui.status_label.setText("Download completed successfully!")
            
            # Wait a moment before resetting to "Ready" state
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, self.reset_ui)
        # Clear top-right speed when done
        if hasattr(self.ui, 'set_speed_text'):
            self.ui.set_speed_text("")

    def complete_batch(self):
        """Complete batch processing and show summary"""
        summary = self.batch_manager.get_batch_summary()
        self.log_manager.log("SUCCESS", f"Batch completed: {summary.get('successful', 0)} downloads successful")

        # Reset UI
        self.reset_ui()

        # Keep batch mode enabled but clear queue
        self.batch_manager.clear_batch_queue()
        status = self.batch_manager.get_batch_status()
        queue_limit = self.settings.get_max_concurrent_downloads()

        # Show notification that space is available after batch completion ONLY if 100% done
        if summary.get('completion_rate', 0) >= 100:
            self.show_queue_space_available_notification(status['queue_size'], queue_limit)
            self.log_manager.log("SUCCESS", f"Batch completed: {summary.get('successful', 0)} downloads successful. Queue space available.")

    def update_status(self, msg):
        # Add batch info to status if in batch mode
        if self.batch_manager.is_batch_mode:
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            
            if status['queue_size'] > 0:
                # Determine color based on queue usage
                queue_usage = status['queue_size'] / queue_limit
                # No emoji indicators
                color_indicator = ""
                
                # Calculate remaining items in queue
                remaining_items = status['queue_size'] - status['current_index']
                
                if 'playlist' in status:
                    playlist_title = status['playlist']['title']
                    # Format: [Playlist: Current/Total - Title] Queue: Items/Limit
                    batch_info = f" {color_indicator} [Playlist: {status['current_index']}/{status['queue_size']} - {playlist_title}] Queue: {status['queue_size']}/{queue_limit}"
                else:
                    # Format: [Batch: Current/Total] Queue: Items/Limit
                    batch_info = f" {color_indicator} [Batch: {status['current_index']}/{status['queue_size']}] Queue: {status['queue_size']}/{queue_limit}"
                
                self.ui.status_label.setText(msg + batch_info)
            else:
                self.ui.status_label.setText(msg)
        else:
            self.ui.status_label.setText(msg)

    def update_video_info(self, title, filesize):
        # Store total file size for progress calculation
        if isinstance(filesize, str) and 'MB' in filesize:
            try:
                # Extract numeric value from filesize string (e.g., "125.5 MB")
                size_str = filesize.replace(' MB', '').replace(' GB', '')
                if 'GB' in filesize:
                    self.total_file_size = float(size_str) * 1024  # Convert GB to MB
                else:
                    self.total_file_size = float(size_str)
            except:
                self.total_file_size = 0

        # Update UI with downloaded size (initially 0)
        self.ui.update_video_details(filename=title, filesize="0 MB")

    def update_download_progress(self, percentage, speed=""):
        """Update download progress with downloaded file size"""
        try:
            if hasattr(self.ui, 'set_activity_state'):
                self.ui.set_activity_state('downloading')
        except Exception:
            pass
        # Build display text combining percentage and speed for visibility
        if isinstance(percentage, str) and '%' in percentage:
            progress_text = f"{percentage}"
        else:
            progress_text = f"{percentage}%" if isinstance(percentage, (int, float)) else ""
        display_text = progress_text

        # Update speed label in MB/s (consistent with settings)
        def format_speed(speed_str: str) -> str:
            if not speed_str:
                return ""
            s = speed_str.strip().replace(" ", "")
            try:
                # Normalize binary units to decimal-like labels and keep adaptive units
                if "GiB/s" in s:
                    val = float(s.split("GiB/s")[0])
                    return f"{val:.2f} GB/s"
                if "MiB/s" in s:
                    val = float(s.split("MiB/s")[0])
                    return f"{val:.1f} MB/s"
                if "KiB/s" in s:
                    val = float(s.split("KiB/s")[0])
                    return f"{val:.0f} KB/s"
                if "GB/s" in s:
                    val = float(s.split("GB/s")[0])
                    return f"{val:.2f} GB/s"
                if "MB/s" in s:
                    val = float(s.split("MB/s")[0])
                    return f"{val:.1f} MB/s"
                if "KB/s" in s:
                    val = float(s.split("KB/s")[0])
                    return f"{val:.0f} KB/s"
                if "B/s" in s:
                    val = float(s.split("B/s")[0])
                    return f"{int(val)} B/s"
                return s
            except Exception:
                return s

        self.ui.set_speed_text(format_speed(speed))

        # Log progress updates periodically
        if isinstance(percentage, str) and '%' in percentage:
            try:
                progress_num = float(percentage.replace('%', ''))
                # Log every 10% progress
                if progress_num % 10 == 0:
                    self.log_manager.update_download_progress(percentage, speed)
            except:
                pass

        # Calculate downloaded size based on percentage (parse string if needed)
        progress_value = None
        if isinstance(percentage, (int, float)):
            progress_value = float(percentage)
        elif isinstance(percentage, str) and '%' in percentage:
            try:
                progress_value = float(percentage.replace('%', ''))
            except:
                progress_value = None

        if self.total_file_size > 0 and isinstance(progress_value, float):
            self.downloaded_size = (progress_value / 100.0) * self.total_file_size

            # Format downloaded size
            if self.downloaded_size >= 1024:  # >= 1 GB
                downloaded_size_text = f"{self.downloaded_size / 1024:.1f} GB"
            else:
                downloaded_size_text = f"{self.downloaded_size:.1f} MB"

            # Update UI with downloaded size
            self.ui.update_video_details(filesize=downloaded_size_text, progress=display_text)
        else:
            # Fallback to just showing speed
            self.ui.update_video_details(progress=display_text)

    def update_retry_info(self, retry_status):
        """Handle retry status updates with logging"""
        self.log_manager.log("WARNING", f"Retry attempt: {retry_status}")
        self.ui.update_video_details(progress=f"{retry_status}")
        try:
            if hasattr(self.ui, 'set_activity_state'):
                self.ui.set_activity_state('retrying')
        except Exception:
            pass

    def handle_progress_status(self, status_msg):
        """Handle progress status messages including file already exists"""
        if "File already exists" in status_msg:
            # Extract filename from status message
            if ":" in status_msg:
                filename = status_msg.split(":", 1)[1].strip()
                # Show the file already downloaded message for a moment
                self.ui.show_file_already_downloaded(filename, duration=4000, offer_open=True)
            else:
                # Fallback if we can't extract filename
                self.ui.show_file_already_downloaded("Unknown file", duration=4000)

    def reset_ui(self):
        if not self.batch_manager.is_batch_mode or self.batch_manager.is_batch_complete():
            self.ui.link_input.clear()

        self.ui.download_button.setEnabled(True)
        
        # Re-enable all input controls
        self.ui.resolution_box.setEnabled(True)
        self.ui.subtitle_checkbox.setEnabled(True)
        self.ui.path_input.setEnabled(True)
        self.ui.browse_button.setEnabled(True)
        
        # Update batch mode settings if active
        if self.batch_manager.is_batch_mode:
            self.update_batch_mode_from_ui()
        
        # Show better status information instead of just "Ready"
        if self.batch_manager.is_batch_mode:
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            if status['queue_size'] > 0:
                self.ui.status_label.setText(f"Ready for next download - Queue: {status['queue_size']}/{queue_limit} items")
            else:
                self.ui.status_label.setText("Ready for new URLs - Batch mode active")
        else:
            self.ui.status_label.setText("Ready to download - Enter YouTube URL")
            
        self.ui.reset_video_details()

        # Reset file size tracking
        self.total_file_size = 0
        self.downloaded_size = 0
        # Clear top-right speed on reset
        if hasattr(self.ui, 'set_speed_text'):
            self.ui.set_speed_text("")

    def start_download_with_settings(self, url, resolution, download_subs, download_path):
        """Public method for external use (e.g., batch integration)"""
        self._start_download_with_settings(url, resolution, download_subs, download_path)

    def initialize_cookies(self):
        """Initialize cookie management on startup"""
        self.refresh_cookie_status()

    def refresh_cookie_status(self):
        """Refresh cookie status based on current settings"""
        try:
            # Check if cookies are disabled
            if self.settings.get_disable_cookies():
                self.log_manager.log("INFO", "Cookies disabled by user setting")
                self.ui.update_cookie_status(False, status_details="Disabled by user")
                self.current_cookie_file = None
                self.current_cookie_browser = None
                return
            
            # Check if auto-detect is enabled
            if self.settings.get_auto_detect_cookies():
                self.log_manager.log("INFO", "Auto-detecting browser cookies...")
                
                # Try to auto-detect cookies with preferred browser
                preferred_browser = self.settings.get_preferred_browser()
                self.log_manager.log("DEBUG", f"Preferred browser: {preferred_browser}")
                
                cookie_file, browser_name = auto_detect_cookies(preferred_browser)
                self.log_manager.log("DEBUG", f"Auto-detect result: cookie_file={cookie_file}, browser_name={browser_name}")
                
                if cookie_file:
                    self.current_cookie_file = cookie_file
                    self.current_cookie_browser = browser_name
                    self.log_manager.log("INFO", f"Auto-detected cookies from {browser_name}")
                    # Update UI to show cookies are active with browser name
                    self.ui.update_cookie_status(True, browser_name, "Auto-detected")
                    # Force UI update
                    self.ui.status_label.setText(f"🔓 Cookies detected from {browser_name}")
                    self.log_manager.log("SUCCESS", f"Cookie status updated: {browser_name} (Auto-detected)")
                else:
                    self.log_manager.log("INFO", "No cookies auto-detected")
                    self.ui.update_cookie_status(False, status_details="Auto-detect failed")
                    self.current_cookie_file = None
                    self.current_cookie_browser = None
            else:
                # Auto-detect is disabled, check manual cookie file
                manual_cookie_file = self.settings.get_cookie_file_path()
                if manual_cookie_file and os.path.exists(manual_cookie_file):
                    if test_cookies(manual_cookie_file):
                        self.current_cookie_file = manual_cookie_file
                        self.current_cookie_browser = "Manual"
                        self.log_manager.log("INFO", f"Using manual cookie file: {manual_cookie_file}")
                        # Update UI to show cookies are active
                        self.ui.update_cookie_status(True, "Manual", "File loaded")
                    else:
                        self.log_manager.log("WARNING", "Manual cookie file is invalid")
                        self.ui.update_cookie_status(False, status_details="Invalid file")
                        self.current_cookie_file = None
                        self.current_cookie_browser = None
                else:
                    # Check for JSON cookie file
                    json_cookie_file = self.settings.get_json_cookie_file_path()
                    if json_cookie_file and os.path.exists(json_cookie_file):
                        if test_cookies(json_cookie_file):
                            self.current_cookie_file = json_cookie_file
                            self.current_cookie_browser = "JSON"
                            self.log_manager.log("INFO", f"Using JSON cookie file: {json_cookie_file}")
                            # Update UI to show cookies are active
                            self.ui.update_cookie_status(True, "JSON", "File loaded")
                        else:
                            self.log_manager.log("WARNING", "JSON cookie file is invalid")
                            self.ui.update_cookie_status(False, status_details="Invalid JSON file")
                            self.current_cookie_file = None
                            self.current_cookie_browser = None
                    else:
                        # Check if JSON cookie input contains pasted data
                        json_cookie_data = self.settings.get_json_cookie_file_path()
                        if json_cookie_data and (json_cookie_data.strip().startswith('{') or json_cookie_data.strip().startswith('[')):
                            if test_cookies(json_cookie_data):
                                self.current_cookie_file = json_cookie_data
                                self.current_cookie_browser = "Pasted JSON"
                                self.log_manager.log("INFO", "Using pasted JSON cookie data")
                                # Update UI to show cookies are active
                                self.ui.update_cookie_status(True, "Pasted JSON", "Data loaded")
                            else:
                                self.log_manager.log("WARNING", "Pasted JSON cookie data is invalid")
                                self.ui.update_cookie_status(False, status_details="Invalid pasted JSON")
                                self.current_cookie_file = None
                                self.current_cookie_browser = None
                        else:
                            self.log_manager.log("INFO", "No manual, JSON file, or pasted JSON data set")
                            self.ui.update_cookie_status(False, status_details="No data set")
                    self.current_cookie_file = None
                    self.current_cookie_browser = None
            
            # After updating status, provide a gentle expiry hint if we have cookies
            try:
                if getattr(self, 'current_cookie_file', None):
                    from cookie_manager import CookieManager
                    cm = CookieManager()
                    expiry = cm.get_cookie_expiry(self.current_cookie_file)
                    if expiry:
                        import time
                        seconds_left = max(0, int(expiry - time.time()))
                        days_left = seconds_left // 86400
                        if days_left <= 3:
                            self.ui.status_label.setText(f"Cookies expiring soon (~{days_left}d). Consider refreshing.")
                            self.log_manager.log("WARNING", f"Cookies expiring in ~{days_left} day(s)")
            except Exception:
                pass
                    
        except Exception as e:
            self.log_manager.log("ERROR", f"Cookie status refresh failed: {str(e)}")
            self.ui.update_cookie_status(False, status_details="Error occurred")
            self.current_cookie_file = None
            self.current_cookie_browser = None

    def test_current_cookies(self):
        """Test the current cookies and show status"""
        try:
            if not self.current_cookie_file:
                self.ui.update_cookie_status(False, status_details="No cookies to test")
                return
                
            if test_cookies(self.current_cookie_file):
                # Get browser name from current cookie file
                browser_name = "Unknown"
                if hasattr(self, 'current_cookie_browser'):
                    browser_name = self.current_cookie_browser
                elif "chrome" in self.current_cookie_file.lower():
                    browser_name = "Chrome"
                elif "firefox" in self.current_cookie_file.lower():
                    browser_name = "Firefox"
                elif "brave" in self.current_cookie_file.lower():
                    browser_name = "Brave"
                elif self.current_cookie_file.lower().endswith('.json'):
                    browser_name = "JSON"
                else:
                    browser_name = "Manual"
                
                self.ui.update_cookie_status(True, browser_name, "Test passed")
                self.log_manager.log("SUCCESS", "Cookie test passed")
            else:
                self.ui.update_cookie_status(False, status_details="Test failed")
                self.log_manager.log("WARNING", "Cookie test failed")
                
        except Exception as e:
            self.log_manager.log("ERROR", f"Cookie test failed: {str(e)}")
            self.ui.update_cookie_status(False, status_details="Test error")

    def _start_download_button_glow(self):
        """Begin a subtle glow animation on the Download button to indicate readiness."""
        try:
            if not hasattr(self.ui, 'download_button') or self.ui.download_button is None:
                return
            # If already running, do nothing
            anim = getattr(self, '_dl_glow_anim', None)
            if anim and anim.state() == QPropertyAnimation.Running:
                return
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            effect = QGraphicsDropShadowEffect()
            effect.setXOffset(0)
            effect.setYOffset(0)
            # Stronger, smoother glow
            effect.setBlurRadius(28)

            # Pick base color per theme and lighten it slightly
            try:
                from theme import get_palette, get_current_theme_key, Theme
                p = get_palette()
                key = get_current_theme_key()
                # Explicit per-theme base color to mirror the button color
                if key == Theme.YOUTUBE or getattr(key, 'name', str(key)) == 'YOUTUBE':
                    base_hex = '#ff0000'  # YouTube red
                    alpha = 205
                    lighten_factor = 0.35
                elif key == Theme.DARK or getattr(key, 'name', str(key)) == 'DARK':
                    base_hex = '#22c55e'  # Dark: green
                    alpha = 190
                    lighten_factor = 0.28
                else:
                    base_hex = '#6366f1'  # Default: blue
                    alpha = 175
                    lighten_factor = 0.30
                # Fallback to palette if available
                try:
                    if key == Theme.YOUTUBE:
                        base_hex = p.get('primary', base_hex)
                    elif key == Theme.DARK:
                        base_hex = p.get('success', base_hex)
                    else:
                        base_hex = p.get('primary', base_hex)
                except Exception:
                    pass
                col = QColor(base_hex)
                # Lighten toward white a bit
                try:
                    r, g, b = col.red(), col.green(), col.blue()
                    r = int(r + (255 - r) * lighten_factor)
                    g = int(g + (255 - g) * lighten_factor)
                    b = int(b + (255 - b) * lighten_factor)
                    col = QColor(r, g, b)
                except Exception:
                    pass
                col.setAlpha(alpha)
            except Exception:
                col = QColor('#6366f1')
                col.setAlpha(175)

            effect.setColor(col)
            self.ui.download_button.setGraphicsEffect(effect)

            anim = QPropertyAnimation(effect, b"blurRadius", self.ui)
            anim.setDuration(1200)
            anim.setStartValue(20.0)
            anim.setEndValue(58.0)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)
            anim.start()
            self._dl_glow_effect = effect
            self._dl_glow_anim = anim
        except Exception:
            pass

    def _stop_download_button_glow(self):
        """Stop the glow animation and clear effect from the Download button."""
        try:
            anim = getattr(self, '_dl_glow_anim', None)
            if anim:
                anim.stop()
                self._dl_glow_anim = None
            if hasattr(self, 'ui') and hasattr(self.ui, 'download_button') and self.ui.download_button:
                # Only clear if we set it
                if getattr(self, '_dl_glow_effect', None):
                    self.ui.download_button.setGraphicsEffect(None)
                    self._dl_glow_effect = None
        except Exception:
            pass

    def on_download_path_changed(self, new_path):
        """Handle changes to the download path and update batch mode settings"""
        if self.batch_manager.is_batch_mode:
            # Update batch mode settings with new download path
            self.batch_manager.update_batch_settings(download_path=new_path)
            self.log_manager.log("INFO", f"Batch mode download path updated to: {new_path}")
            
            # Update status to show the change
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            if status['queue_size'] > 0:
                self.ui.status_label.setText(f"Download path updated - Queue: {status['queue_size']}/{queue_limit} items")

    def update_batch_mode_from_ui(self):
        """Manually update batch mode settings from current UI values"""
        if self.batch_manager.is_batch_mode:
            current_res = self.ui.resolution_box.currentText()
            current_subs = self.ui.subtitle_checkbox.isChecked()
            current_path = self.ui.path_input.text().strip()
            
            self.log_manager.log("DEBUG", f"Manually updating batch mode: resolution='{current_res}', subs={current_subs}, path='{current_path}'")
            
            self.batch_manager.update_batch_settings(
                resolution=current_res,
                download_subs=current_subs,
                download_path=current_path
            )
            
            self.log_manager.log("INFO", f"Batch mode settings manually updated")
            
            # Update status
            status = self.batch_manager.get_batch_status()
            queue_limit = self.settings.get_max_concurrent_downloads()
            if status['queue_size'] > 0:
                self.ui.status_label.setText(f"Settings updated - Queue: {status['queue_size']}/{queue_limit} items")

    def start_update_dialog(self):
        """Open the full updater dialog and let user start the process."""
        try:
            if UPDATER_AVAILABLE:
                # Prefer pre-created dialog if available
                if hasattr(self, '_updater_dialog') and self._updater_dialog is not None:
                    try:
                        self._updater_dialog.show()
                        self._updater_dialog.raise_()
                        self._updater_dialog.activateWindow()
                    except Exception:
                        self._updater_dialog.exec()
                else:
                    show_updater_dialog(self.ui, install_dir="./bin")
                # After updater dialog closes, keep it 1-click by arming the button again
                if hasattr(self.ui, 'update_button') and self.ui.update_button:
                    try:
                        self.ui.update_button.setToolTip("Check for updates")
                    except Exception:
                        pass
                # Re-check and arm so the next click opens immediately
                try:
                    QTimer.singleShot(300, lambda: self.check_and_show_update_warning(arm_button=True))
                except Exception:
                    pass
            else:
                QMessageBox.information(self.ui, "Updater", "Updater module not available.")
        except Exception as e:
            try:
                QMessageBox.critical(self.ui, "Updater", f"Failed to start updater: {e}")
            except Exception:
                pass
        finally:
            # Safety: ensure state/text isn't stuck
            if hasattr(self.ui, 'update_button') and self.ui.update_button:
                try:
                    self.ui.update_button.setToolTip("Check for updates")
                except Exception:
                    pass
            self._updates_ready = False


if __name__ == "__main__":
    # Check and install dependencies for the updater
    if UPDATER_AVAILABLE:
        check_and_install_dependencies()

    app = QApplication(sys.argv)
    # Apply theme from settings
    try:
        from settings import AppSettings
        from theme import apply_theme, Theme
        _s = AppSettings()
        theme_name = str(_s._qs.value("ui/theme", "Default"))
        if theme_name == "YouTube":
            theme_key = Theme.YOUTUBE
        elif theme_name == "Dark":
            theme_key = Theme.DARK
        else:
            theme_key = Theme.DEFAULT
        apply_theme(app, theme_key)
    except Exception:
        pass
    
    # Set application properties
    app.setApplicationName("YouTube Downloader")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("YTDownloader")
    
    # Direct startup without splash screen
    controller = EnhancedController()
    try:
        if hasattr(controller.ui, 'apply_theme_styles'):
            controller.ui.apply_theme_styles()
    except Exception:
        pass
    controller.ui.show()
    # Defer potentially heavy cookie initialization until after the UI is responsive
    try:
        QTimer.singleShot(600, controller.initialize_cookies)
    except Exception:
        pass
    sys.exit(app.exec())