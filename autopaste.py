import re
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class AutoPasteManager(QObject):
    """Manages automatic clipboard monitoring and URL detection."""
    url_detected = pyqtSignal(str)  # new YouTube URL detected
    clipboard_changed = pyqtSignal(str)  # clipboard content changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = False
        self.clipboard = QApplication.clipboard()
        self.last_clipboard_content = ""
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_clipboard)
        self.check_interval = 500  # Check every 500ms

        # YouTube URL patterns
        self.youtube_patterns = [
            # Regular video URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+(?:\?[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+(?:\?[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+(?:\?[\w=&-]*)?',

            # Playlist URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+(?:&[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*list=[\w-]+(?:&[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?.*&list=[\w-]+(?:&[\w=&-]*)?',

            # Shorts URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+(?:\?[\w=&-]*)?',

            # Mobile URLs
            r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w=&-]*)?',
            r'(?:https?://)?(?:m\.)?youtube\.com/playlist\?list=[\w-]+(?:&[\w=&-]*)?',

            # Channel URLs
            r'(?:https?://)?(?:www\.)?youtube\.com/channel/[\w-]+/playlists?(?:\?[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/c/[\w-]+/playlists?(?:\?[\w=&-]*)?',
            r'(?:https?://)?(?:www\.)?youtube\.com/@[\w-]+/playlists?(?:\?[\w=&-]*)?',

            # User playlists
            r'(?:https?://)?(?:www\.)?youtube\.com/user/[\w-]+/playlists?(?:\?[\w=&-]*)?',
        ]

    def enable_autopaste(self):
        """Enable clipboard monitoring."""
        if not self.is_enabled:
            self.is_enabled = True
            self.last_clipboard_content = self.get_clipboard_text()
            self.timer.start(self.check_interval)

    def disable_autopaste(self):
        """Disable clipboard monitoring."""
        if self.is_enabled:
            self.is_enabled = False
            self.timer.stop()

    def set_check_interval(self, interval_ms):
        """Set clipboard check interval in milliseconds."""
        self.check_interval = max(100, interval_ms)  # Minimum 100ms
        if self.timer.isActive():
            self.timer.stop()
            self.timer.start(self.check_interval)

    def get_clipboard_text(self):
        """Get current clipboard text."""
        try:
            mime_data = self.clipboard.mimeData()
            if mime_data.hasText():
                return mime_data.text().strip()
        except Exception:
            pass
        return ""

    def check_clipboard(self):
        """Check clipboard for changes and YouTube URLs."""
        if not self.is_enabled:
            return

        current_content = self.get_clipboard_text()

        # Check if content changed
        if current_content != self.last_clipboard_content:
            self.last_clipboard_content = current_content
            self.clipboard_changed.emit(current_content)

            # Check for YouTube URL
            youtube_url = self.extract_youtube_url(current_content)
            if youtube_url:
                self.url_detected.emit(youtube_url)

    def extract_youtube_url(self, text):
        """Extract YouTube URL from text."""
        if not text:
            return None

        # Check each pattern
        for pattern in self.youtube_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                url = matches[0]
                # Ensure URL has proper protocol
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                return self.clean_youtube_url(url)

        return None

    def clean_youtube_url(self, url):
        """Clean and normalize YouTube URL"""
        if not url:
            return None

        # Remove common tracking parameters but keep important ones like list, v, t
        important_params = ['v', 'list', 't', 'index', 'start']

        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

            parsed = urlparse(url)
            if parsed.query:
                # Parse query parameters
                params = parse_qs(parsed.query, keep_blank_values=True)

                # Keep only important parameters
                cleaned_params = {}
                for key, values in params.items():
                    if key in important_params and values:
                        cleaned_params[key] = values[0]  # Take first value

                # Rebuild query string
                new_query = urlencode(cleaned_params) if cleaned_params else ''

                # Rebuild URL
                cleaned_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))

                return cleaned_url
        except ImportError:
            # Fallback if urllib is not available
            pass

        return url

    def is_youtube_url(self, url):
        """Check if a given URL is a YouTube URL"""
        if not url:
            return False
        return self.extract_youtube_url(url) is not None

    def is_playlist_url(self, url):
        """Check if a given URL is a YouTube playlist URL"""
        if not url:
            return False

        # Check for playlist indicators
        playlist_indicators = [
            'list=',
            '/playlist?',
            '/playlists',
        ]

        url_lower = url.lower()
        return any(indicator in url_lower for indicator in playlist_indicators)

    def get_url_type(self, url):
        """Determine the type of YouTube URL"""
        if not self.is_youtube_url(url):
            return None

        url_lower = url.lower()

        if self.is_playlist_url(url):
            return 'playlist'
        elif '/shorts/' in url_lower:
            return 'shorts'
        elif 'watch?v=' in url_lower or 'youtu.be/' in url_lower:
            return 'video'
        elif '/channel/' in url_lower or '/c/' in url_lower or '/@' in url_lower:
            return 'channel'
        else:
            return 'unknown'

    def validate_youtube_url(self, url):
        """Validate and clean a YouTube URL"""
        if not url:
            return None

        # Extract URL if it's part of a larger text
        clean_url = self.extract_youtube_url(url)
        if clean_url:
            return clean_url

        # If direct URL, validate it
        if self.is_youtube_url(url):
            if not url.startswith(('http://', 'https://')):
                return 'https://' + url
            return self.clean_youtube_url(url)

        return None

    def get_status(self):
        """Get current autopaste status"""
        return {
            'enabled': self.is_enabled,
            'check_interval': self.check_interval,
            'last_content': self.last_clipboard_content[:50] + '...' if len(
                self.last_clipboard_content) > 50 else self.last_clipboard_content
        }


class AutoPasteUI:
    """
    UI helper class for autopaste functionality
    """

    @staticmethod
    def create_autopaste_indicator(parent):
        """Create a visual indicator for autopaste status"""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import Qt

        indicator = QLabel("AutoPaste: OFF")
        indicator.setStyleSheet("""
            QLabel {
                background-color: #f3f4f6;
                color: #6b7280;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return indicator

    @staticmethod
    def update_autopaste_indicator(indicator, is_enabled):
        """Update the autopaste indicator"""
        if is_enabled:
            indicator.setText("AutoPaste: ON")
            indicator.setStyleSheet("""
                QLabel {
                    background-color: #dcfce7;
                    color: #166534;
                    border: 1px solid #bbf7d0;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        else:
            indicator.setText("AutoPaste: OFF")
            indicator.setStyleSheet("""
                QLabel {
                    background-color: #f3f4f6;
                    color: #6b7280;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)


class AutoPasteIntegration:

    def __init__(self, main_controller):
        self.controller = main_controller
        self.autopaste_manager = AutoPasteManager()
        self.autopaste_enabled = False

        # Connect signals
        self.autopaste_manager.url_detected.connect(self.on_url_detected)
        self.autopaste_manager.clipboard_changed.connect(self.on_clipboard_changed)

        # Create UI indicator if UI exists
        if hasattr(self.controller, 'ui'):
            self.setup_ui_integration()

    def setup_ui_integration(self):
        """Set up UI integration for autopaste"""
        # This would be called during UI initialization
        # to add autopaste controls to the interface
        pass

    def toggle_autopaste(self):
        """Toggle autopaste on/off"""
        if self.autopaste_enabled:
            self.disable_autopaste()
        else:
            self.enable_autopaste()

    def enable_autopaste(self):
        """Enable autopaste functionality"""
        self.autopaste_enabled = True
        self.autopaste_manager.enable_autopaste()

        # Update UI if available
        if hasattr(self.controller, 'ui'):
            self.controller.ui.status_label.setText("AutoPaste enabled - Monitoring clipboard")

    def disable_autopaste(self):
        """Disable autopaste functionality"""
        self.autopaste_enabled = False
        self.autopaste_manager.disable_autopaste()

        # Update UI if available
        if hasattr(self.controller, 'ui'):
            if "AutoPaste" in self.controller.ui.status_label.text():
                self.controller.ui.status_label.setText("Ready")

    def on_url_detected(self, url):
        """Handle detected YouTube URL with playlist awareness"""
        if hasattr(self.controller, 'ui'):
            # Auto-fill the URL input field
            self.controller.ui.link_input.setText(url)

            # Determine URL type for better status messaging
            url_type = self.autopaste_manager.get_url_type(url)
            type_to_emoji = {
                'playlist': '',
                'shorts': '',
                'channel': ''
            }

            # Update status with URL type information
            self.controller.ui.status_label.setText(f"{url_type.title()} detected: {url[:30]}...")

            # Optional: Auto-start download if in batch mode
            if hasattr(self.controller, 'batch_manager') and getattr(self.controller.batch_manager, 'is_batch_mode',
                                                                     False):
                # Add to batch queue instead of auto-starting
                self.controller.batch_manager.add_to_batch(url)
                self.controller.ui.status_label.setText(f"{url_type.title()} added to batch queue")

    def on_clipboard_changed(self, content):
        """Handle clipboard content changes"""
        # This can be used for additional processing or logging
        if len(content) > 0 and hasattr(self.controller, 'ui'):
            # Only show brief notification for non-URL content
            if not self.autopaste_manager.is_youtube_url(content):
                # Don't spam with non-URL clipboard changes
                pass

    def set_autopaste_interval(self, interval_ms):
        """Set the autopaste check interval"""
        self.autopaste_manager.set_check_interval(interval_ms)

    def get_autopaste_status(self):
        """Get autopaste status information"""
        return {
            'integration_enabled': self.autopaste_enabled,
            'manager_status': self.autopaste_manager.get_status()
        }

    def manual_paste_check(self):
        """Manually trigger a clipboard check"""
        if self.autopaste_enabled:
            self.autopaste_manager.check_clipboard()

    def validate_and_paste_url(self, url):
        """Validate and paste a URL manually"""
        validated_url = self.autopaste_manager.validate_youtube_url(url)
        if validated_url and hasattr(self.controller, 'ui'):
            self.controller.ui.link_input.setText(validated_url)

            # Show URL type in status
            url_type = self.autopaste_manager.get_url_type(validated_url)
            type_to_emoji = {
                'playlist': '',
                'shorts': '',
                'channel': ''
            }

            if url_type:
                if hasattr(self.controller, 'ui'):
                    self.controller.ui.status_label.setText(
                        f"{url_type.title()} URL validated and pasted")

            return True
        return False


# Utility functions for standalone usage
def create_autopaste_for_ui(ui_widget, link_input_widget):
    """
    Create standalone autopaste functionality for any UI widget

    Args:
        ui_widget: Parent widget for the autopaste manager
        link_input_widget: The input widget where URLs should be pasted
    """
    autopaste = AutoPasteManager(ui_widget)

    def on_url_detected(url):
        link_input_widget.setText(url)

    autopaste.url_detected.connect(on_url_detected)
    return autopaste


def is_youtube_link(text):
    """Check if text contains a YouTube link"""
    autopaste = AutoPasteManager()
    return autopaste.is_youtube_url(text)


def extract_youtube_link(text):
    """Extract YouTube link from text"""
    autopaste = AutoPasteManager()
    return autopaste.extract_youtube_url(text)


def is_playlist_link(text):
    """Check if text contains a YouTube playlist link"""
    autopaste = AutoPasteManager()
    return autopaste.is_playlist_url(text)


def get_youtube_url_type(url):
    """Get the type of YouTube URL (video, playlist, shorts, channel)"""
    autopaste = AutoPasteManager()
    return autopaste.get_url_type(url)