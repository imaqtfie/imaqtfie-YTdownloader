import os
import json
import threading
from datetime import datetime
from collections import deque
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QTabWidget, QWidget, QLabel, QScrollArea, QFrame, QGraphicsDropShadowEffect,
    QStylePainter, QStyleOptionButton, QStyle
)
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QPalette


class LogManager(QObject):
    """Manages all logging functionality including real-time logs and download history"""

    # Signals for real-time log updates
    log_updated = pyqtSignal(str, str)  # message, level
    download_completed = pyqtSignal(dict)  # download info

    def __init__(self, max_realtime_logs=100, max_history_entries=10):
        super().__init__()
        self.max_realtime_logs = max_realtime_logs
        self.max_history_entries = max_history_entries

        # Real-time logs storage (in memory)
        self.realtime_logs = deque(maxlen=max_realtime_logs)

        # Download history storage (persistent)
        self.history_file = os.path.expanduser("~/Downloads/yt_downloader_history.json")
        self.download_history = self.load_history()

        # Thread lock for safe operations
        self.lock = threading.Lock()

        # Current download session info
        self.current_session = {
            'start_time': None,
            'url': None,
            'title': None,
            'resolution': None,
            'status': 'idle',
            'logs': []
        }

    def start_download_session(self, url, resolution, download_subs=False, batch_mode=False):
        """Start a new download session"""
        with self.lock:
            self.current_session = {
                'start_time': datetime.now(),
                'url': url,
                'title': None,
                'resolution': resolution,
                'download_subs': download_subs,
                'batch_mode': batch_mode,
                'status': 'downloading',
                'logs': [],
                'end_time': None,
                'file_size': None,
                'download_path': None
            }

        self.log("INFO", f"Started download: {url} [{resolution}]")

    def log(self, level, message):
        """Add a log entry to real-time logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message
        }

        with self.lock:
            self.realtime_logs.append(log_entry)
            if self.current_session['status'] == 'downloading':
                self.current_session['logs'].append(log_entry)

        # Emit signal for real-time updates
        self.log_updated.emit(f"[{timestamp}] {message}", level)

    def update_video_info(self, title, file_size=None):
        """Update current session with video information"""
        with self.lock:
            if self.current_session['status'] == 'downloading':
                self.current_session['title'] = title
                if file_size:
                    self.current_session['file_size'] = file_size

        self.log("INFO", f"Video: {title}")
        if file_size:
            self.log("INFO", f"Size: {file_size}")

    def update_download_progress(self, progress, speed=None):
        """Update download progress"""
        message = f"Progress: {progress}"
        if speed:
            message += f" | Speed: {speed}"
        self.log("PROGRESS", message)

    def complete_download_session(self, success=True, error_message=None, download_path=None):
        """Complete the current download session"""
        with self.lock:
            if self.current_session['status'] != 'downloading':
                return

            self.current_session['end_time'] = datetime.now()
            self.current_session['status'] = 'completed' if success else 'failed'
            if download_path:
                self.current_session['download_path'] = download_path
            if error_message:
                self.current_session['error'] = error_message

            # Calculate duration
            if self.current_session['start_time']:
                duration = self.current_session['end_time'] - self.current_session['start_time']
                self.current_session['duration'] = str(duration).split('.')[0]  # Remove microseconds

            # Add to history
            self.add_to_history(self.current_session.copy())

        if success:
            self.log("SUCCESS", "Download completed successfully!")
        else:
            self.log("ERROR", f"Download failed: {error_message or 'Unknown error'}")

        # Emit completion signal
        self.download_completed.emit(self.current_session.copy())

    def add_to_history(self, session_data):
        """Add completed download to history"""
        # Keep only essential data for history
        history_entry = {
            'timestamp': session_data['start_time'].isoformat() if session_data['start_time'] else None,
            'end_time': session_data['end_time'].isoformat() if session_data['end_time'] else None,
            'url': session_data['url'],
            'title': session_data['title'] or 'Unknown Title',
            'resolution': session_data['resolution'],
            'status': session_data['status'],
            'duration': session_data.get('duration', 'Unknown'),
            'file_size': session_data.get('file_size'),
            'download_path': session_data.get('download_path'),
            'batch_mode': session_data.get('batch_mode', False),
            'download_subs': session_data.get('download_subs', False),
            'error': session_data.get('error'),
            'log_count': len(session_data.get('logs', []))
        }

        self.download_history.append(history_entry)

        # Keep only the last N entries
        if len(self.download_history) > self.max_history_entries:
            self.download_history = self.download_history[-self.max_history_entries:]

        # Save to file
        self.save_history()

    def load_history(self):
        """Load download history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
        return []

    def save_history(self):
        """Save download history to file"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.download_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving history: {e}")

    def get_realtime_logs(self):
        """Get all current real-time logs"""
        with self.lock:
            return list(self.realtime_logs)

    def get_download_history(self):
        """Get download history"""
        return self.download_history.copy()

    def clear_realtime_logs(self):
        """Clear real-time logs"""
        with self.lock:
            self.realtime_logs.clear()
        self.log("INFO", "Real-time logs cleared")


class FilterButton(QPushButton):
    """QPushButton that forces its text color independent of QSS for robust visibility."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_dark = False

    def set_dark_mode(self, is_dark: bool):
        self._is_dark = bool(is_dark)
        self.update()

    def paintEvent(self, event):
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        forced = QColor('#ffffff' if self._is_dark else '#000000')
        opt.palette.setColor(QPalette.ColorRole.ButtonText, forced)
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, opt)


class LogDialog(QDialog):
    """Dialog window to display logs and download history"""

    def __init__(self, log_manager, parent_ui, on_retry=None):
        super().__init__(parent_ui)
        self.log_manager = log_manager
        self.on_retry = on_retry
        self.setWindowTitle("Download Logs")
        self.setModal(False)  # Allow interaction with main window
        self.resize(850, 650)  # Slightly larger for better content display

        # Connect to log manager signals
        self.log_manager.log_updated.connect(self.add_realtime_log)
        self.log_manager.download_completed.connect(lambda _: self.load_history())

        self.setup_ui()
        self.load_initial_data()
        self.apply_theme_styles() # Call apply_theme_styles here

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Apply palette-driven styling to match current theme (supports dark, default, YouTube)
        try:
            self.setStyleSheet(self._build_styles())
        except Exception:
            pass

        # Tab widget for different views
        self.tabs = QTabWidget()

        # Add shadow effect to tab widget
        tab_shadow = QGraphicsDropShadowEffect()
        tab_shadow.setBlurRadius(20)
        tab_shadow.setXOffset(0)
        tab_shadow.setYOffset(4)
        tab_shadow.setColor(QColor(0, 0, 0, 30))
        self.tabs.setGraphicsEffect(tab_shadow)

        # Real-time logs tab
        self.realtime_tab = QWidget()
        self.setup_realtime_tab()
        self.tabs.addTab(self.realtime_tab, "Real-time Logs")

        # Download history tab
        self.history_tab = QWidget()
        self.setup_history_tab()
        self.tabs.addTab(self.history_tab, "Download History")

        # Set SVG icons for tabs if assets exist
        try:
            from theme import load_svg_icon
            _rt_icon = load_svg_icon("assets/icons/real-time logs.svg", None, 18)
            _hist_icon = load_svg_icon("assets/icons/download history.svg", None, 18)
            self.tabs.setTabIcon(0, _rt_icon)
            self.tabs.setTabIcon(1, _hist_icon)
        except Exception:
            pass

        layout.addWidget(self.tabs)

        # Bottom buttons with enhanced styling and proper spacing
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setContentsMargins(0, 10, 0, 0)

        self.clear_logs_btn = QPushButton("Clear Real-time Logs")
        self.clear_logs_btn.setObjectName("clear_logs_btn")
        self.clear_logs_btn.clicked.connect(self.clear_realtime_logs)
        try:
            from theme import button_style
            self.clear_logs_btn.setStyleSheet(button_style('warn'))
        except Exception:
            pass

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        try:
            from theme import button_style
            self.refresh_btn.setStyleSheet(button_style('primary'))
        except Exception:
            pass

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("close_btn")
        self.close_btn.clicked.connect(self.close)
        try:
            from theme import button_style
            self.close_btn.setStyleSheet(button_style('primary', radius=6, padding='10px 18px'))
        except Exception:
            pass

        button_layout.addWidget(self.clear_logs_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def setup_realtime_tab(self):
        """Setup the real-time logs tab"""
        layout = QVBoxLayout(self.realtime_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Info label with enhanced styling
        self.realtime_info_label = QLabel("Real-time logs (last 100 entries)")
        try:
            from theme import get_palette, get_current_theme_key, Theme
            _p = get_palette()
            _key = get_current_theme_key()
            if _key == Theme.DARK:
                _color = "#ffffff"
            elif _key in (Theme.DEFAULT, Theme.YOUTUBE):
                _color = "#000000"
            else:
                _color = _p['text']
            self.realtime_info_label.setStyleSheet(f"font-weight: 600; color: {_color}; padding: 8px 12px;")
        except Exception:
            self.realtime_info_label.setStyleSheet("font-weight: 600; color: #1e293b; padding: 8px 12px;")
        layout.addWidget(self.realtime_info_label)

        # Log display with enhanced styling
        self.realtime_text = QTextEdit()
        self.realtime_text.setReadOnly(True)
        self.realtime_text.setFont(QFont("Consolas", 11))  # Slightly larger font

        # Add shadow to text area
        text_shadow = QGraphicsDropShadowEffect()
        text_shadow.setBlurRadius(10)
        text_shadow.setXOffset(0)
        text_shadow.setYOffset(2)
        text_shadow.setColor(QColor(0, 0, 0, 20))
        self.realtime_text.setGraphicsEffect(text_shadow)

        layout.addWidget(self.realtime_text)

    def setup_history_tab(self):
        """Setup the download history tab"""
        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Filter controls
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self.filter_label = QLabel("Filter:")
        try:
            from theme import get_palette, get_current_theme_key, Theme
            _p = get_palette()
            _key = get_current_theme_key()
            if _key in (Theme.DEFAULT, Theme.YOUTUBE):
                self.filter_label.setStyleSheet("color: #000000; font-weight: 600;")
            elif _key == Theme.DARK:
                self.filter_label.setStyleSheet("color: #ffffff; font-weight: 600;")
            else:
                self.filter_label.setStyleSheet(f"color: {_p['text']}; font-weight: 600;")
        except Exception:
            self.filter_label.setStyleSheet("color: #000000; font-weight: 600;")
        self.filter_all_btn = FilterButton("All")
        self.filter_all_btn.setObjectName("filter_all_btn")
        self.filter_success_btn = FilterButton("Success")
        self.filter_success_btn.setObjectName("filter_success_btn")
        self.filter_failed_btn = FilterButton("Failed")
        self.filter_failed_btn.setObjectName("filter_failed_btn")
        for btn in (self.filter_all_btn, self.filter_success_btn, self.filter_failed_btn):
            btn.setFixedHeight(30)
            try:
                from theme import get_current_theme_key, Theme
                _key = get_current_theme_key()
                _name = getattr(_key, 'name', str(_key))
                if _name in ('DEFAULT', 'YOUTUBE'):
                    # Role-tinted buttons on light themes: All=blue, Success=green, Failed=red
                    _p = get_palette()
                    if btn is self.filter_all_btn:
                        role_color = _p['primary'] if _name == 'DEFAULT' else _p['info']
                    elif btn is self.filter_success_btn:
                        role_color = _p['success']
                    else:
                        role_color = _p['danger']
                    btn.setStyleSheet(
                        f"""
                        QPushButton#{btn.objectName()} {{
                            background: {_rgba(role_color, 0.10)};
                            color: #000000;
                            border: 1px solid {_rgba(role_color, 0.35)};
                            border-radius: 6px;
                            padding: 6px 12px;
                            font-weight: 600;
                        }}
                        QPushButton#{btn.objectName()}:hover {{
                            color: #000000;
                            background: {_rgba(role_color, 0.16)};
                            border-color: {_rgba(role_color, 0.45)};
                        }}
                        QPushButton#{btn.objectName()}:pressed {{
                            color: #000000;
                            background: {_rgba(role_color, 0.22)};
                            border-color: {_rgba(role_color, 0.55)};
                        }}
                        QPushButton#{btn.objectName()}:checked,
                        QPushButton#{btn.objectName()}:checked:hover,
                        QPushButton#{btn.objectName()}:checked:pressed {{
                            color: #000000;
                        }}
                        QPushButton#{btn.objectName()}:disabled {{
                            color: rgba(0, 0, 0, 0.6);
                        }}
                        """
                    )
                    # Reinforce via palette
                    try:
                        pal = btn.palette()
                        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#000000"))
                        btn.setPalette(pal)
                    except Exception:
                        pass
                    # Append a final selector-scoped rule to ensure override
                    btn.setStyleSheet(btn.styleSheet() + f"\nQPushButton#{btn.objectName()} {{ color: #000000; }}\n")
                else:
                    from theme import button_style, get_palette
                    role = 'info'
                    if btn is self.filter_success_btn:
                        role = 'success'
                    elif btn is self.filter_failed_btn:
                        role = 'danger'
                    _style = button_style(role, radius=6, padding='6px 12px')
                    # Lighten background specifically for dark theme using role tint
                    try:
                        _p = get_palette()
                        if role == 'info':
                            role_color = _p['info']
                        elif role == 'success':
                            role_color = _p['success']
                        else:
                            role_color = _p['danger']
                    except Exception:
                        role_color = '#43f1fa'
                    _style += (
                        f"\nQPushButton#{btn.objectName()} {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:hover {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:pressed {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:checked {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:checked:hover {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:checked:pressed {{ color: #ffffff; }}\n"
                        f"QPushButton#{btn.objectName()}:disabled {{ color: rgba(255, 255, 255, 0.6); }}\n"
                        f"QPushButton#{btn.objectName()} {{\n"
                        f"  background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,\n"
                        f"      stop: 0 {_rgba(role_color, 0.35)}, stop: 1 {_rgba(role_color, 0.50)});\n"
                        f"  border: 1px solid {_rgba(role_color, 0.55)};\n"
                        f"}}\n"
                        f"QPushButton#{btn.objectName()}:hover {{\n"
                        f"  background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,\n"
                        f"      stop: 0 {_rgba(role_color, 0.45)}, stop: 1 {_rgba(role_color, 0.60)});\n"
                        f"  border-color: {_rgba(role_color, 0.65)};\n"
                        f"}}\n"
                        f"QPushButton#{btn.objectName()}:pressed {{\n"
                        f"  background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,\n"
                        f"      stop: 0 {_rgba(role_color, 0.50)}, stop: 1 {_rgba(role_color, 0.65)});\n"
                        f"  border-color: {_rgba(role_color, 0.75)};\n"
                        f"}}\n"
                    )
                    btn.setStyleSheet(_style)
                    # Reinforce via palette at creation time
                    try:
                        pal = btn.palette()
                        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
                        btn.setPalette(pal)
                    except Exception:
                        pass
                    # Append a final selector-scoped rule to ensure override
                    btn.setStyleSheet(btn.styleSheet() + f"\nQPushButton#{btn.objectName()} {{ color: #ffffff; }}\n")
            except Exception:
                btn.setStyleSheet("padding: 6px 12px; font-size: 12px;")
        self.current_filter = 'all'
        self.filter_all_btn.clicked.connect(lambda: self._set_filter('all'))
        self.filter_success_btn.clicked.connect(lambda: self._set_filter('completed'))
        self.filter_failed_btn.clicked.connect(lambda: self._set_filter('failed'))
        # After creating buttons, sync text color by theme
        try:
            self._update_filter_text_color_by_theme()
        except Exception:
            pass
        filter_row.addWidget(self.filter_label)
        filter_row.addWidget(self.filter_all_btn)
        filter_row.addWidget(self.filter_success_btn)
        filter_row.addWidget(self.filter_failed_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        # Ensure filter button styles are reapplied on theme changes
        try:
            self._restyle_filters()
        except Exception:
            pass

        # Info label with enhanced styling
        self.history_info_label = QLabel("Download history (last 30 downloads)")
        try:
            from theme import get_palette, get_current_theme_key, Theme
            _p = get_palette()
            _key = get_current_theme_key()
            if _key == Theme.DARK:
                _color = "#ffffff"
            elif _key in (Theme.DEFAULT, Theme.YOUTUBE):
                _color = "#000000"
            else:
                _color = _p['text']
            self.history_info_label.setStyleSheet(f"font-weight: 600; color: {_color}; padding: 8px 12px;")
        except Exception:
            self.history_info_label.setStyleSheet("font-weight: 600; color: #1e293b; padding: 8px 12px;")
        layout.addWidget(self.history_info_label)

        # Scroll area for history with enhanced styling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Enhanced scrollbar styling
        scroll.setStyleSheet("""
            QScrollBar:vertical {
                background: rgba(226, 232, 240, 0.5);
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                           stop: 0 #cbd5e1, stop: 1 #94a3b8);
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                           stop: 0 #94a3b8, stop: 1 #64748b);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setSpacing(8)
        self.history_layout.setContentsMargins(5, 5, 5, 5)

        # Add shadow to scroll area
        scroll_shadow = QGraphicsDropShadowEffect()
        scroll_shadow.setBlurRadius(8)
        scroll_shadow.setXOffset(0)
        scroll_shadow.setYOffset(2)
        scroll_shadow.setColor(QColor(0, 0, 0, 15))
        scroll.setGraphicsEffect(scroll_shadow)

        scroll.setWidget(self.history_widget)
        layout.addWidget(scroll)

    def load_initial_data(self):
        """Load initial data for both tabs"""
        try:
            self.load_realtime_logs()
            self.load_history()
        except Exception as e:
            print(f"Error loading initial data: {e}")

    def load_realtime_logs(self):
        """Load existing real-time logs"""
        try:
            logs = self.log_manager.get_realtime_logs()
            # Force all text color per theme (white in Dark, black in Default/YouTube)
            from theme import get_current_theme_key, Theme
            _key = get_current_theme_key()
            forced_color = '#ffffff' if _key == Theme.DARK else '#000000'
            self.realtime_text.clear()

            for log_entry in logs:
                level = log_entry.get('level', 'INFO')
                timestamp = log_entry.get('timestamp', '')
                message = log_entry.get('message', '')

                # Force prefix and message to the same theme-driven color
                formatted_log = f'<span style="color: {forced_color}; font-weight: 500;">[{timestamp}] [{level}]</span> <span style="color: {forced_color};">{message}</span>'
                self.realtime_text.append(formatted_log)

            # Scroll to bottom
            cursor = self.realtime_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.realtime_text.setTextCursor(cursor)
        except Exception as e:
            print(f"Error loading realtime logs: {e}")
            self.realtime_text.setText(f"Error loading logs: {str(e)}")

    def add_realtime_log(self, formatted_message, level):
        """Add new real-time log entry"""
        try:
            if self.isVisible() and self.tabs.currentWidget() == self.realtime_tab:
                # Force both prefix and message to the theme-driven color
                from theme import get_current_theme_key, Theme
                _key = get_current_theme_key()
                forced_color = '#ffffff' if _key == Theme.DARK else '#000000'
                # Extract the message part after the timestamp
                message_parts = formatted_message.split("] ", 1)
                message = message_parts[-1] if len(message_parts) > 1 else formatted_message
                timestamp = datetime.now().strftime("%H:%M:%S")
                formatted_log = f'<span style="color: {forced_color}; font-weight: 500;">[{timestamp}] [{level}]</span> <span style="color: {forced_color};">{message}</span>'
                self.realtime_text.append(formatted_log)

                # Auto-scroll to bottom
                cursor = self.realtime_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.realtime_text.setTextCursor(cursor)
        except Exception as e:
            print(f"Error adding realtime log: {e}")

    def get_log_color(self, level):
        """Get color for log level"""
        colors = {
            'INFO': '#60a5fa',  # Blue
            'SUCCESS': '#34d399',  # Green
            'PROGRESS': '#fbbf24',  # Yellow
            'ERROR': '#f87171',  # Red
            'WARNING': '#fb923c',  # Orange
            'DEBUG': '#9ca3af'  # Gray
        }
        return colors.get(level, '#e2e8f0')  # Default light gray

    def load_history(self):
        """Load download history"""
        try:
            # Clear existing history widgets safely
            while self.history_layout.count():
                child = self.history_layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)

            history = self.log_manager.get_download_history()

            if not history:
                no_history_frame = QFrame()
                no_history_frame.setStyleSheet("""
                    QFrame {
                        background: rgba(248, 250, 252, 0.8);
                        border: 2px dashed #cbd5e1;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 10px;
                    }
                """)
                no_history_layout = QVBoxLayout(no_history_frame)
                no_history_label = QLabel("📂 No download history available")
                no_history_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                try:
                    from theme import get_current_theme_key, Theme
                    _key = get_current_theme_key()
                    forced = '#ffffff' if _key == Theme.DARK else '#000000'
                    no_history_label.setStyleSheet(
                        f"color: {forced}; font-style: italic; font-size: 16px; font-weight: 500;"
                    )
                except Exception:
                    no_history_label.setStyleSheet(
                        "color: #1e293b; font-style: italic; font-size: 16px; font-weight: 500;"
                    )
                no_history_layout.addWidget(no_history_label)
                self.history_layout.addWidget(no_history_frame)
                return

            # Apply filter and show most recent first
            filtered = []
            if self.current_filter == 'all':
                filtered = history
            else:
                filtered = [e for e in history if e.get('status') == self.current_filter]
            for entry in reversed(filtered):
                self.create_history_entry_widget(entry)

            # Add stretch at the end
            self.history_layout.addStretch()
        except Exception as e:
            print(f"Error loading history: {e}")
            error_frame = QFrame()
            error_frame.setStyleSheet("""
                QFrame {
                    background: rgba(254, 242, 242, 0.9);
                    border: 2px solid #fecaca;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 10px;
                }
            """)
            error_layout = QVBoxLayout(error_frame)
            error_label = QLabel(f"❌ Error loading history: {str(e)}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #dc2626; font-style: italic; font-size: 14px; font-weight: 500;")
            error_layout.addWidget(error_label)
            self.history_layout.addWidget(error_frame)

    def create_history_entry_widget(self, entry):
        """Create a widget for a history entry"""
        try:
            try:
                from theme import get_palette, get_current_theme_key, Theme
                _p = get_palette()
                _key = get_current_theme_key()
                if _key == Theme.DARK:
                    _text = '#ffffff'
                elif _key in (Theme.DEFAULT, Theme.YOUTUBE):
                    _text = '#000000'
                else:
                    _text = _p['text']
            except Exception:
                _p, _text = None, "#e5e7eb"
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.NoFrame)

            # Set object name based on status for styling
            status = entry.get('status', 'unknown')
            if status == 'completed':
                frame.setObjectName("history_entry_success")
            elif status == 'failed':
                frame.setObjectName("history_entry_failed")
            else:
                frame.setObjectName("history_entry")

            # Add shadow effect to each entry
            entry_shadow = QGraphicsDropShadowEffect()
            entry_shadow.setBlurRadius(8)
            entry_shadow.setXOffset(0)
            entry_shadow.setYOffset(2)
            entry_shadow.setColor(QColor(0, 0, 0, 15))
            frame.setGraphicsEffect(entry_shadow)

            layout = QVBoxLayout(frame)
            layout.setSpacing(8)
            layout.setContentsMargins(16, 12, 16, 12)

            # Title and status row
            title_layout = QHBoxLayout()
            title_layout.setSpacing(12)

            title = entry.get('title', 'Unknown Title')
            if len(title) > 65:  # Slightly more generous length
                title = title[:62] + "..."

            title_label = QLabel(f"{title}")
            title_label.setStyleSheet(f"font-weight: 600; color: {_text}; font-size: 15px; padding: 2px 0px;")
            title_label.setWordWrap(True)

            status_color = '#22c55e' if status == 'completed' else '#ef4444' if status == 'failed' else '#6366f1'
            status_label = QLabel(f"{status.upper()}")
            try:
                # Use high-contrast text in dark; colored text in light themes
                from theme import get_current_theme_key, Theme
                _key = get_current_theme_key()
                if _key == Theme.DARK:
                    # Dark: light text on a soft tinted badge
                    if status == 'completed':
                        badge_bg = 'rgba(34, 197, 94, 0.18)'
                    elif status == 'failed':
                        badge_bg = 'rgba(239, 68, 68, 0.18)'
                    else:
                        badge_bg = 'rgba(99, 102, 241, 0.18)'
                    status_label.setStyleSheet(
                        f"color: {_text}; font-weight: 700; font-size: 13px; padding: 4px 8px; "
                        f"background: {badge_bg}; border-radius: 6px; border: 1px solid transparent;"
                    )
                else:
                    status_label.setStyleSheet(f"""
                        color: {_text};
                font-weight: 700; 
                font-size: 13px;
                padding: 4px 8px;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 6px;
                border: 1px solid {status_color}40;
            """)
            except Exception:
                status_label.setStyleSheet(f"color: {status_color}; font-weight: 700; font-size: 13px; padding: 4px 8px;")
            status_label.setFixedHeight(28)

            title_layout.addWidget(title_label, 1)
            title_layout.addWidget(status_label, 0)
            layout.addLayout(title_layout)

            # Details row 1 - Date and Resolution
            details1_layout = QHBoxLayout()
            details1_layout.setSpacing(20)

            timestamp_str = entry.get('timestamp')
            date_text = "Unknown Date"
            if timestamp_str:
                try:
                    if 'T' in timestamp_str:
                        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    date_text = f"{dt.strftime('%Y-%m-%d %H:%M:%S')}"
                except (ValueError, TypeError):
                    date_text = f"{timestamp_str}"

            # Date row with calendar SVG icon
            date_icon_label = QLabel()
            try:
                from theme import load_svg_icon
                _cal_icon = load_svg_icon("assets/icons/calendar.svg", None, 14)
                date_icon_label.setPixmap(_cal_icon.pixmap(14, 14))
            except Exception:
                date_icon_label.setText("📅")
                date_icon_label.setStyleSheet(f"color: {_text}; font-size: 12px; font-weight: 500;")

            date_label = QLabel(date_text)
            date_label.setStyleSheet(f"color: {_text}; font-size: 12px; font-weight: 500;")

            resolution_label = QLabel(f"{entry.get('resolution', 'Unknown')}")
            resolution_label.setStyleSheet(f"color: {_text}; font-size: 12px; font-weight: 500;")

            details1_layout.addWidget(date_icon_label)
            details1_layout.addWidget(date_label)
            details1_layout.addWidget(resolution_label)
            details1_layout.addStretch()
            layout.addLayout(details1_layout)

            # Details row 2 - Duration, Size, and Features
            details2_layout = QHBoxLayout()
            details2_layout.setSpacing(20)

            duration = entry.get('duration')
            if duration and duration != 'Unknown':
                duration_label = QLabel(f"{duration}")
                duration_label.setStyleSheet(f"color: {_text}; font-size: 12px; font-weight: 500;")
                details2_layout.addWidget(duration_label)

            file_size = entry.get('file_size')
            if file_size:
                size_label = QLabel(f"{file_size}")
                size_label.setStyleSheet(f"color: {_text}; font-size: 12px; font-weight: 500;")
                details2_layout.addWidget(size_label)

            # Feature tags
            features_layout = QHBoxLayout()
            features_layout.setSpacing(8)

            # Audio-only indicator (icon) when resolution is 'Audio'
            try:
                res_text = str(entry.get('resolution', '') or '').strip().lower()
                if res_text == 'audio':
                    audio_icon_label = QLabel()
                    try:
                        from theme import load_svg_icon
                        audio_icon = load_svg_icon("assets/icons/audio.svg", None, 14)
                        audio_icon_label.setPixmap(audio_icon.pixmap(14, 14))
                    except Exception:
                        audio_icon_label.setText("Audio")
                        audio_icon_label.setStyleSheet(f"color: {_text}; font-size: 10px; font-weight: 600;")
                    features_layout.addWidget(audio_icon_label)
            except Exception:
                pass

            if entry.get('batch_mode'):
                batch_tag = QLabel("Batch")
                batch_tag.setStyleSheet(f"""
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                               stop: 0 #ddd6fe, stop: 1 #c4b5fd);
                    color: {_text};
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                """)
                features_layout.addWidget(batch_tag)

            if entry.get('download_subs'):
                subs_tag = QLabel("Subs")
                subs_tag.setStyleSheet(f"""
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                               stop: 0 #fed7aa, stop: 1 #fdba74);
                    color: {_text};
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                """)
                features_layout.addWidget(subs_tag)

            details2_layout.addLayout(features_layout)
            details2_layout.addStretch()
            layout.addLayout(details2_layout)

            # Error message if failed
            if status == 'failed' and entry.get('error'):
                error_msg = str(entry['error'])
                if len(error_msg) > 120:  # More generous error message length
                    error_msg = error_msg[:117] + "..."

                error_frame = QFrame()
                error_frame.setStyleSheet("""
                    QFrame {
                        background: rgba(254, 226, 226, 0.8);
                        border: 1px solid #fca5a5;
                        border-radius: 6px;
                        padding: 8px;
                        margin-top: 4px;
                    }
                """)
                error_layout = QVBoxLayout(error_frame)
                error_layout.setContentsMargins(8, 6, 8, 6)

                error_label = QLabel(f"{error_msg}")
                try:
                    from theme import get_current_theme_key, Theme
                    _key = get_current_theme_key()
                    forced = '#ffffff' if _key == Theme.DARK else '#000000'
                    error_label.setStyleSheet(f"color: {forced}; font-size: 12px; font-style: italic; font-weight: 500;")
                except Exception:
                    error_label.setStyleSheet("color: #1e293b; font-size: 12px; font-style: italic; font-weight: 500;")
                error_label.setWordWrap(True)
                error_layout.addWidget(error_label)
                layout.addWidget(error_frame)

            # Actions row
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(10)
            open_folder_btn = QPushButton("Open Folder")
            open_folder_btn.setFixedHeight(28)
            retry_btn = QPushButton("Retry")
            retry_btn.setFixedHeight(28)
            # Theme-aware contrast for action buttons
            try:
                from theme import get_palette, get_current_theme_key, Theme
                _p = get_palette()
                _key = get_current_theme_key()
                if _key == Theme.DARK:
                    # Use themed info button style in dark
                    from theme import button_style
                    open_folder_btn.setStyleSheet(button_style('info', radius=6, padding='6px 12px'))
                    retry_btn.setStyleSheet(button_style('primary', radius=6, padding='6px 12px'))
                else:
                    # Light/YouTube: neutral outline buttons with dark text
                    actions_qss = f"""
                        QPushButton {{
                            background: transparent;
                            color: #000000;
                            border: 1px solid {_p['border']};
                            border-radius: 6px;
                            padding: 6px 12px;
                            font-weight: 600;
                        }}
                        QPushButton:hover {{
                            background: {_rgba(_p['primary'], 0.10)};
                            border-color: {_rgba(_p['primary'], 0.35)};
                        }}
                        QPushButton:pressed {{
                            background: {_rgba(_p['primary'], 0.16)};
                            border-color: {_rgba(_p['primary'], 0.45)};
                        }}
                    """
                    open_folder_btn.setStyleSheet(actions_qss)
                    retry_btn.setStyleSheet(actions_qss)
            except Exception:
                pass

            def _open_folder(path):
                try:
                    if not path:
                        return
                    import platform, subprocess
                    if platform.system().lower() == 'darwin':
                        subprocess.Popen(['open', path])
                    elif platform.system().lower() == 'windows':
                        os.startfile(path)
                    else:
                        subprocess.Popen(['xdg-open', path])
                except Exception as e:
                    print(f"Error opening folder: {e}")

            open_folder_btn.clicked.connect(lambda _, p=entry.get('download_path'): _open_folder(p))

            def _retry():
                if callable(self.on_retry):
                    self.on_retry({
                        'url': entry.get('url'),
                        'resolution': entry.get('resolution'),
                        'download_subs': entry.get('download_subs', False),
                        'download_path': entry.get('download_path'),
                        'batch_mode': entry.get('batch_mode', False)
                    })

            retry_btn.clicked.connect(_retry)

            # Enable/disable actions based on status
            try:
                if status == 'completed':
                    retry_btn.setEnabled(False)
                    retry_btn.setToolTip("Already downloaded successfully")
                else:
                    # Not completed (failed or other): allow retry
                    retry_btn.setEnabled(True)
                # Disable 'Open Folder' for failed entries or when path missing
                dl_path = entry.get('download_path')
                if status == 'failed' or not dl_path:
                    open_folder_btn.setEnabled(False)
                    open_folder_btn.setToolTip("Unavailable for failed downloads or missing file path")
                else:
                    open_folder_btn.setEnabled(True)
            except Exception:
                pass

            actions_layout.addWidget(open_folder_btn)
            actions_layout.addStretch()
            actions_layout.addWidget(retry_btn)
            layout.addLayout(actions_layout)

            self.history_layout.addWidget(frame)
        except Exception as e:
            print(f"Error creating history entry: {e}")

    def refresh_data(self):
        """Refresh all data safely"""
        try:
            # Reload history from file in case it was updated externally
            self.log_manager.download_history = self.log_manager.load_history()

            # Refresh both tabs
            self.load_realtime_logs()
            self.load_history()

            # Show success message briefly in the current tab
            current_tab = self.tabs.currentWidget()
            if current_tab == self.history_tab and hasattr(self, 'history_layout'):
                success_frame = QFrame()
                success_frame.setStyleSheet("""
                    QFrame {
                        background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                                   stop: 0 #dcfce7, stop: 1 #bbf7d0);
                        border: 2px solid #86efac;
                        border-radius: 8px;
                        padding: 12px;
                        margin: 5px;
                    }
                """)
                success_layout = QVBoxLayout(success_frame)
                success_label = QLabel("Data refreshed successfully")
                success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                try:
                    from theme import get_current_theme_key, Theme
                    _key = get_current_theme_key()
                    forced = '#ffffff' if _key == Theme.DARK else '#000000'
                    success_label.setStyleSheet(f"color: {forced}; font-weight: 600; font-size: 14px;")
                except Exception:
                    success_label.setStyleSheet("color: #1e293b; font-weight: 600; font-size: 14px;")
                success_layout.addWidget(success_label)
                self.history_layout.insertWidget(0, success_frame)

                # Remove the success message after 2 seconds
                QTimer.singleShot(2000, lambda: success_frame.setParent(None))

        except Exception as e:
            print(f"Error refreshing data: {e}")
            # Show error message in the dialog
            if hasattr(self, 'history_layout'):
                error_frame = QFrame()
                error_frame.setStyleSheet("""
                    QFrame {
                        background: rgba(254, 242, 242, 0.9);
                        border: 2px solid #fca5a5;
                        border-radius: 8px;
                        padding: 12px;
                        margin: 5px;
                    }
                """)
                error_layout = QVBoxLayout(error_frame)
                error_label = QLabel(f"Error refreshing data: {str(e)}")
                error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                try:
                    from theme import get_current_theme_key, Theme
                    _key = get_current_theme_key()
                    forced = '#ffffff' if _key == Theme.DARK else '#000000'
                    error_label.setStyleSheet(f"color: {forced}; font-weight: 600; font-size: 14px;")
                except Exception:
                    error_label.setStyleSheet("color: #1e293b; font-weight: 600; font-size: 14px;")
                error_layout.addWidget(error_label)
                self.history_layout.insertWidget(0, error_frame)

    def clear_realtime_logs(self):
        """Clear real-time logs safely"""
        try:
            self.log_manager.clear_realtime_logs()
            self.realtime_text.clear()

            # Add a confirmation message
            try:
                from theme import get_current_theme_key, Theme
                _key = get_current_theme_key()
                forced = '#ffffff' if _key == Theme.DARK else '#000000'
            except Exception:
                forced = '#000000'
            confirmation_msg = f'<span style="color: {forced}; font-weight: 600;">[SYSTEM] Real-time logs have been cleared</span>'
            self.realtime_text.append(confirmation_msg)
        except Exception as e:
            print(f"Error clearing logs: {e}")

    def closeEvent(self, event):
        """Handle dialog close event"""
        try:
            self.hide()  # Hide instead of closing so we can reuse the dialog
            event.ignore()
        except Exception as e:
            print(f"Error closing dialog: {e}")
            event.accept()  # Accept the close event if there's an error

    def showEvent(self, event):
        """Ensure styles are enforced when dialog is shown (after theme changes)."""
        try:
            self._apply_header_label_colors()
            self._restyle_filters()
            self._update_filter_text_color_by_theme()
        except Exception:
            pass
        super().showEvent(event)

    def _set_filter(self, status_key: str):
        self.current_filter = status_key
        self.load_history()

    def apply_theme_styles(self):
        """Re-apply theme-driven styles for dialog buttons at runtime."""
        try:
            from theme import button_style
        except Exception:
            return
        try:
            # Re-apply palette-driven dialog stylesheet first
            try:
                self.setStyleSheet(self._build_styles())
            except Exception:
                pass
            if hasattr(self, 'clear_logs_btn') and self.clear_logs_btn:
                self.clear_logs_btn.setStyleSheet(button_style('warn'))
            if hasattr(self, 'refresh_btn') and self.refresh_btn:
                self.refresh_btn.setStyleSheet(button_style('primary'))
            if hasattr(self, 'close_btn') and self.close_btn:
                self.close_btn.setStyleSheet(button_style('primary', radius=6, padding='10px 18px'))
            # Ensure header labels follow strict color rules per theme
            try:
                self._apply_header_label_colors()
            except Exception:
                pass
            # Ensure filter text color is forced based on theme
            try:
                self._update_filter_text_color_by_theme()
            except Exception:
                pass
        except Exception:
            pass

    def _apply_header_label_colors(self):
        """Force header label colors: white in Dark, black in Default/YouTube."""
        try:
            from theme import get_palette, get_current_theme_key, Theme
            _p = get_palette()
            _key = get_current_theme_key()
            if _key == Theme.DARK:
                color = "#ffffff"
            elif _key in (Theme.DEFAULT, Theme.YOUTUBE):
                color = "#000000"
            else:
                color = _p['text']
            if hasattr(self, 'realtime_info_label') and self.realtime_info_label:
                self.realtime_info_label.setStyleSheet(f"font-weight: 600; color: {color}; padding: 8px 12px;")
            if hasattr(self, 'history_info_label') and self.history_info_label:
                self.history_info_label.setStyleSheet(f"font-weight: 600; color: {color}; padding: 8px 12px;")
            if hasattr(self, 'filter_label') and self.filter_label:
                # Filter label uses same white/black rule
                self.filter_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        except Exception:
            pass

    def _update_filter_text_color_by_theme(self):
        """Toggle FilterButton text color according to theme (white in dark, black otherwise)."""
        try:
            from theme import get_current_theme_key, Theme
            key = get_current_theme_key()
            is_dark = (key == Theme.DARK) or (getattr(key, 'name', str(key)) == 'DARK')
            for btn in (self.filter_all_btn, self.filter_success_btn, self.filter_failed_btn):
                if isinstance(btn, FilterButton):
                    btn.set_dark_mode(is_dark)
        except Exception:
            pass

    def _build_styles(self) -> str:
        """Build palette-driven stylesheet for the log dialog (light/dark compatible)."""
        try:
            from theme import get_palette, get_current_theme_key, Theme
            p = get_palette()
            key = get_current_theme_key()
        except Exception:
            return self.styleSheet()
        surface = p['surface']
        text = '#ffffff' if 'key' in locals() and key == Theme.DARK else p['text']
        border = p['border']
        primary = p['primary']
        primaryHover = p['primaryHover']
        # Realtime log area colors per theme
        if 'key' in locals() and key == Theme.DARK:
            qte_bg = '#2e2e2e'
            qte_text = '#ffffff'
            header_text = text
        elif 'key' in locals() and key == Theme.DEFAULT:
            qte_bg = '#f3f4f6'
            qte_text = '#000000'
            header_text = '#000000'
        else:  # YouTube
            qte_bg = '#f3f4f6'
            qte_text = '#000000'
            header_text = p['text']
        return f"""
            QDialog {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 12px;
                font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', 'Arial', sans-serif;
            }}
            QLabel {{ color: {header_text}; font-weight: 500; font-size: 14px; }}
            QTabWidget {{ background: transparent; border: none; }}
            QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; margin-top: 8px; }}
            QTabBar {{ background: transparent; }}
            QTabBar::tab {{ background: {surface}; color: {header_text}; border: 1px solid {border}; padding: 12px 24px; margin-right: 4px; margin-top: 4px; border-radius: 10px; font-weight: 600; font-size: 14px; min-width: 120px; text-align: center; }}
            QTabBar::tab:hover {{ background: {_rgba(primary, 0.10)}; border: 1px solid {_rgba(primaryHover, 0.35)}; }}
            QTabBar::tab:selected {{ background: {_rgba(primary, 0.18)}; color: {header_text}; border: 1px solid {_rgba(primaryHover, 0.45)}; margin-top: 0px; }}
            QTextEdit {{ background: {qte_bg}; color: {qte_text}; border: 1px solid {border}; border-radius: 10px; padding: 12px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 12px; selection-background-color: {primaryHover}; }}
            QTextEdit:focus {{ border: 1px solid {primary}; }}
            QScrollArea {{ background: transparent; border: none; border-radius: 10px; }}
            QScrollArea QWidget {{ background: transparent; }}
            QFrame[objectName="history_entry"] {{ background: {_rgba(text, 0.02)}; border: 1px solid {border}; border-radius: 12px; margin: 6px; padding: 0px; }}
            QFrame[objectName="history_entry"]:hover {{ border: 1px solid {_rgba(primary, 0.35)}; background: {_rgba(primary, 0.06)}; }}
            QFrame[objectName="history_entry_success"] {{ background: {_rgba('#22c55e', 0.10)}; border: 1px solid {_rgba('#22c55e', 0.35)}; }}
            QFrame[objectName="history_entry_failed"] {{ background: {_rgba('#ef4444', 0.10)}; border: 1px solid {_rgba('#ef4444', 0.35)}; }}
        """

def _hex_to_rgb(h: str):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgba(h: str, a: float) -> str:
    r, g, b = _hex_to_rgb(h)
    a = 0 if a < 0 else 1 if a > 1 else a
    return f"rgba({r}, {g}, {b}, {a:.2f})"


# Global log manager instance
log_manager = LogManager()