import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QFileDialog,
    QSplitter, QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor, QPixmap, QTransform, QPainter, QMovie
import os


class AnimatedButton(QPushButton):
    """Custom button with animation support"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._animation = QPropertyAnimation(self, b"color")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def enterEvent(self, event):
        self._animation.setDirection(QPropertyAnimation.Direction.Forward)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animation.setDirection(QPropertyAnimation.Direction.Backward)
        self._animation.start()
        super().leaveEvent(event)


class IconButton(QPushButton):
    def __init__(self, icon_path: str, base_icon_px: int, hover_icon_px: int, effect_color: QColor, parent=None):
        super().__init__("", parent)
        self._icon_path = icon_path
        self._base_icon_px = int(base_icon_px)
        self._hover_icon_px = int(hover_icon_px)
        self._effect_color = effect_color
        # Transparent style; no background
        self.setStyleSheet("QPushButton{background:transparent;border:none;padding:0px;} QPushButton:hover{background:transparent;} QPushButton:pressed{background:transparent;}")
        # Load icon at high res for crisp scaling
        try:
            from theme import load_svg_icon
            self.setIcon(load_svg_icon(self._icon_path, None, max(self._base_icon_px, self._hover_icon_px)))
        except Exception:
            pass
        self.setIconSize(QSize(self._base_icon_px, self._base_icon_px))
        # Glow effect (faint baseline so it's visible pre-hover)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setXOffset(0)
        self._glow.setYOffset(0)
        self._glow.setBlurRadius(6.0)
        self._glow.setColor(QColor(self._effect_color.red(), self._effect_color.green(), self._effect_color.blue(), 60))
        self.setGraphicsEffect(self._glow)
        # Animations
        self._size_anim = QPropertyAnimation(self, b"iconSize", self)
        self._size_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._blur_anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._blur_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

    def enterEvent(self, event):
        try:
            self._blur_anim.stop()
            self._blur_anim.setStartValue(float(self._glow.blurRadius()))
            self._blur_anim.setEndValue(32.0)
            self._blur_anim.setDuration(220)
            self._glow.setColor(QColor(self._effect_color.red(), self._effect_color.green(), self._effect_color.blue(), 175))
            self._blur_anim.start()
            self._size_anim.stop()
            self._size_anim.setStartValue(QSize(self.iconSize().width(), self.iconSize().height()))
            self._size_anim.setEndValue(QSize(self._hover_icon_px, self._hover_icon_px))
            self._size_anim.setDuration(220)
            self._size_anim.start()
        except Exception:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        try:
            self._blur_anim.stop()
            self._blur_anim.setStartValue(float(self._glow.blurRadius()))
            self._blur_anim.setEndValue(6.0)
            self._blur_anim.setDuration(220)
            self._glow.setColor(QColor(self._effect_color.red(), self._effect_color.green(), self._effect_color.blue(), 60))
            self._blur_anim.start()
            self._size_anim.stop()
            self._size_anim.setStartValue(QSize(self.iconSize().width(), self.iconSize().height()))
            self._size_anim.setEndValue(QSize(self._base_icon_px, self._base_icon_px))
            self._size_anim.setDuration(220)
            self._size_anim.start()
        except Exception:
            pass
        super().leaveEvent(event)


class ElidedLabel(QLabel):
    """QLabel that elides long text to a single line (no wrapping)."""
    def __init__(self, text: str = "", parent=None, mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight):
        super().__init__(text, parent)
        self._full_text = text or ""
        self._mode = mode
        self.setWordWrap(False)

    def setText(self, text: str) -> None:
        self._full_text = text or ""
        self._update_elision()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        fm = self.fontMetrics()
        width = self.contentsRect().width()
        elided = fm.elidedText(self._full_text, self._mode, max(0, width))
        QLabel.setText(self, elided)


class MainUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        # Make window resizable with a larger default size
        self.setMinimumSize(800, 520)
        self.resize(980, 640)

        # Enhanced stylesheet with IMPROVED FONT SIZES
        self.setStyleSheet("""
            QWidget {
                font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', 'Arial', sans-serif;
                background-color: #f8fafc;
            }

/* Labels with text shadow effect */
QLabel {
    color: #1e293b;
    font-weight: 500;
    font-size: 14px; /* Increased from 13px */
}

/* Enhanced Input Fields with gradient borders on focus */
QLineEdit {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #ffffff, stop: 1 #f8fafc);
    color: #0f172a;
    border: 2px solid #e2e8f0;
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 14px; /* Increased from 13px */
    font-weight: 400;
}

QLineEdit:focus {
    border: 2px solid transparent;
    background-clip: padding-box;
    background: #ffffff;
    border-image: linear-gradient(135deg, #667eea 0%, #764ba2 100%) 1;
}

QLineEdit:hover {
    border-color: #cbd5e1;
    background: #ffffff;
}

/* Enhanced ComboBox with smooth dropdown animation */
QComboBox {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #ffffff, stop: 1 #f8fafc);
    color: #0f172a;
    border: 2px solid #e2e8f0;
    padding: 10px 14px; /* Increased padding from 9px 12px */
    border-radius: 10px;
    font-weight: 500;
    font-size: 14px; /* Added explicit font size */
    min-height: 20px;
}

QComboBox:hover {
    border: 2px solid transparent;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #f0f9ff, stop: 1 #e0f2fe);
    border-image: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%) 1;
}

QComboBox:on {
    border: 2px solid transparent;
    border-image: linear-gradient(135deg, #667eea 0%, #764ba2 100%) 1;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 35px; /* Increased from 30px */
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #f8fafc, stop: 1 #f1f5f9);
}

QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 6px solid transparent; /* Increased from 5px */
    border-right: 6px solid transparent; /* Increased from 5px */
    border-top: 7px solid #64748b; /* Increased from 6px */
    margin-right: 6px; /* Increased from 5px */
}

/* Smooth dropdown */
QComboBox QAbstractItemView {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 6px; /* Increased from 4px */
    outline: none;
    font-size: 14px; /* Added explicit font size */
}

QComboBox QAbstractItemView::item {
    padding: 8px 12px; /* Added padding for dropdown items */
    border-radius: 4px;
}

/* Enhanced Checkboxes with softer radius and improved text */
QCheckBox {
    color: rgba(51, 65, 85, 0.9);
    padding: 8px; /* Increased from 6px */
    font-weight: 500;
    font-size: 14px; /* Added explicit font size */
    spacing: 10px; /* Increased from 8px */
    border-radius: 4px;
}

QCheckBox::indicator {
    width: 22px; /* Increased from 20px */
    height: 22px; /* Increased from 20px */
    border-radius: 6px;
    border: 2px solid #cbd5e1;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 #ffffff, stop: 1 #f8fafc);
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
    image: url(checkmark.png); /* You can add a custom checkmark image */
}

QCheckBox::indicator:checked:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #a78bfa, stop: 1 #818cf8);
}

/* Download Button with animated gradient - IMPROVED FONT SIZE */
QPushButton {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #6366f1, stop: 0.5 #4f46e5, stop: 1 #4338ca);
    color: white;
    border: none;
    padding: 14px 26px; /* Increased padding from 12px 24px */
    border-radius: 10px;
    font-weight: 600;
    font-size: 15px; /* Increased from 14px */
    letter-spacing: 0.3px;
    min-height: 16px; /* Added minimum height for text */
}

QPushButton:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #818cf8, stop: 0.5 #6366f1, stop: 1 #4f46e5);
}

QPushButton:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #4338ca, stop: 0.5 #3730a3, stop: 1 #312e81);
    padding: 15px 26px 13px 26px; /* Adjusted for pressed effect */
}

/* Cancel Button with red gradient */
QPushButton[objectName="cancel_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #f87171, stop: 0.5 #ef4444, stop: 1 #dc2626);
    font-size: 15px; /* Ensured consistent font size */
}

QPushButton[objectName="cancel_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #fca5a5, stop: 0.5 #f87171, stop: 1 #ef4444);
}

QPushButton[objectName="cancel_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #dc2626, stop: 0.5 #b91c1c, stop: 1 #991b1b);
}

/* Browse Button with glass morphism effect - IMPROVED FONT SIZE */
QPushButton[objectName="browse_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                               stop: 0 rgba(255, 255, 255, 0.9),
                               stop: 1 rgba(255, 255, 255, 0.7));
    color: #4f46e5;
    border: 2px solid;
    border-image: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 100%) 1;
    font-weight: 500;
    font-size: 13px; /* Increased from 11px */
    padding: 12px 16px; /* Added explicit padding */
    min-height: 12px; /* Added minimum height */
}

QPushButton[objectName="browse_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #ede9fe, stop: 1 #ddd6fe);
    border-image: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%) 1;
    color: #6366f1;
}

/* Logs Button with subtle gradient - IMPROVED FONT SIZE */
QPushButton[objectName="logs_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #64748b, stop: 1 #475569);
    color: white;
    border: none;
    padding: 10px 16px; /* Increased from 8px 14px */
    border-radius: 6px;
    font-size: 11px; /* Increased from 9px */
    font-weight: 600;
    min-height: 8px; /* Added minimum height */
}

QPushButton[objectName="logs_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #94a3b8, stop: 1 #64748b);
}

/* Frame styling with subtle shadows */
QFrame {
    background: rgba(255, 255, 255, 0.8);
    border-radius: 12px;
}

/* Splitter styling */
QSplitter::handle {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                               stop: 0 #e2e8f0, stop: 0.5 #cbd5e1, stop: 1 #e2e8f0);
    height: 2px;
}

QSplitter::handle:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                               stop: 0 #a5b4fc, stop: 0.5 #818cf8, stop: 1 #a5b4fc);
}



/* Clear Queue button with matching design to download/cancel buttons */
QPushButton[objectName="clear_queue_button"] {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #fbbf24, stop: 0.5 #f59e0b, stop: 1 #d97706);
    color: white;
    border: none;
    padding: 14px 26px; /* Increased padding to match other buttons */
    border-radius: 10px;
    font-weight: 600;
    font-size: 15px; /* Increased from 14px to match other buttons */
    letter-spacing: 0.3px;
    min-height: 16px; /* Added minimum height */
}

QPushButton[objectName="clear_queue_button"]:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #fcd34d, stop: 0.5 #fbbf24, stop: 1 #f59e0b);
}

QPushButton[objectName="clear_queue_button"]:pressed {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                               stop: 0 #d97706, stop: 0.5 #b45309, stop: 1 #92400e);
    padding: 15px 26px 13px 26px; /* Adjusted for pressed effect */
}
""")
        # Override static stylesheet with palette-driven one so theme colors (YouTube) apply consistently
        try:
            self.setStyleSheet(self._build_styles())
        except Exception:
            pass

        main_layout = QVBoxLayout(self)

        # --- Top Bar with Update Button ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 5)  # Minimal margins
        
        # Settings button (gear) next to update
        self.settings_button = IconButton("assets/icons/settings.svg", base_icon_px=32, hover_icon_px=40, effect_color=QColor(99, 102, 241))
        self.settings_button.setFixedSize(48, 48)
        try:
            from PyQt6.QtWidgets import QSizePolicy as _QSizePolicy
            self.settings_button.setSizePolicy(_QSizePolicy.Policy.Fixed, _QSizePolicy.Policy.Fixed)
            self.settings_button.setMinimumSize(48, 48)
        except Exception:
            pass
        self.settings_button.setToolTip("Settings")
        # Style handled by IconButton

        self.update_button_container = self.create_update_button_layout()
        # Cookie status indicator placed in the top-left
        
        # Cookie status indicator placed in the top-right
        self.cookie_status_layout = QHBoxLayout()
        self.cookie_status_layout.setSpacing(8)
        
        self.cookie_indicator = QLabel("🔒")
        self.cookie_indicator.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #94a3b8;
                padding: 4px;
                margin-right: 4px;
                font-weight: bold;
            }
        """)
        self.cookie_indicator.setToolTip("No cookies available")
        self.cookie_indicator.setVisible(True)  # Always visible to show cookie status
        
        self.cookie_status_text = QLabel("No cookies")
        self.cookie_status_text.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #94a3b8;
                font-weight: 500;
                margin-right: 8px;
            }
        """)
        self.cookie_status_text.setVisible(True)  # Always visible to show cookie status
        
        self.cookie_status_layout.addWidget(self.cookie_indicator)
        self.cookie_status_layout.addWidget(self.cookie_status_text)
        
        # Order: cookies at far left, then stretch, then settings and update at far right
        top_bar_layout.addLayout(self.cookie_status_layout)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.settings_button)
        top_bar_layout.addWidget(self.update_button_container)

        main_layout.addLayout(top_bar_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Split the window vertically
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(2)

        # --- Top Frame for Inputs ---
        top_frame = QFrame()
        # Add drop shadow effect to frame
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 30))
        top_frame.setGraphicsEffect(shadow)

        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(15, 15, 15, 15)
        top_layout.setSpacing(20)

        # Link input and Resolution on same line
        link_res_layout = QHBoxLayout()
        link_res_layout.setSpacing(30)

        # Left side - YouTube Link
        link_section = QHBoxLayout()
        link_section.setSpacing(10)
        self.link_label = QLabel("YouTube Link:")
        self.link_label.setFixedWidth(100)
        self.link_input = QLineEdit()
        self.link_input.setMinimumHeight(40)  # Increased from 35 for better text display
        link_section.addWidget(self.link_label)
        link_section.addWidget(self.link_input)

        # Right side - Resolution
        res_section = QHBoxLayout()
        res_section.setSpacing(10)
        self.res_label = QLabel("Resolution:")
        self.res_label.setFixedWidth(80)
        self.resolution_box = QComboBox()
        self.resolution_box.addItems(["360p", "480p", "720p", "1080p", "Audio"])
        self.resolution_box.setFixedWidth(150)  # Increased from 130 for better text display
        self.resolution_box.setMinimumWidth(150)  # Ensure minimum width
        self.resolution_box.setMinimumHeight(40)  # Increased from 35

        res_section.addWidget(self.res_label)
        res_section.addWidget(self.resolution_box)

        link_res_layout.addLayout(link_section, 2)
        link_res_layout.addLayout(res_section, 1)
        top_layout.addLayout(link_res_layout)

        # Subtitle checkbox and batch/autopaste controls - centered together
        subtitle_layout = QHBoxLayout()
        subtitle_layout.addStretch()  # Add stretch before checkboxes for centering
        
        self.subtitle_checkbox = QCheckBox("Download English Subtitles")
        subtitle_layout.addWidget(self.subtitle_checkbox)
        
        self.batch_checkbox = QCheckBox("Batch Mode")
        self.batch_checkbox.setToolTip("Enable batch mode for multiple downloads")
        
        self.autopaste_checkbox = QCheckBox("Auto-Paste")
        self.autopaste_checkbox.setToolTip("Automatically paste URLs from clipboard")
        
        # New: Choose Format option (opens pre-download selector)
        self.choose_format_checkbox = QCheckBox("Choose Format")
        self.choose_format_checkbox.setToolTip("Show a format/resolution chooser before starting a download")
        
        subtitle_layout.addWidget(self.batch_checkbox)
        subtitle_layout.addWidget(self.autopaste_checkbox)
        subtitle_layout.addWidget(self.choose_format_checkbox)
        subtitle_layout.addStretch()  # Add stretch after checkboxes for centering
        top_layout.addLayout(subtitle_layout)

        # Path input
        path_layout = QHBoxLayout()
        path_layout.setSpacing(15)
        self.path_label = QLabel("Save to:")
        self.path_label.setFixedWidth(100)
        self.path_input = QLineEdit()
        self.path_input.setMinimumHeight(40)  # Increased from 35

        self.browse_button = QPushButton("Browse")
        self.browse_button.setObjectName("browse_button")
        self.browse_button.setFixedWidth(130)  # Increased from 110
        self.browse_button.setMinimumWidth(130)  # Ensure minimum width
        self.browse_button.setMinimumHeight(40)  # Increased from 35
        self.browse_button.clicked.connect(self.select_download_path)
        # Add shadow to browse button
        browse_shadow = QGraphicsDropShadowEffect()
        browse_shadow.setBlurRadius(10)
        browse_shadow.setXOffset(0)
        browse_shadow.setYOffset(2)
        browse_shadow.setColor(QColor(139, 92, 246, 50))
        self.browse_button.setGraphicsEffect(browse_shadow)

        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        top_layout.addLayout(path_layout)

        top_layout.addSpacing(10)

        # Buttons with shadows
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        self.download_button = QPushButton("Download")
        self.download_button.setMinimumHeight(45)  # Increased from 40
        self.download_button.setFixedWidth(130)  # Increased from 120
        try:
            from theme import button_style
            self.download_button.setStyleSheet(button_style('primary'))
        except Exception:
            pass

        # Add glow effect to download button
        download_shadow = QGraphicsDropShadowEffect()
        download_shadow.setBlurRadius(15)
        download_shadow.setXOffset(0)
        download_shadow.setYOffset(3)
        download_shadow.setColor(QColor(99, 102, 241, 80))
        self.download_button.setGraphicsEffect(download_shadow)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(45)  # Increased from 40
        self.cancel_button.setFixedWidth(130)  # Increased from 120
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.cancel_download)
        try:
            from theme import button_style
            self.cancel_button.setStyleSheet(button_style('danger'))
        except Exception:
            pass

        # Add shadow to cancel button
        cancel_shadow = QGraphicsDropShadowEffect()
        cancel_shadow.setBlurRadius(15)
        cancel_shadow.setXOffset(0)
        cancel_shadow.setYOffset(3)
        cancel_shadow.setColor(QColor(239, 68, 68, 80))
        self.cancel_button.setGraphicsEffect(cancel_shadow)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()
        top_layout.addLayout(buttons_layout)

        # Add separator with gradient
        separator_layout = QHBoxLayout()
        separator_layout.setContentsMargins(10, 15, 10, 5)
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.HLine)
        separator_line.setStyleSheet("""
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                       stop: 0 rgba(203, 213, 225, 0),
                                       stop: 0.5 rgba(203, 213, 225, 1),
                                       stop: 1 rgba(203, 213, 225, 0));
            border: none;
            height: 1px;
        """)
        separator_layout.addWidget(separator_line)
        top_layout.addLayout(separator_layout)

        top_frame.setLayout(top_layout)

        # --- Bottom Frame for Status ---
        bottom_frame = QFrame()
        bottom_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        bottom_frame.setFixedHeight(220)
        bottom_shadow = QGraphicsDropShadowEffect()
        bottom_shadow.setBlurRadius(20)
        bottom_shadow.setXOffset(0)
        bottom_shadow.setYOffset(4)
        bottom_shadow.setColor(QColor(0, 0, 0, 30))
        bottom_frame.setGraphicsEffect(bottom_shadow)

        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(15, 10, 15, 15)
        bottom_layout.setSpacing(8)

        # Main status row: status text (left) + small speed (right)
        status_row = QHBoxLayout()
        # Animated activity icon (left of status)
        self.activity_icon = QLabel()
        self.activity_icon.setFixedSize(90, 90)
        self.activity_icon.setVisible(False)
        self.activity_icon.setStyleSheet("background: transparent;")
        status_row.addWidget(self.activity_icon)
        self.status_label = QLabel("Ready to download")
        self.status_label.setStyleSheet("font-size: 13px; color: #64748b; font-weight: 600;")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label)
        bottom_layout.addLayout(status_row)

        # Cookie status indicator (moved to top bar)
        # Removed duplicate section
        
        # Add a small test cookies button (animated)
        self.test_cookies_button = IconButton("assets/icons/search.svg", base_icon_px=20, hover_icon_px=26, effect_color=QColor(99, 102, 241))
        self.test_cookies_button.setFixedSize(32, 32)
        self.test_cookies_button.setToolTip("Test current cookies")
        
        # Add a refresh cookies button (animated)
        self.refresh_cookies_button = IconButton("assets/icons/refresh.svg", base_icon_px=20, hover_icon_px=26, effect_color=QColor(99, 102, 241))
        self.refresh_cookies_button.setFixedSize(32, 32)
        self.refresh_cookies_button.setToolTip("Refresh cookie detection")
        
        # Add both buttons to the cookie status layout
        self.cookie_status_layout.addWidget(self.test_cookies_button)
        self.cookie_status_layout.addWidget(self.refresh_cookies_button)

        # Video details section
        self.details_frame = QFrame()
        self.details_frame.setVisible(False)
        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(0, 5, 0, 0)
        details_layout.setSpacing(4)

        self.filename_label = ElidedLabel("")
        self.filename_label.setStyleSheet("font-size: 13px; color: #334155; font-weight: 700;")
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_speed_row = QHBoxLayout()
        title_speed_row.addWidget(self.filename_label, 1)
        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet("font-size: 10px; color: #10b981; font-weight: 700;")
        self.speed_label.setVisible(False)
        title_speed_row.addWidget(self.speed_label, 0)
        details_layout.addLayout(title_speed_row)

        progress_info_layout = QHBoxLayout()
        progress_info_layout.setSpacing(20)

        self.filesize_label = ElidedLabel("")
        self.filesize_label.setStyleSheet("font-size: 10px; color: #64748b;")

        self.progress_label = ElidedLabel("")
        self.progress_label.setStyleSheet("font-size: 10px; color: #6366f1; font-weight: 600;")

        progress_info_layout.addWidget(self.filesize_label)
        progress_info_layout.addStretch()
        progress_info_layout.addWidget(self.progress_label)

        details_layout.addLayout(progress_info_layout)
        self.details_frame.setLayout(details_layout)
        bottom_layout.addWidget(self.details_frame)

        # Logs button
        logs_layout = QHBoxLayout()
        logs_layout.setContentsMargins(0, 8, 0, 0)

        # Logs button as animated icon-only (SVG only)
        self.logs_button = IconButton("assets/icons/logs.svg", base_icon_px=32, hover_icon_px=40, effect_color=QColor(99, 102, 241))
        try:
            from PyQt6.QtWidgets import QSizePolicy as _QSizePolicy
            self.logs_button.setSizePolicy(_QSizePolicy.Policy.Fixed, _QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        self.logs_button.setFixedSize(48, 48)
        self.logs_button.setToolTip("Logs & History")
        logs_layout.addWidget(self.logs_button)
        logs_layout.addStretch()
        # Shutdown (power) button with red-tinted glow
        self.shutdown_button = IconButton("assets/icons/shutdown.svg", base_icon_px=32, hover_icon_px=40, effect_color=QColor(239, 68, 68))
        self.shutdown_button.setFixedSize(48, 48)
        try:
            from PyQt6.QtWidgets import QSizePolicy as _QSizePolicy
            self.shutdown_button.setSizePolicy(_QSizePolicy.Policy.Fixed, _QSizePolicy.Policy.Fixed)
            self.shutdown_button.setMinimumSize(48, 48)
        except Exception:
            pass
        logs_layout.addWidget(self.shutdown_button)

        bottom_layout.addLayout(logs_layout)
        bottom_frame.setLayout(bottom_layout)

        splitter.addWidget(top_frame)
        splitter.addWidget(bottom_frame)
        splitter.setSizes([500, 220])  # Allocate space considering larger window and bottom rows

        main_layout.addWidget(splitter)

        # Activity animation state via QMovie (pre-rendered GIFs)
        self._activity_mode = None  # 'downloading' | 'retrying' | None
        self._activity_movie = None
        # Animation assets - using animated SVG support!
        self._downloading_assets = [
            "assets/icons/downloading_animation.svg"
        ]
        self._retrying_assets = [
            "assets/icons/retrying_animation.svg"
        ]
        
        # Initialize animation timer for fallback animation
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._tick_activity_anim)
        self._animation_frame = 0

    def create_update_button_layout(self):
        """Minimal update button - clean and simple"""
        # Remove the QFrame container and use the button directly
        self.update_button = IconButton("assets/icons/updated.svg", base_icon_px=36, hover_icon_px=46, effect_color=QColor(99, 102, 241))
        self.update_button.setFixedSize(56, 56)
        try:
            from PyQt6.QtWidgets import QSizePolicy as _QSizePolicy
            self.update_button.setSizePolicy(_QSizePolicy.Policy.Fixed, _QSizePolicy.Policy.Fixed)
            self.update_button.setMinimumSize(56, 56)
        except Exception:
            pass
        # Style handled by IconButton
        return self.update_button

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def select_download_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if path:
            self.path_input.setText(path)

    def update_video_details(self, filename=None, filesize=None, progress=None):
        if filename is not None:
            if len(filename) > 80:
                filename = filename[:77] + "..."
            self.filename_label.setText(f"📹 {filename}")

        if filesize is not None:
            self.filesize_label.setText(f"📁 {filesize}")

        if progress is not None:
            self.progress_label.setText(f"{progress}")

        if (self.filename_label.text() or self.filesize_label.text() or self.progress_label.text() or (self.speed_label.isVisible() and self.speed_label.text())):
            self.details_frame.setVisible(True)

    def reset_video_details(self):
        self.details_frame.setVisible(False)
        self.filename_label.setText("")
        self.filesize_label.setText("")
        self.progress_label.setText("")

    def cancel_download(self):
        self.status_label.setText("Download canceled.")

    def set_update_button_state(self, state):
        """Keep the update button states as they were"""
        if state == "checking":
            self.update_button.setText("")
            self.update_button.setToolTip("Checking for updates...")
            self.update_button.setEnabled(False)
            # keep current icon
        elif state == "up_to_date":
            self.update_button.setText("")
            self.update_button.setToolTip("All components are up to date")
            self.update_button.setEnabled(True)
            # show updated icon
            try:
                from theme import load_svg_icon
                self.update_button.setIcon(load_svg_icon("assets/icons/updated.svg", None, self.update_button.iconSize().width()))
            except Exception:
                pass
        elif state == "update_available":
            self.update_button.setText("")
            self.update_button.setToolTip("Updates available - click to update")
            self.update_button.setEnabled(True)
            # show warning icon when updates are available (per request)
            try:
                from theme import load_svg_icon
                self.update_button.setIcon(load_svg_icon("assets/icons/warning.svg", None, self.update_button.iconSize().width()))
            except Exception:
                pass
        else:
            self.update_button.setText("")
            self.update_button.setToolTip("Check for updates")
            self.update_button.setEnabled(True)
            # keep current icon

    def update_cookie_status(self, has_cookies=False, browser_name=None, status_details=""):
        """Update the cookie status indicator"""
        if has_cookies:
            self.cookie_indicator.setText("🔓")
            self.cookie_indicator.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    color: #10b981;
                    padding: 4px;
                    font-weight: bold;
                }
            """)
            
            # Create detailed tooltip
            tooltip_text = f"Cookies active from {browser_name or 'browser'}"
            if status_details:
                tooltip_text += f"\n{status_details}"
            self.cookie_indicator.setToolTip(tooltip_text)
            
            # Show browser name or status details
            display_text = f"Cookies: {browser_name or 'Active'}"
            if status_details:
                display_text = f"Cookies: {browser_name or 'Active'} ({status_details})"
            
            self.cookie_status_text.setText(display_text)
            self.cookie_status_text.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #10b981;
                    font-weight: 600;
                }
            """)
            
            # Always visible, just update the state
            self.cookie_indicator.setVisible(True)
            self.cookie_status_text.setVisible(True)
        else:
            self.cookie_indicator.setText("🔒")
            self.cookie_indicator.setStyleSheet("""
                QLabel {
                    font-size: 18px;
                    color: #94a3b8;
                    padding: 4px;
                    font-weight: bold;
                }
            """)
            
            # Create detailed tooltip for no cookies state
            tooltip_text = "No cookies available"
            if status_details:
                tooltip_text += f"\n{status_details}"
            self.cookie_indicator.setToolTip(tooltip_text)
            
            # Show status details if available
            display_text = "No cookies"
            if status_details:
                display_text = f"No cookies ({status_details})"
            
            self.cookie_status_text.setText(display_text)
            self.cookie_status_text.setStyleSheet("""
                QLabel {
                    font-size: 12px;
                    color: #94a3b8;
                    font-weight: 500;
                }
            """)
            
            # Always visible, just update the state
            self.cookie_indicator.setVisible(True)
            self.cookie_status_text.setVisible(True)

    def show_file_already_downloaded(self, filename, duration=3000, offer_open=False):
        """Show a message when a file is already downloaded, with optional quick action."""
        self.status_label.setText(f"✅ File already exists: {filename}")

        if offer_open:
            try:
                from PyQt6.QtWidgets import QMessageBox
                from PyQt6.QtCore import QTimer as _QTimer
                import os as _os, platform as _platform, subprocess as _subprocess

                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("File Already Exists")
                # Show only the basename for readability
                base = _os.path.basename(filename) if filename else "file"
                folder = _os.path.dirname(filename) if filename else None
                msg_box.setText(f"This file is already in your folder:\n{base}")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                open_btn = msg_box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
                msg_box.setModal(False)

                def _open_folder():
                    if not folder:
                        return
                    try:
                        system = _platform.system().lower()
                        if system == 'darwin':
                            _subprocess.Popen(['open', folder])
                        elif system == 'windows':
                            _os.startfile(folder)
                        else:
                            _subprocess.Popen(['xdg-open', folder])
                    except Exception:
                        pass

                def _on_clicked(btn):
                    if btn == open_btn:
                        _open_folder()

                msg_box.buttonClicked.connect(_on_clicked)
                msg_box.show()
                _QTimer.singleShot(max(1500, int(duration)), msg_box.close)
            except Exception:
                pass

        # Reset to ready state after showing the message
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(duration, self.reset_to_ready_state)
    
    def reset_to_ready_state(self):
        """Reset the status to ready state"""
        self.status_label.setText("Ready to download - Enter YouTube URL")
        try:
            self.set_activity_state("idle")
        except Exception:
            pass

    def set_speed_text(self, text: str) -> None:
        if text:
            self.speed_label.setText(text)
            self.speed_label.setVisible(True)
            # Ensure details section is visible when speed is shown
            self.details_frame.setVisible(True)
        else:
            self.speed_label.setText("")
            self.speed_label.setVisible(False)

    def set_activity_state(self, mode: str):
        """Disable animated SVGs; rely on status text only."""
        try:
            # Always clear/hide any previous animation state
            self._activity_mode = None
            if self._activity_movie:
                try:
                    self._activity_movie.stop()
                except Exception:
                    pass
                self._activity_movie = None
            if hasattr(self, '_animation_timer'):
                self._animation_timer.stop()
            self.activity_icon.clear()
            self.activity_icon.setVisible(False)
            return
        except Exception:
            self.activity_icon.setVisible(False)
            return
    
    def _tick_activity_anim(self):
        """Provide simple animation for the activity icon"""
        try:
            if not self.activity_icon.isVisible() or not self._activity_mode:
                return
                
            # Create a pulsing/breathing animation effect
            self._animation_frame += 1
            if self._animation_frame > 60:  # Reset after full cycle
                self._animation_frame = 0
                
            # Calculate scale factor for pulsing effect (0.8 to 1.2)
            import math
            scale_factor = 0.8 + 0.4 * math.sin(self._animation_frame * 0.1)
            
            # Apply scale transform
            from PyQt6.QtGui import QTransform
            transform = QTransform()
            transform.scale(scale_factor, scale_factor)
            
            # Get the original pixmap and apply transform
            original_pixmap = self.activity_icon.pixmap()
            if original_pixmap and not original_pixmap.isNull():
                # Calculate new size based on scale
                new_width = int(90 * scale_factor)
                new_height = int(90 * scale_factor)
                
                # Create scaled pixmap
                scaled_pixmap = original_pixmap.scaled(
                    new_width, new_height, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Center the scaled pixmap in the 90x90 space
                from PyQt6.QtGui import QPixmap
                final_pixmap = QPixmap(90, 90)
                final_pixmap.fill(Qt.GlobalColor.transparent)
                
                # Calculate centering offset
                x_offset = (90 - new_width) // 2
                y_offset = (90 - new_height) // 2
                
                # Draw the scaled pixmap centered
                painter = QPainter(final_pixmap)
                painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
                painter.end()
                
                self.activity_icon.setPixmap(final_pixmap)
                
        except Exception as e:
            print(f"Error in animation tick: {e}")
            # Stop animation on error
            if hasattr(self, '_animation_timer'):
                self._animation_timer.stop()
    
    def load_default_settings(self, settings):
        """Load default settings into the UI elements"""
        try:
            # Load default resolution
            default_res = settings.get_default_resolution()
            if default_res in ["360p", "480p", "720p", "1080p", "Audio"]:
                self.resolution_box.setCurrentText(default_res)
            
            # Load default download path
            default_path = settings.get_default_download_path()
            if default_path:
                self.path_input.setText(default_path)
            
            # Load default subtitle preference
            auto_subs = settings.get_auto_download_subs()
            self.subtitle_checkbox.setChecked(auto_subs)
            
        except Exception as e:
            print(f"Error loading default settings: {e}")

    def apply_theme_styles(self):
        """Re-apply theme-driven styles for key buttons at runtime."""
        try:
            from theme import button_style, icon_button_style, get_palette
        except Exception:
            return
        try:
            # Rebuild the window stylesheet from the current theme palette first
            try:
                self.setStyleSheet(self._build_styles())
            except Exception:
                pass
            if hasattr(self, 'download_button') and self.download_button:
                self.download_button.setStyleSheet(button_style('primary'))
            if hasattr(self, 'cancel_button') and self.cancel_button:
                self.cancel_button.setStyleSheet(button_style('danger'))
            # Leave logs_button (IconButton) transparent with its own animation style
            if hasattr(self, 'logs_button') and self.logs_button:
                try:
                    # Only style if it's not our IconButton
                    if not isinstance(self.logs_button, IconButton):
                        self.logs_button.setStyleSheet(button_style('info', radius=6, padding='10px 16px'))
                except Exception:
                    pass
            if hasattr(self, 'update_button') and self.update_button:
                self.update_button.setStyleSheet(icon_button_style('info', radius=18))
            if hasattr(self, 'test_cookies_button') and self.test_cookies_button:
                self.test_cookies_button.setStyleSheet(icon_button_style('info'))
            if hasattr(self, 'refresh_cookies_button') and self.refresh_cookies_button:
                self.refresh_cookies_button.setStyleSheet(icon_button_style('info'))
            if hasattr(self, 'shutdown_button') and self.shutdown_button:
                self.shutdown_button.setStyleSheet(icon_button_style('danger', radius=14))
            # Theme the settings icon button as well
            if hasattr(self, 'settings_button') and self.settings_button:
                self.settings_button.setStyleSheet(icon_button_style('info', radius=16))
            # Theme checkboxes explicitly to override window stylesheet
            p = get_palette()
            checkbox_qss = f"""
            QCheckBox {{
                color: {p['text']};
                padding: 8px;
                font-weight: 500;
                font-size: 14px;
                spacing: 10px;
                border-radius: 4px;
            }}
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border-radius: 6px;
                border: 2px solid {p['border']};
                background: {p['surface']};
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {p['primary']};
                background: {p['surface']};
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid {p['primary']};
                background: {p['primary']};
            }}
            QCheckBox::indicator:checked:hover {{
                background: {p['primaryHover']};
            }}
            """
            for attr in ('subtitle_checkbox', 'batch_checkbox', 'autopaste_checkbox', 'choose_format_checkbox'):
                if hasattr(self, attr) and getattr(self, attr):
                    getattr(self, attr).setStyleSheet(checkbox_qss)
            # Adapt key labels to theme text color for readability
            try:
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.setStyleSheet(f"font-size: 13px; color: {p['text']}; font-weight: 600;")
                if hasattr(self, 'cookie_status_text') and self.cookie_status_text:
                    self.cookie_status_text.setStyleSheet(f"QLabel {{ font-size: 12px; color: {p['text']}; font-weight: 500; }}")
                if hasattr(self, 'filename_label') and self.filename_label:
                    self.filename_label.setStyleSheet(f"font-size: 13px; color: {p['text']}; font-weight: 700;")
                if hasattr(self, 'filesize_label') and self.filesize_label:
                    self.filesize_label.setStyleSheet(f"font-size: 10px; color: {p['text']};")
                if hasattr(self, 'progress_label') and self.progress_label:
                    self.progress_label.setStyleSheet(f"font-size: 10px; color: {p['primary']}; font-weight: 600;")
            except Exception:
                pass
        except Exception:
            pass

    def _build_styles(self) -> str:
        """Build a palette-driven window stylesheet so YouTube/Default/Dark colors apply consistently."""
        try:
            from theme import get_palette, get_current_theme_key, Theme
            p = get_palette()
            theme_key = get_current_theme_key()
        except Exception:
            return self.styleSheet()
        surface = p['surface']
        text = p['text']
        border = p['border']
        primary = p['primary']
        primaryHover = p['primaryHover']
        primaryActive = p.get('primaryActive', primaryHover)
        warn = p.get('warn', '#f59e0b')
        warnHover = p.get('warnHover', '#d97706')
        warnActive = p.get('warnActive', '#b45309')
        danger = p.get('danger', '#ef4444')
        dangerHover = p.get('dangerHover', '#dc2626')
        dangerActive = p.get('dangerActive', '#b91c1c')
 
        def _hex_to_rgb(h: str):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
 
        def _rgba(h: str, a: float) -> str:
            r, g, b = _hex_to_rgb(h)
            a = 0 if a < 0 else 1 if a > 1 else a
            return f"rgba({r}, {g}, {b}, {a:.2f})"
 
        # Inputs/panels: use darker bg in dark theme, white otherwise
        input_bg = '#342a2a' if ('theme_key' in locals() and theme_key == Theme.DARK) else '#ffffff'
 
        # Clear Queue color scheme: orange in Default, red in YouTube; in Dark keep red to stand out
        if 'theme_key' in locals() and theme_key == Theme.DEFAULT:
            clearA, clearB, clearC = warn, warnHover, warnActive
        else:
            clearA, clearB, clearC = danger, dangerHover, dangerActive
 
        # Browse button text colors by theme for proper contrast
        if 'theme_key' in locals() and theme_key == Theme.DARK:
            browse_text = '#f5f7fa'
            browse_text_hover = '#ffffff'
        else:
            browse_text = primary
            browse_text_hover = primaryHover
 
        return f"""
            QWidget {{
                font-family: 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI', 'Arial', sans-serif;
                background-color: {surface};
            }}
            QLabel {{
                color: {text};
                font-weight: 500;
                font-size: 14px;
            }}
            QLineEdit {{
                background: {input_bg};
                color: {text};
                border: 2px solid {border};
                padding: 10px 14px;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 400;
            }}
            QLineEdit:hover {{
                border-color: {primaryHover};
                background: {input_bg};
            }}
            QLineEdit:focus {{
                border: 2px solid {primary};
                background: {input_bg};
            }}
            QComboBox {{
                background: {input_bg};
                color: {text};
                border: 2px solid {border};
                padding: 10px 14px;
                border-radius: 10px;
                font-weight: 500;
                font-size: 14px;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border: 2px solid {primary};
                background: {input_bg};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 35px;
                border-left: 1px solid {border};
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background: {input_bg};
            }}
            QComboBox QAbstractItemView {{
                background: {input_bg};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 6px;
                outline: none;
                font-size: 14px;
            }}
            /* Browse: subtle primary-tinted gradient with light border; keep size/radius unchanged */
            QPushButton[objectName="browse_button"] {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {_rgba(primary, 0.06)},
                                            stop: 1 {_rgba(primaryHover, 0.10)});
                color: {browse_text};
                border: 1px solid {_rgba(primary, 0.25)};
            }}
            QPushButton[objectName="browse_button"]:hover {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {_rgba(primary, 0.10)},
                                            stop: 1 {_rgba(primaryHover, 0.16)});
                border: 1px solid {_rgba(primaryHover, 0.35)};
                color: {browse_text_hover};
            }}
            QPushButton[objectName="browse_button"]:pressed {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {_rgba(primaryHover, 0.18)},
                                            stop: 1 {_rgba(primaryActive, 0.24)});
                border: 1px solid {_rgba(primaryActive, 0.45)};
                color: #ffffff;
            }}
            QFrame {{
                background: {_rgba(surface, 0.80)};
                border-radius: 12px;
            }}
            QSplitter::handle {{
                background: {border};
                height: 2px;
            }}
            /* Clear Queue: themed gradient, preserve existing radius */
            QPushButton[objectName="clear_queue_button"] {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {clearA},
                                            stop: 0.5 {clearB},
                                            stop: 1 {clearC});
                color: #ffffff;
                border: none;
                border-radius: 10px;
            }}
            QPushButton[objectName="clear_queue_button"]:hover {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {clearB},
                                            stop: 0.5 {clearA},
                                            stop: 1 {clearB});
            }}
            QPushButton[objectName="clear_queue_button"]:pressed {{
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                            stop: 0 {clearC},
                                            stop: 0.5 {clearB},
                                            stop: 1 {clearA});
            }}
         """

    def _position_floating_buttons(self):
        return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        return

    def showEvent(self, event):
        super().showEvent(event)
        return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainUI()
    window.show()
    sys.exit(app.exec())