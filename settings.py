from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QFrame, QTextEdit, QGroupBox, QScrollArea, QWidget, QLineEdit, QComboBox, QFileDialog
)
from PyQt6.QtCore import QSettings, Qt, QDir, QSize
from PyQt6.QtGui import QPalette, QColor, QFont
from cookie_manager import show_cookies_dialog
import os


class AppSettings:
    """Typed accessors for application settings using QSettings."""

    ORG = "YTDownloader"
    APP = "App"

    def __init__(self):
        self._qs = QSettings(AppSettings.ORG, AppSettings.APP)

    # Throttling master switch
    def is_throttle_enabled(self) -> bool:
        return self._qs.value("throttle/enabled", True, bool)

    def set_throttle_enabled(self, enabled: bool) -> None:
        self._qs.setValue("throttle/enabled", enabled)

    # Rate limit MB/s
    def get_rate_limit_mbps(self) -> int:
        return int(self._qs.value("throttle/rate_limit_mb", 20))

    def set_rate_limit_mbps(self, mbps: int) -> None:
        self._qs.setValue("throttle/rate_limit_mb", int(mbps))

    def get_rate_limit_bytes(self) -> int:
        return max(0, self.get_rate_limit_mbps()) * 1024 * 1024

    # Pre-download delay (seconds)
    def get_pre_delay_range(self) -> tuple[float, float]:
        min_s = float(self._qs.value("throttle/pre_delay_min", 1.5))
        max_s = float(self._qs.value("throttle/pre_delay_max", 3.5))
        return min_s, max_s

    def set_pre_delay_range(self, min_s: float, max_s: float) -> None:
        self._qs.setValue("throttle/pre_delay_min", float(min_s))
        self._qs.setValue("throttle/pre_delay_max", float(max_s))

    # Between-item delays (seconds)
    def get_between_success_range(self) -> tuple[float, float]:
        min_s = float(self._qs.value("throttle/success_min", 3.0))
        max_s = float(self._qs.value("throttle/success_max", 7.0))
        return min_s, max_s

    def set_between_success_range(self, min_s: float, max_s: float) -> None:
        self._qs.setValue("throttle/success_min", float(min_s))
        self._qs.setValue("throttle/success_max", float(max_s))

    def get_between_failure_range(self) -> tuple[float, float]:
        min_s = float(self._qs.value("throttle/failure_min", 5.0))
        max_s = float(self._qs.value("throttle/failure_max", 12.0))
        return min_s, max_s

    def set_between_failure_range(self, min_s: float, max_s: float) -> None:
        self._qs.setValue("throttle/failure_min", float(min_s))
        self._qs.setValue("throttle/failure_max", float(max_s))

    # Request sleep and fragment concurrency
    def get_request_sleep(self) -> tuple[int, int, int, int, int]:
        sleep_interval = int(self._qs.value("throttle/sleep_interval", 2))
        max_sleep_interval = int(self._qs.value("throttle/max_sleep_interval", 5))
        sleep_requests = int(self._qs.value("throttle/sleep_requests", 1))
        max_sleep_requests = int(self._qs.value("throttle/max_sleep_requests", 3))
        concurrent_fragments = int(self._qs.value("throttle/concurrent_fragments", 1))
        return sleep_interval, max_sleep_interval, sleep_requests, max_sleep_requests, concurrent_fragments

    def set_request_sleep(self, sleep_interval: int, max_sleep_interval: int,
                          sleep_requests: int, max_sleep_requests: int, concurrent_fragments: int) -> None:
        self._qs.setValue("throttle/sleep_interval", int(sleep_interval))
        self._qs.setValue("throttle/max_sleep_interval", int(max_sleep_interval))
        self._qs.setValue("throttle/sleep_requests", int(sleep_requests))
        self._qs.setValue("throttle/max_sleep_requests", int(max_sleep_requests))
        self._qs.setValue("throttle/concurrent_fragments", int(concurrent_fragments))

    # General Application Settings
    def get_default_download_path(self) -> str:
        return str(self._qs.value("general/default_download_path", ""))

    def set_default_download_path(self, path: str) -> None:
        self._qs.setValue("general/default_download_path", str(path))

    def get_default_resolution(self) -> str:
        return str(self._qs.value("general/default_resolution", "720p"))

    def set_default_resolution(self, resolution: str) -> None:
        self._qs.setValue("general/default_resolution", str(resolution))

    def get_auto_download_subs(self) -> bool:
        return self._qs.value("general/auto_download_subs", False, bool)

    def set_auto_download_subs(self, enabled: bool) -> None:
        self._qs.setValue("general/auto_download_subs", enabled)

    def get_auto_clear_input(self) -> bool:
        return self._qs.value("general/auto_clear_input", True, bool)

    def set_auto_clear_input(self, enabled: bool) -> None:
        self._qs.setValue("general/auto_clear_input", enabled)

    def get_show_notifications(self) -> bool:
        return self._qs.value("general/show_notifications", True, bool)

    def set_show_notifications(self, enabled: bool) -> None:
        self._qs.setValue("general/show_notifications", enabled)

    def get_auto_check_updates(self) -> bool:
        return self._qs.value("general/auto_check_updates", True, bool)

    def set_auto_check_updates(self, enabled: bool) -> None:
        self._qs.setValue("general/auto_check_updates", enabled)

    def get_remember_window_size(self) -> bool:
        return self._qs.value("general/remember_window_size", True, bool)

    def set_remember_window_size(self, enabled: bool) -> None:
        self._qs.setValue("general/remember_window_size", enabled)

    def get_window_size(self) -> tuple[int, int]:
        width = int(self._qs.value("general/window_width", 800))
        height = int(self._qs.value("general/window_height", 600))
        return width, height

    def set_window_size(self, width: int, height: int) -> None:
        self._qs.setValue("general/window_width", int(width))
        self._qs.setValue("general/window_height", int(height))

    def get_theme(self) -> str:
        return str(self._qs.value("general/theme", "light"))

    def set_theme(self, theme: str) -> None:
        self._qs.setValue("general/theme", str(theme))

    def get_language(self) -> str:
        return str(self._qs.value("general/language", "en"))

    def set_language(self, language: str) -> None:
        self._qs.setValue("general/language", str(language))

    # Format Settings
    def get_preferred_video_format(self) -> str:
        return str(self._qs.value("format/preferred_video", "mp4"))

    def set_preferred_video_format(self, format: str) -> None:
        self._qs.setValue("format/preferred_video", str(format))

    def get_preferred_audio_format(self) -> str:
        return str(self._qs.value("format/preferred_audio", "m4a"))

    def set_preferred_audio_format(self, format: str) -> None:
        self._qs.setValue("format/preferred_audio", str(format))

    def get_audio_quality(self) -> str:
        return str(self._qs.value("format/audio_quality", "192k"))

    def set_audio_quality(self, quality: str) -> None:
        self._qs.setValue("format/audio_quality", str(quality))

    # Download Behavior Settings
    def get_retry_attempts(self) -> int:
        return int(self._qs.value("download/retry_attempts", 3))

    def set_retry_attempts(self, attempts: int) -> None:
        self._qs.setValue("download/retry_attempts", max(0, min(10, int(attempts))))

    def get_retry_delay(self) -> int:
        return int(self._qs.value("download/retry_delay", 5))

    def set_retry_delay(self, delay: int) -> None:
        self._qs.setValue("download/retry_delay", max(1, min(60, int(delay))))

    def get_skip_existing_files(self) -> bool:
        return self._qs.value("download/skip_existing_files", True, bool)

    def set_skip_existing_files(self, enabled: bool) -> None:
        self._qs.setValue("download/skip_existing_files", bool(enabled))

    def get_max_concurrent_downloads(self) -> int:
        return int(self._qs.value("download/max_concurrent_downloads", 3))

    def set_max_concurrent_downloads(self, max_downloads: int) -> None:
        self._qs.setValue("download/max_concurrent_downloads", max(1, min(10, int(max_downloads))))

    def get_auto_resume_downloads(self) -> bool:
        return self._qs.value("download/auto_resume_downloads", True, bool)

    def set_auto_resume_downloads(self, enabled: bool) -> None:
        self._qs.setValue("download/auto_resume_downloads", bool(enabled))

    # Cookie Settings
    def get_cookie_file_path(self) -> str:
        return str(self._qs.value("cookies/file_path", ""))

    def set_cookie_file_path(self, path: str) -> None:
        self._qs.setValue("cookies/file_path", str(path))

    def get_auto_detect_cookies(self) -> bool:
        return self._qs.value("cookies/auto_detect", True, bool)

    def set_auto_detect_cookies(self, enabled: bool) -> None:
        self._qs.setValue("cookies/auto_detect", bool(enabled))

    def get_disable_cookies(self) -> bool:
        return self._qs.value("cookies/disable_cookies", False, bool)

    def set_disable_cookies(self, enabled: bool) -> None:
        self._qs.setValue("cookies/disable_cookies", bool(enabled))

    def get_preferred_browser(self) -> str:
        return str(self._qs.value("cookies/preferred_browser", "chrome"))

    def set_preferred_browser(self, browser: str) -> None:
        self._qs.setValue("cookies/preferred_browser", str(browser))

    # New: Save playlists to subfolder
    def get_save_playlists_to_subfolder(self) -> bool:
        return self._qs.value("download/save_playlists_to_subfolder", True, bool)

    def set_save_playlists_to_subfolder(self, enabled: bool) -> None:
        self._qs.setValue("download/save_playlists_to_subfolder", bool(enabled))

    def get_json_cookie_file_path(self) -> str:
        return str(self._qs.value("cookies/json_file_path", ""))

    def set_json_cookie_file_path(self, path: str) -> None:
        self._qs.setValue("cookies/json_file_path", str(path))


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 600)
        
        # Apply palette-driven styling (supports dark/default/youtube)
        try:
            from theme import get_palette
            _p = get_palette()
            self.setStyleSheet(f"""
                QDialog {{ background-color: {_p['surface']}; color: {_p['text']}; }}
                QLabel {{ color: {_p['text']}; font-size: 12px; }}
                QGroupBox {{ font-weight: bold; font-size: 13px; color: {_p['text']}; border: 1px solid {_p['border']}; border-radius: 8px; margin-top: 12px; padding-top: 8px; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 8px 0 8px; background-color: {_p['surface']}; }}
                QCheckBox {{ color: {_p['text']}; font-size: 12px; spacing: 8px; padding: 4px 0px; }}
                QCheckBox::indicator {{ width: 18px; height: 18px; }}
                QCheckBox::indicator:unchecked {{ border: 2px solid {_p['border']}; background-color: {_p['surface']}; border-radius: 4px; }}
                QCheckBox::indicator:checked {{ border: 2px solid {_p['primary']}; background-color: {_p['primary']}; border-radius: 4px; }}
                /* Slightly heavier borders for dropdowns and spin boxes */
                QSpinBox, QDoubleSpinBox, QComboBox {{ color: {_p['text']}; background-color: {_p['surface']}; border: 2px solid {_p['border']}; border-radius: 6px; padding: 6px 10px; font-size: 12px; min-height: 20px; }}
                /* Keep line edits lighter */
                QLineEdit {{ color: {_p['text']}; background-color: {_p['surface']}; border: 1px solid {_p['border']}; border-radius: 6px; padding: 6px 10px; font-size: 12px; min-height: 20px; }}
                QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{ border-color: {_p['primary']}; outline: none; }}
                QComboBox::drop-down {{ border: none; width: 20px; }}
                QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid {_p['text']}; margin-right: 5px; }}
                QScrollArea {{ border: none; background-color: transparent; }}
                QWidget#scrollContent {{ background-color: transparent; }}
            """)
        except Exception:
            pass
        
        # Store original values to restore if reset is cancelled
        self.original_values = {}
        

        self._settings = AppSettings()
        self._setup_ui()
        try:
            self._apply_theme_styles()
        except Exception:
            pass

    def _setup_ui(self):
        """Setup the improved UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header with title and info button
        header_layout = QHBoxLayout()
        title_label = QLabel("Download Settings")
        try:
            from theme import get_palette
            _p = get_palette()
            title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {_p['text']}; margin-bottom: 8px;")
        except Exception:
            title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b; margin-bottom: 8px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Info button
        from PyQt6.QtWidgets import QToolButton
        info_btn = QToolButton()
        try:
            from theme import get_palette, load_svg_icon
            _p = get_palette()
            info_btn.setIcon(load_svg_icon("assets/icons/info.svg", None, 18))
            info_btn.setIconSize(QSize(18, 18))
            info_btn.setText("")
        except Exception:
            info_btn.setText("")
        info_btn.setAutoRaise(True)
        info_btn.setToolTip("Show settings information")
        info_btn.clicked.connect(self._show_info)
        header_layout.addWidget(info_btn)
        
        main_layout.addLayout(header_layout)

        # Create scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_widget.setObjectName("scrollContent")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(16)

        # Throttling Group
        throttle_group = QGroupBox("Throttling Settings")
        throttle_layout = QVBoxLayout(throttle_group)
        throttle_layout.setSpacing(12)

        # Throttle enable with description
        self.enable_cb = QCheckBox("Enable gentle throttling")
        self.enable_cb.setChecked(self._settings.is_throttle_enabled())
        self.enable_cb.setToolTip("When enabled, downloads will be throttled to avoid being blocked by YouTube")
        throttle_layout.addWidget(self.enable_cb)

        # Rate limit with better layout
        rate_layout = QHBoxLayout()
        rate_label = QLabel("Rate limit:")
        rate_label.setFixedWidth(120)
        self.rate_sb = QSpinBox()
        self.rate_sb.setRange(0, 200)
        self.rate_sb.setValue(self._settings.get_rate_limit_mbps())
        self.rate_sb.setSuffix(" MB/s")
        self.rate_sb.setToolTip("Maximum download speed. Set to 0 for unlimited speed")
        rate_layout.addWidget(rate_label)
        rate_layout.addWidget(self.rate_sb)
        rate_layout.addStretch()
        throttle_layout.addLayout(rate_layout)

        content_layout.addWidget(throttle_group)

        # Delay Settings Group
        delay_group = QGroupBox("Delay Settings")
        delay_layout = QVBoxLayout(delay_group)
        delay_layout.setSpacing(12)

        # Pre-download delay
        pre_layout = QHBoxLayout()
        pre_label = QLabel("Pre-download delay:")
        pre_label.setFixedWidth(120)
        self.pre_min = QDoubleSpinBox()
        self.pre_min.setRange(0.0, 30.0)
        self.pre_min.setDecimals(1)
        self.pre_min.setSuffix(" s")
        self.pre_max = QDoubleSpinBox()
        self.pre_max.setRange(0.0, 30.0)
        self.pre_max.setDecimals(1)
        self.pre_max.setSuffix(" s")
        min_pre, max_pre = self._settings.get_pre_delay_range()
        self.pre_min.setValue(min_pre)
        self.pre_max.setValue(max_pre)
        self.pre_min.setToolTip("Minimum delay before starting download")
        self.pre_max.setToolTip("Maximum delay before starting download")
        
        pre_layout.addWidget(pre_label)
        pre_layout.addWidget(self.pre_min)
        pre_layout.addWidget(QLabel("to"))
        pre_layout.addWidget(self.pre_max)
        pre_layout.addStretch()
        delay_layout.addLayout(pre_layout)

        # Between-item delays (success)
        succ_layout = QHBoxLayout()
        succ_label = QLabel("Success delay:")
        succ_label.setFixedWidth(120)
        self.succ_min = QDoubleSpinBox()
        self.succ_min.setRange(0.0, 60.0)
        self.succ_min.setDecimals(1)
        self.succ_min.setSuffix(" s")
        self.succ_max = QDoubleSpinBox()
        self.succ_max.setRange(0.0, 60.0)
        self.succ_max.setDecimals(1)
        self.succ_max.setSuffix(" s")
        smin, smax = self._settings.get_between_success_range()
        self.succ_min.setValue(smin)
        self.succ_max.setValue(smax)
        self.succ_min.setToolTip("Minimum delay between successful downloads")
        self.succ_max.setToolTip("Maximum delay between successful downloads")
        
        succ_layout.addWidget(succ_label)
        succ_layout.addWidget(self.succ_min)
        succ_layout.addWidget(QLabel("to"))
        succ_layout.addWidget(self.succ_max)
        succ_layout.addStretch()
        delay_layout.addLayout(succ_layout)

        # Between-item delays (failure)
        fail_layout = QHBoxLayout()
        fail_label = QLabel("Failure delay:")
        fail_label.setFixedWidth(120)
        self.fail_min = QDoubleSpinBox()
        self.fail_min.setRange(0.0, 120.0)
        self.fail_min.setDecimals(1)
        self.fail_min.setSuffix(" s")
        self.fail_max = QDoubleSpinBox()
        self.fail_max.setRange(0.0, 120.0)
        self.fail_max.setDecimals(1)
        self.fail_max.setSuffix(" s")
        fmin, fmax = self._settings.get_between_failure_range()
        self.fail_min.setValue(fmin)
        self.fail_max.setValue(fmax)
        self.fail_min.setToolTip("Minimum delay after failed downloads")
        self.fail_max.setToolTip("Maximum delay after failed downloads")
        
        fail_layout.addWidget(fail_label)
        fail_layout.addWidget(self.fail_min)
        fail_layout.addWidget(QLabel("to"))
        fail_layout.addWidget(self.fail_max)
        fail_layout.addStretch()
        delay_layout.addLayout(fail_layout)

        content_layout.addWidget(delay_group)

        # Advanced Settings Group
        advanced_group = QGroupBox("Advanced Network Settings")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(12)

        # Request sleep options with better layout
        si, msi, sr, msr, cf = self._settings.get_request_sleep()
        
        # Sleep interval
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Sleep interval:")
        interval_label.setFixedWidth(120)
        self.sleep_interval = QSpinBox()
        self.sleep_interval.setRange(0, 10)
        self.sleep_interval.setValue(si)
        self.sleep_interval.setSuffix(" s")
        self.sleep_interval.setToolTip("Base sleep interval between requests")
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.sleep_interval)
        interval_layout.addStretch()
        advanced_layout.addLayout(interval_layout)

        # Max sleep interval
        max_interval_layout = QHBoxLayout()
        max_interval_label = QLabel("Max interval:")
        max_interval_label.setFixedWidth(120)
        self.max_sleep_interval = QSpinBox()
        self.max_sleep_interval.setRange(0, 60)
        self.max_sleep_interval.setValue(msi)
        self.max_sleep_interval.setSuffix(" s")
        self.max_sleep_interval.setToolTip("Maximum sleep interval")
        max_interval_layout.addWidget(max_interval_label)
        max_interval_layout.addWidget(self.max_sleep_interval)
        max_interval_layout.addStretch()
        advanced_layout.addLayout(max_interval_layout)

        # Sleep requests
        requests_layout = QHBoxLayout()
        requests_label = QLabel("Sleep per request:")
        requests_label.setFixedWidth(120)
        self.sleep_requests = QSpinBox()
        self.sleep_requests.setRange(0, 10)
        self.sleep_requests.setValue(sr)
        self.sleep_requests.setSuffix(" s")
        self.sleep_requests.setToolTip("Sleep time per individual request")
        requests_layout.addWidget(requests_label)
        requests_layout.addWidget(self.sleep_requests)
        requests_layout.addStretch()
        advanced_layout.addLayout(requests_layout)

        # Max sleep requests
        max_requests_layout = QHBoxLayout()
        max_requests_label = QLabel("Max per request:")
        max_requests_label.setFixedWidth(120)
        self.max_sleep_requests = QSpinBox()
        self.max_sleep_requests.setRange(0, 60)
        self.max_sleep_requests.setValue(msr)
        self.max_sleep_requests.setSuffix(" s")
        self.max_sleep_requests.setToolTip("Maximum sleep time per request")
        max_requests_layout.addWidget(max_requests_label)
        max_requests_layout.addWidget(self.max_sleep_requests)
        max_requests_layout.addStretch()
        advanced_layout.addLayout(max_requests_layout)

        # Concurrent fragments
        frags_layout = QHBoxLayout()
        frags_label = QLabel("Concurrent fragments:")
        frags_label.setFixedWidth(120)
        self.concurrent_frags = QSpinBox()
        self.concurrent_frags.setRange(1, 10)
        self.concurrent_frags.setValue(cf)
        self.concurrent_frags.setToolTip("Number of concurrent download fragments")
        frags_layout.addWidget(frags_label)
        frags_layout.addWidget(self.concurrent_frags)
        frags_layout.addStretch()
        advanced_layout.addLayout(frags_layout)

        content_layout.addWidget(advanced_group)

        # Theme Group
        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.setSpacing(12)
        theme_label = QLabel("Theme:")
        theme_label.setFixedWidth(120)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Default", "YouTube", "Dark"])
        try:
            current_theme = str(self._settings._qs.value("ui/theme", "Default"))
            if current_theme in ("Default", "YouTube", "Dark"):
                self.theme_combo.setCurrentText(current_theme)
        except Exception:
            pass
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        content_layout.addWidget(theme_group)

        # General Settings Group
        general_group = QGroupBox("General Settings")
        general_layout = QVBoxLayout(general_group)
        general_layout.setSpacing(12)

        # Default download path
        path_layout = QHBoxLayout()
        path_label = QLabel("Default download path:")
        path_label.setFixedWidth(150)
        self.default_path_input = QLineEdit()
        self.default_path_input.setText(self._settings.get_default_download_path())
        self.default_path_input.setPlaceholderText("Leave empty to use system Downloads folder")
        self.default_path_input.setToolTip("Default folder where videos will be saved")
        
        # Browse button
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(100)  # Increased from 80
        browse_btn.setMinimumWidth(100)  # Ensure minimum width
        browse_btn.clicked.connect(self._browse_download_path)
        browse_btn.setToolTip("Select default download folder")
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.default_path_input)
        path_layout.addWidget(browse_btn)
        general_layout.addLayout(path_layout)

        # Default resolution
        res_layout = QHBoxLayout()
        res_label = QLabel("Default resolution:")
        res_label.setFixedWidth(150)
        self.default_res_combo = QComboBox()
        self.default_res_combo.addItems(["360p", "480p", "720p", "1080p", "Audio"])
        self.default_res_combo.setCurrentText(self._settings.get_default_resolution())
        self.default_res_combo.setToolTip("Default video quality for new downloads")
        self.default_res_combo.setMinimumWidth(130)  # Increased width for better display
        res_layout.addWidget(res_label)
        res_layout.addWidget(self.default_res_combo)
        res_layout.addStretch()
        general_layout.addLayout(res_layout)

        # Auto-download subtitles
        self.auto_subs_cb = QCheckBox("Automatically download English subtitles")
        self.auto_subs_cb.setChecked(self._settings.get_auto_download_subs())
        self.auto_subs_cb.setToolTip("Automatically check the subtitle option for new downloads")
        general_layout.addWidget(self.auto_subs_cb)

        # Auto-clear input
        self.auto_clear_cb = QCheckBox("Clear input field after download")
        self.auto_clear_cb.setChecked(self._settings.get_auto_clear_input())
        self.auto_clear_cb.setToolTip("Automatically clear the URL input field after successful download")
        general_layout.addWidget(self.auto_clear_cb)

        # Show notifications
        self.notifications_cb = QCheckBox("Show download notifications")
        self.notifications_cb.setChecked(self._settings.get_show_notifications())
        self.notifications_cb.setToolTip("Show system notifications when downloads complete")
        general_layout.addWidget(self.notifications_cb)

        # Auto-check updates
        self.auto_update_cb = QCheckBox("Automatically check for updates")
        self.auto_update_cb.setChecked(self._settings.get_auto_check_updates())
        self.auto_update_cb.setToolTip("Check for yt-dlp updates on startup")
        general_layout.addWidget(self.auto_update_cb)

        # Remember window size
        self.remember_size_cb = QCheckBox("Remember window size and position")
        self.remember_size_cb.setChecked(self._settings.get_remember_window_size())
        self.remember_size_cb.setToolTip("Save and restore window size and position on startup")
        general_layout.addWidget(self.remember_size_cb)

        content_layout.addWidget(general_group)
        content_layout.addStretch()

        # Format Settings Group
        format_group = QGroupBox("Format Settings")
        format_layout = QVBoxLayout(format_group)
        format_layout.setSpacing(12)

        # Preferred video format
        video_format_layout = QHBoxLayout()
        video_format_label = QLabel("Preferred video format:")
        video_format_label.setFixedWidth(150)
        self.video_format_combo = QComboBox()
        self.video_format_combo.addItems(["mp4", "webm", "mkv"])
        self.video_format_combo.setCurrentText(self._settings.get_preferred_video_format())
        self.video_format_combo.setToolTip("Preferred video container format")
        self.video_format_combo.setMinimumWidth(120)  # Increased width
        video_format_layout.addWidget(video_format_label)
        video_format_layout.addWidget(self.video_format_combo)
        video_format_layout.addStretch()
        format_layout.addLayout(video_format_layout)

        # Preferred audio format
        audio_format_layout = QHBoxLayout()
        audio_format_label = QLabel("Preferred audio format:")
        audio_format_label.setFixedWidth(150)
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItems(["m4a", "mp3", "opus", "aac"])
        self.audio_format_combo.setCurrentText(self._settings.get_preferred_audio_format())
        self.audio_format_combo.setToolTip("Preferred audio format for audio-only downloads")
        self.audio_format_combo.setMinimumWidth(120)  # Increased width
        audio_format_layout.addWidget(audio_format_label)
        audio_format_layout.addWidget(self.audio_format_combo)
        audio_format_layout.addStretch()
        format_layout.addLayout(audio_format_layout)

        # Audio quality
        audio_quality_layout = QHBoxLayout()
        audio_quality_label = QLabel("Audio quality:")
        audio_quality_label.setFixedWidth(150)
        self.audio_quality_combo = QComboBox()
        self.audio_quality_combo.addItems(["128k", "192k", "256k", "320k"])
        self.audio_quality_combo.setCurrentText(self._settings.get_audio_quality())
        self.audio_quality_combo.setToolTip("Audio bitrate for audio-only downloads")
        self.audio_quality_combo.setMinimumWidth(120)  # Increased width
        audio_quality_layout.addWidget(audio_quality_label)
        audio_quality_layout.addWidget(self.audio_quality_combo)
        audio_quality_layout.addStretch()
        format_layout.addLayout(audio_quality_layout)

        content_layout.addWidget(format_group)
        content_layout.addStretch()

        # Download Behavior Group
        download_group = QGroupBox("Download Behavior")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(12)

        # Retry attempts
        retry_layout = QHBoxLayout()
        retry_label = QLabel("Retry attempts:")
        retry_label.setFixedWidth(150)
        self.retry_attempts_sb = QSpinBox()
        self.retry_attempts_sb.setRange(0, 10)
        self.retry_attempts_sb.setValue(self._settings.get_retry_attempts())
        self.retry_attempts_sb.setSuffix(" times")
        self.retry_attempts_sb.setToolTip("Number of times to retry failed downloads")
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(self.retry_attempts_sb)
        retry_layout.addStretch()
        download_layout.addLayout(retry_layout)

        # Retry delay
        retry_delay_layout = QHBoxLayout()
        retry_delay_label = QLabel("Retry delay:")
        retry_delay_label.setFixedWidth(150)
        self.retry_delay_sb = QSpinBox()
        self.retry_delay_sb.setRange(1, 60)
        self.retry_delay_sb.setValue(self._settings.get_retry_delay())
        self.retry_delay_sb.setSuffix(" seconds")
        self.retry_delay_sb.setToolTip("Time to wait between retry attempts")
        retry_delay_layout.addWidget(retry_delay_label)
        retry_delay_layout.addWidget(self.retry_delay_sb)
        retry_delay_layout.addStretch()
        download_layout.addLayout(retry_delay_layout)

        # Max concurrent downloads
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("Batch queue limit:")
        concurrent_label.setFixedWidth(150)
        self.max_concurrent_sb = QSpinBox()
        self.max_concurrent_sb.setRange(1, 10)
        self.max_concurrent_sb.setValue(self._settings.get_max_concurrent_downloads())
        self.max_concurrent_sb.setSuffix(" items")
        self.max_concurrent_sb.setToolTip("Maximum number of items allowed in batch queue (affects autopaste and batch mode)")
        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.max_concurrent_sb)
        concurrent_layout.addStretch()
        download_layout.addLayout(concurrent_layout)

        # New: Save playlists to subfolder
        self.playlist_subfolder_cb = QCheckBox("Save playlists into a separate subfolder")
        self.playlist_subfolder_cb.setChecked(self._settings.get_save_playlists_to_subfolder())
        self.playlist_subfolder_cb.setToolTip("When enabled, playlist items are saved to …/Playlists/<Playlist Title>/ inside your chosen folder")
        download_layout.addWidget(self.playlist_subfolder_cb)

        # Skip existing files
        self.skip_existing_cb = QCheckBox("Skip existing files")
        self.skip_existing_cb.setChecked(self._settings.get_skip_existing_files())
        self.skip_existing_cb.setToolTip("Don't re-download if file already exists")
        download_layout.addWidget(self.skip_existing_cb)

        # Auto-resume downloads
        self.auto_resume_cb = QCheckBox("Auto-resume interrupted downloads")
        self.auto_resume_cb.setChecked(self._settings.get_auto_resume_downloads())
        self.auto_resume_cb.setToolTip("Resume failed downloads automatically")
        download_layout.addWidget(self.auto_resume_cb)

        content_layout.addWidget(download_group)
        content_layout.addStretch()

        # Authentication/Cookies Group (compact)
        cookie_group = QGroupBox("Authentication")
        cookie_layout = QHBoxLayout(cookie_group)
        cookie_layout.setSpacing(12)
        cookie_desc = QLabel("Manage YouTube cookies for authentication")
        cookies_btn = QPushButton("Cookies…")
        cookies_btn.setFixedWidth(120)
        try:
            from theme import button_style
            cookies_btn.setStyleSheet(button_style('info', radius=6, padding='8px 14px'))
        except Exception:
            pass
        cookies_btn.clicked.connect(self._open_cookies_dialog)
        cookie_layout.addWidget(cookie_desc)
        cookie_layout.addStretch()
        cookie_layout.addWidget(cookies_btn)
        content_layout.addWidget(cookie_group)
        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Buttons
        btns_layout = QHBoxLayout()
        default_btn = QPushButton("Default")
        try:
            from theme import button_style
            default_btn.setStyleSheet(button_style('warn', radius=6, padding='10px 20px'))
        except Exception:
            default_btn.setStyleSheet("background-color: #6b7280; color: #ffffff; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold;")
        default_btn.clicked.connect(self._reset_to_defaults)
        btns_layout.addWidget(default_btn)
        btns_layout.addStretch()
        save_btn = QPushButton("Save Settings")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        try:
            save_btn.setStyleSheet(button_style('primary', radius=6, padding='10px 20px'))
            cancel_btn.setStyleSheet(button_style('danger', radius=6, padding='10px 20px'))
        except Exception:
            save_btn.setStyleSheet("background-color: #3b82f6; color: #ffffff; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold;")
            cancel_btn.setStyleSheet("background-color: #ef4444; color: #ffffff; border: none; border-radius: 6px; padding: 10px 20px; font-weight: bold;")
        btns_layout.addWidget(save_btn)
        btns_layout.addWidget(cancel_btn)
        main_layout.addLayout(btns_layout)
        
        # Store original values after UI is set up
        self._store_original_values()

        # Keep references for styling
        self._btn_default = default_btn
        self._btn_save = save_btn
        self._btn_cancel = cancel_btn
        # Some other common buttons, if present
        self._btn_browse_path = browse_btn
        # Inline cookies buttons removed in compact UI

    def _open_cookies_dialog(self):
        """Open the consolidated Cookies dialog."""
        try:
            show_cookies_dialog(self)
        except Exception:
            pass

    def _show_info(self):
        """Show information dialog"""
        info_dialog = InformationDialog(self)
        info_dialog.exec()

    def _on_save(self):
        """Save all settings"""
        self._settings.set_throttle_enabled(self.enable_cb.isChecked())
        self._settings.set_rate_limit_mbps(self.rate_sb.value())
        self._settings.set_pre_delay_range(self.pre_min.value(), self.pre_max.value())
        self._settings.set_between_success_range(self.succ_min.value(), self.succ_max.value())
        self._settings.set_between_failure_range(self.fail_min.value(), self.fail_max.value())
        self._settings.set_request_sleep(
            self.sleep_interval.value(),
            self.max_sleep_interval.value(),
            self.sleep_requests.value(),
            self.max_sleep_requests.value(),
            self.concurrent_frags.value(),
        )
        self._settings.set_default_download_path(self.default_path_input.text())
        self._settings.set_default_resolution(self.default_res_combo.currentText())
        self._settings.set_auto_download_subs(self.auto_subs_cb.isChecked())
        self._settings.set_auto_clear_input(self.auto_clear_cb.isChecked())
        self._settings.set_show_notifications(self.notifications_cb.isChecked())
        self._settings.set_auto_check_updates(self.auto_update_cb.isChecked())
        self._settings.set_remember_window_size(self.remember_size_cb.isChecked())
        self._settings.set_retry_attempts(self.retry_attempts_sb.value())
        self._settings.set_retry_delay(self.retry_delay_sb.value())
        self._settings.set_max_concurrent_downloads(self.max_concurrent_sb.value())
        self._settings.set_skip_existing_files(self.skip_existing_cb.isChecked())
        self._settings.set_auto_resume_downloads(self.auto_resume_cb.isChecked())
        self._settings.set_preferred_video_format(self.video_format_combo.currentText())
        self._settings.set_preferred_audio_format(self.audio_format_combo.currentText())
        self._settings.set_audio_quality(self.audio_quality_combo.currentText())
        # New: save playlist subfolder preference
        self._settings.set_save_playlists_to_subfolder(self.playlist_subfolder_cb.isChecked())
        
        # Cookie settings are managed in Cookies dialog

        # Save theme and apply immediately
        try:
            theme_name = self.theme_combo.currentText()
            self._settings._qs.setValue("ui/theme", theme_name)
            from PyQt6.QtWidgets import QApplication
            from theme import apply_theme, Theme
            app = QApplication.instance()
            if theme_name == "YouTube":
                theme_key = Theme.YOUTUBE
            elif theme_name == "Dark":
                theme_key = Theme.DARK
            else:
                theme_key = Theme.DEFAULT
            apply_theme(app, theme_key)
            # Ask parent main window to refresh button styles
            try:
                if hasattr(self.parent(), 'apply_theme_styles'):
                    self.parent().apply_theme_styles()
            except Exception:
                pass
            # Re-apply dialog button styles too
            try:
                self._apply_theme_styles()
            except Exception:
                pass
        except Exception:
            pass
        
        self.accept()

    def _apply_theme_styles(self):
        try:
            from theme import button_style
        except Exception:
            return
        # Map roles
        role_for = {
            '_btn_default': 'warn',
            '_btn_save': 'primary',
            '_btn_cancel': 'danger',
            '_btn_browse_path': 'info',
        }
        for attr, role in role_for.items():
            btn = getattr(self, attr, None)
            if btn:
                try:
                    # Slightly smaller padding for small buttons
                    pad = '10px 20px' if role in ('primary', 'danger', 'warn') else '6px 12px'
                    btn.setStyleSheet(button_style(role, radius=6, padding=pad))
                except Exception:
                    pass

    def _reset_to_defaults(self):
        """Reset settings to default values with confirmation."""
        # Store current values before resetting
        self._store_original_values()
        
        # Show confirmation dialog
        from PyQt6.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Reset to Defaults")
        msg_box.setText("Are you sure you want to reset all settings to default values?")
        msg_box.setInformativeText("This will reset all your current settings including:\n• Throttling preferences\n• Download paths\n• Cookie settings\n• Browser preferences\n\nThis action cannot be undone.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        
        # Style the message box
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
            QPushButton[text="Cancel"] {
                background-color: #6b7280;
            }
            QPushButton[text="Cancel"]:hover {
                background-color: #4b5563;
            }
        """)
        
        result = msg_box.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            # User confirmed, proceed with reset
            self._perform_reset()
        else:
            # User cancelled, restore original values
            self._restore_original_values()

    def _perform_reset(self):
        """Actually perform the reset to default values."""
        # Reset all UI values to defaults
        self.enable_cb.setChecked(True)
        self.rate_sb.setValue(20)
        self.pre_min.setValue(1.5)
        self.pre_max.setValue(3.5)
        self.succ_min.setValue(3.0)
        self.succ_max.setValue(7.0)
        self.fail_min.setValue(5.0)
        self.fail_max.setValue(12.0)
        self.sleep_interval.setValue(2)
        self.max_sleep_interval.setValue(5)
        self.sleep_requests.setValue(1)
        self.max_sleep_requests.setValue(3)
        self.concurrent_frags.setValue(1)
        self.default_path_input.setText("")
        self.default_res_combo.setCurrentText("720p")
        self.auto_subs_cb.setChecked(False)
        self.auto_clear_cb.setChecked(True)
        self.notifications_cb.setChecked(True)
        self.auto_update_cb.setChecked(True)
        self.remember_size_cb.setChecked(True)
        self.retry_attempts_sb.setValue(3)
        self.retry_delay_sb.setValue(5)
        self.max_concurrent_sb.setValue(3)
        self.skip_existing_cb.setChecked(True)
        self.auto_resume_cb.setChecked(True)
        self.video_format_combo.setCurrentText("mp4")
        self.audio_format_combo.setCurrentText("m4a")
        self.audio_quality_combo.setCurrentText("192k")
        self.playlist_subfolder_cb.setChecked(True) # Reset this new checkbox
        
        # Cookie settings are managed in Cookies dialog
        
        # Clear original values since reset was confirmed
        self.original_values = {}

    def _store_original_values(self):
        """Store current values to restore if reset is cancelled"""
        self.original_values = {
            'throttle_enabled': self.enable_cb.isChecked(),
            'rate_limit': self.rate_sb.value(),
            'pre_min': self.pre_min.value(),
            'pre_max': self.pre_max.value(),
            'succ_min': self.succ_min.value(),
            'succ_max': self.succ_max.value(),
            'fail_min': self.fail_min.value(),
            'fail_max': self.fail_max.value(),
            'sleep_interval': self.sleep_interval.value(),
            'max_sleep_interval': self.max_sleep_interval.value(),
            'sleep_requests': self.sleep_requests.value(),
            'max_sleep_requests': self.max_sleep_requests.value(),
            'concurrent_frags': self.concurrent_frags.value(),
            'default_path': self.default_path_input.text(),
            'default_resolution': self.default_res_combo.currentText(),
            'auto_subs': self.auto_subs_cb.isChecked(),
            'auto_clear': self.auto_clear_cb.isChecked(),
            'notifications': self.notifications_cb.isChecked(),
            'auto_update': self.auto_update_cb.isChecked(),
            'remember_size': self.remember_size_cb.isChecked(),
            'retry_attempts': self.retry_attempts_sb.value(),
            'retry_delay': self.retry_delay_sb.value(),
            'max_concurrent': self.max_concurrent_sb.value(),
            'skip_existing': self.skip_existing_cb.isChecked(),
            'auto_resume': self.auto_resume_cb.isChecked(),
            'video_format': self.video_format_combo.currentText(),
            'audio_format': self.audio_format_combo.currentText(),
            'audio_quality': self.audio_quality_combo.currentText(),
            'save_playlists_to_subfolder': self.playlist_subfolder_cb.isChecked(),
        }

    def _restore_original_values(self):
        """Restore original values if reset is cancelled"""
        if not self.original_values:
            return
            
        self.enable_cb.setChecked(self.original_values['throttle_enabled'])
        self.rate_sb.setValue(self.original_values['rate_limit'])
        self.pre_min.setValue(self.original_values['pre_min'])
        self.pre_max.setValue(self.original_values['pre_max'])
        self.succ_min.setValue(self.original_values['succ_min'])
        self.succ_max.setValue(self.original_values['succ_max'])
        self.fail_min.setValue(self.original_values['fail_min'])
        self.fail_max.setValue(self.original_values['fail_max'])
        self.sleep_interval.setValue(self.original_values['sleep_interval'])
        self.max_sleep_interval.setValue(self.original_values['max_sleep_interval'])
        self.sleep_requests.setValue(self.original_values['sleep_requests'])
        self.max_sleep_requests.setValue(self.original_values['max_sleep_requests'])
        self.concurrent_frags.setValue(self.original_values['concurrent_frags'])
        self.default_path_input.setText(self.original_values['default_path'])
        self.default_res_combo.setCurrentText(self.original_values['default_resolution'])
        self.auto_subs_cb.setChecked(self.original_values['auto_subs'])
        self.auto_clear_cb.setChecked(self.original_values['auto_clear'])
        self.notifications_cb.setChecked(self.original_values['notifications'])
        self.auto_update_cb.setChecked(self.original_values['auto_update'])
        self.remember_size_cb.setChecked(self.original_values['remember_size'])
        self.retry_attempts_sb.setValue(self.original_values['retry_attempts'])
        self.retry_delay_sb.setValue(self.original_values['retry_delay'])
        self.max_concurrent_sb.setValue(self.original_values['max_concurrent'])
        self.skip_existing_cb.setChecked(self.original_values['skip_existing'])
        self.auto_resume_cb.setChecked(self.original_values['auto_resume'])
        self.video_format_combo.setCurrentText(self.original_values['video_format'])
        self.audio_format_combo.setCurrentText(self.original_values['audio_format'])
        self.audio_quality_combo.setCurrentText(self.original_values['audio_quality'])
        self.playlist_subfolder_cb.setChecked(self.original_values['save_playlists_to_subfolder'])
        
        # Cookie settings are managed in Cookies dialog

    def _browse_download_path(self):
        """Open a file dialog to select a default download path."""
        from pathlib import Path
        
        # Get current path or use home directory as default
        current_path = self.default_path_input.text()
        if current_path and Path(current_path).exists():
            default_path = current_path
        else:
            # Use system's home directory if no path is set or invalid
            default_path = str(Path.home())
        
        # Open folder selection dialog
        selected_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Default Download Path", 
            default_path,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if selected_path:
            self.default_path_input.setText(selected_path)

    # Inline cookie helpers removed; managed in Cookies dialog


class InformationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings Information")
        self.setModal(True)
        self.resize(550, 450)
        
        # Set styling consistent with settings dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                color: #1e293b;
            }
            QLabel {
                color: #1e293b;
                font-size: 12px;
            }
            QTextEdit {
                color: #1e293b;
                background-color: #ffffff;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("Settings Information")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b; margin-bottom: 8px;")
        layout.addWidget(title_label)

        # Information text
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setHtml("""
        <h3 style="color: #1e293b; margin-top: 0;">🎯 Throttling Settings</h3>
        <p><b>Enable gentle throttling:</b> When enabled, the downloader will use intelligent throttling to avoid being blocked by YouTube's anti-bot measures. This makes downloads more reliable but slightly slower.</p>
        
        <h3 style="color: #1e293b;">⚡ Rate Limit</h3>
        <p><b>Rate limit (MB/s):</b> Controls the maximum download speed in megabytes per second. Set to 0 for unlimited speed. Lower values are safer but slower.</p>
        
        <h3 style="color: #1e293b;">⏱️ Pre-download Delay</h3>
        <p><b>Pre-download delay:</b> A random delay (in seconds) before starting each download. This helps avoid detection by making requests appear more human-like.</p>
        
        <h3 style="color: #1e293b;">🔄 Between Items Delay</h3>
        <p><b>Success delay:</b> Delay between successful downloads when processing multiple videos. Keeps a safe interval between requests.</p>
        <p><b>Failure delay:</b> Longer delay after failed downloads before retrying. Gives YouTube's servers time to recover.</p>
        
        <h3 style="color: #1e293b;">🌐 Advanced Network Settings</h3>
        <p><b>Request sleep settings:</b> Fine-tune how the downloader interacts with YouTube's servers:</p>
        <ul>
            <li><b>Sleep interval:</b> Base time to wait between network requests</li>
            <li><b>Max interval:</b> Maximum time to wait (prevents excessive delays)</li>
            <li><b>Sleep per request:</b> Additional sleep time for each individual request</li>
            <li><b>Max per request:</b> Maximum sleep time per request</li>
            <li><b>Concurrent fragments:</b> Number of download pieces to download simultaneously (1 is safest)</li>
        </ul>
        
        <h3 style="color: #1e293b;">⚙️ General Settings</h3>
        <p><b>Default download path:</b> Set a custom folder where videos will be saved by default. Leave empty to use your system's Downloads folder.</p>
        <p><b>Default resolution:</b> Choose the default video quality for new downloads. <b>When you change this setting, the main window's resolution dropdown will update to match your selection the next time you open the settings or after saving.</b></p>
        <p><b>Auto-download subtitles:</b> Automatically check the subtitle option for new downloads.</p>
        <p><b>Clear input field:</b> Automatically clear the URL input after successful downloads for convenience.</p>
        <p><b>Show notifications:</b> Display system notifications when downloads complete.</p>
        <p><b>Auto-check updates:</b> Automatically check for yt-dlp updates when the app starts.</p>
        <p><b>Remember window size:</b> Save and restore the window size and position between app sessions.</p>
        
        <h3 style="color: #1e293b;">🎬 Format Settings</h3>
        <p><b>Preferred video format:</b> Choose the video container format (mp4, webm, mkv). MP4 is most compatible.</p>
        <p><b>Preferred audio format:</b> Choose the audio format for audio-only downloads (m4a, mp3, opus, aac). M4A offers good quality and compatibility.</p>
        <p><b>Audio quality:</b> Set the audio bitrate for audio-only downloads. Higher values mean better quality but larger files.</p>
        
        <h3 style="color: #1e293b;">📥 Download Behavior</h3>
        <p><b>Retry attempts:</b> Number of times to retry failed downloads before giving up. Higher values increase reliability but may take longer.</p>
        <p><b>Retry delay:</b> Time to wait between retry attempts in seconds. Gives servers time to recover.</p>
        <p><b>Batch queue limit:</b> Maximum number of items allowed in the batch download queue. When autopaste is enabled, this limits how many URLs can be queued. The batch status will show color-coded warnings when approaching the limit.</p>
        <p><b>Skip existing files:</b> Don't re-download files that already exist in the target folder. Saves time and bandwidth.</p>
        <p><b>Auto-resume downloads:</b> Automatically resume interrupted downloads when possible. Useful for large files or unstable connections.</p>
        
        <p style="background-color: #fef3c7; padding: 8px; border-radius: 4px; border-left: 4px solid #f59e0b;">
        <b>💡 Tip:</b> These settings help make downloads more reliable and less likely to be blocked. 
        Start with default values and only adjust if you experience issues.
        </p>
        
        <p style="background-color: #dbeafe; padding: 8px; border-radius: 4px; border-left: 4px solid #3b82f6;">
        <b>🔧 Default Button:</b> Click the "Default" button to reset all settings to safe, recommended values.
        </p>
        """)
        layout.addWidget(info_text)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)










