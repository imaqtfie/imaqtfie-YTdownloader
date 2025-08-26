from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt, QSize
try:
    from PyQt6.QtSvg import QSvgRenderer
except Exception:
    QSvgRenderer = None


class Theme:
	DEFAULT = 'default'
	YOUTUBE = 'youtube'
	DARK = 'dark'


def get_qss(theme: str) -> str:
	if theme == Theme.YOUTUBE:
		# YouTube-inspired palette: light background, red accents, dark text
		return """
			QWidget { font-family: 'Segoe UI', Arial, sans-serif; }
			QDialog, QWidget { background: #ffffff; color: #0f172a; }
			QLabel { color: #0f172a; }
			QGroupBox { border: 2px solid #e5e7eb; border-radius: 8px; margin-top: 12px; }
			QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #0f172a; }
			QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; color: #0f172a; border: 2px solid #e5e7eb; border-radius: 8px; padding: 8px 10px; }
			QTableWidget { background: #ffffff; color: #0f172a; gridline-color: #e5e7eb; }
			QHeaderView::section { background: #f3f4f6; color: #111827; border: 1px solid #e5e7eb; padding: 6px; }
			QTabWidget::pane { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }
			QTabBar::tab { background: #f9fafb; color: #0f172a; border: 1px solid #e5e7eb; padding: 8px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; }
			QTabBar::tab:selected { background: #fee2e2; border-color: #fecaca; }
			QTabBar::tab:hover { background: #fef2f2; }
			/* Themed CheckBox */
			QCheckBox { color: #0f172a; padding: 6px; }
			QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #e5e7eb; background: #ffffff; }
			QCheckBox::indicator:hover { border-color: #ff0000; background: #fff1f2; }
			QCheckBox::indicator:checked { border-color: #ff0000; background: #ff0000; }
			QCheckBox::indicator:checked:hover { background: #e60000; }
			/* Themed RadioButton */
			QRadioButton { color: #0f172a; padding: 6px; }
			QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 2px solid #e5e7eb; background: #ffffff; }
			QRadioButton::indicator:hover { border-color: #ff0000; background: #fff1f2; }
			QRadioButton::indicator:checked { border-color: #ff0000; background: #ff0000; }
		"""
	if theme == Theme.DARK:
		# Softer dark gray theme (provided palette): whole window dark, readable text
		return """
			QWidget { font-family: 'SF Pro Display', 'Segoe UI', Arial, sans-serif; }
			/* Surfaces */
			QDialog, QWidget { background: #1f1515; color: #e5e7eb; }
			QFrame { background: #1f1515; }
			QLabel { color: #f3f4f6; }
			QGroupBox { border: 1px solid #4a4141; border-radius: 8px; margin-top: 12px; }
			QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 8px; color: #f3f4f6; }
			/* Inputs */
			QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #342a2a; color: #e5e7eb; border: 1px solid #4a4141; border-radius: 8px; padding: 8px 10px; }
			QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border: 1px solid #67f3fb; }
			QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #43f1fa; }
			/* Tables and headers */
			QTableWidget { background: #342a2a; color: #e5e7eb; gridline-color: #4a4141; }
			QHeaderView::section { background: #342a2a; color: #e5e7eb; border: 1px solid #4a4141; padding: 6px; }
			/* Tabs */
			QTabWidget::pane { background: #1f1515; border: 1px solid #4a4141; border-radius: 8px; }
			QTabBar::tab { background: #342a2a; color: #e5e7eb; border: 1px solid #4a4141; padding: 8px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; }
			QTabBar::tab:selected { background: #525152; border-color: #7a7272; }
			QTabBar::tab:hover { background: #3c3b3c; }
			/* Checkboxes / Radios */
			QCheckBox { color: #e5e7eb; padding: 6px; }
			QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #4a4141; background: #342a2a; }
			QCheckBox::indicator:hover { border-color: #43f1fa; background: #3c3b3c; }
			QCheckBox::indicator:checked { border-color: #43f1fa; background: #43f1fa; }
			QCheckBox::indicator:checked:hover { background: #67f3fb; }
			QRadioButton { color: #e5e7eb; padding: 6px; }
			QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 2px solid #4a4141; background: #342a2a; }
			QRadioButton::indicator:hover { border-color: #43f1fa; background: #3c3b3c; }
			QRadioButton::indicator:checked { border-color: #43f1fa; background: #43f1fa; }
		"""
	# Default: keep current light palette
	return """
		QWidget { font-family: 'SF Pro Display', 'Segoe UI', Arial, sans-serif; }
		/* Default themed CheckBox */
		QCheckBox { color: #1e293b; padding: 6px; }
		QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #e2e8f0; background: #ffffff; }
		QCheckBox::indicator:hover { border-color: #6366f1; background: #eef2ff; }
		QCheckBox::indicator:checked { border-color: #6366f1; background: #6366f1; }
		QCheckBox::indicator:checked:hover { background: #4f46e5; }
		/* Default themed RadioButton */
		QRadioButton { color: #1e293b; padding: 6px; }
		QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 2px solid #e2e8f0; background: #ffffff; }
		QRadioButton::indicator:hover { border-color: #6366f1; background: #eef2ff; }
		QRadioButton::indicator:checked { border-color: #6366f1; background: #6366f1; }
	"""


def apply_theme(app: QApplication, theme: str) -> None:
	app.setStyleSheet(get_qss(theme))
	# Adjust base palette minimal to keep native look
	pal = app.palette()
	if theme == Theme.YOUTUBE:
		pal.setColor(QPalette.ColorRole.Window, QColor('#ffffff'))
		pal.setColor(QPalette.ColorRole.WindowText, QColor('#0f172a'))
		pal.setColor(QPalette.ColorRole.Base, QColor('#ffffff'))
		pal.setColor(QPalette.ColorRole.Text, QColor('#0f172a'))
		pal.setColor(QPalette.ColorRole.Button, QColor('#ff0000'))
		pal.setColor(QPalette.ColorRole.ButtonText, QColor('#ffffff'))
	elif theme == Theme.DARK:
		pal.setColor(QPalette.ColorRole.Window, QColor('#1F1515'))
		pal.setColor(QPalette.ColorRole.WindowText, QColor('#e5e7eb'))
		pal.setColor(QPalette.ColorRole.Base, QColor('#1F1515'))
		pal.setColor(QPalette.ColorRole.Text, QColor('#e5e7eb'))
		pal.setColor(QPalette.ColorRole.Button, QColor('#8b5cf6'))
		pal.setColor(QPalette.ColorRole.ButtonText, QColor('#ffffff'))
	else:
		# Use defaults; no heavy palette changes
		pass
	app.setPalette(pal)


def get_current_theme_key() -> str:
	qs = QSettings('YTDownloader', 'App')
	name = str(qs.value('ui/theme', 'Default'))
	if name == 'YouTube':
		return Theme.YOUTUBE
	if name == 'Dark':
		return Theme.DARK
	return Theme.DEFAULT


def get_palette(theme: str | None = None) -> dict:
	"""Return a centralized palette dictionary for the given theme key."""
	key = theme or get_current_theme_key()
	if key == Theme.YOUTUBE:
		return {
			'primary': '#ff0000',
			'primaryHover': '#e60000',
			'primaryActive': '#cc0000',
			'danger': '#dc2626',
			'dangerHover': '#b91c1c',
			'dangerActive': '#991b1b',
			'success': '#16a34a',
			'successHover': '#15803d',
			'successActive': '#166534',
			'info': '#0ea5e9',
			'infoHover': '#0284c7',
			'infoActive': '#0369a1',
			'warn': '#f59e0b',
			'warnHover': '#d97706',
			'warnActive': '#b45309',
			'surface': '#ffffff',
			'border': '#e5e7eb',
			'text': '#0f172a',
		}
	if key == Theme.DARK:
		return {
			'primary': '#43f1fa',
			'primaryHover': '#67f3fb',
			'primaryActive': '#82f5fb',
			'danger': '#f87171',
			'dangerHover': '#ef4444',
			'dangerActive': '#dc2626',
			'success': '#34d399',
			'successHover': '#10b981',
			'successActive': '#059669',
			'info': '#98f7fc',
			'infoHover': '#acf8fc',
			'infoActive': '#befafd',
			'warn': '#f59e0b',
			'warnHover': '#d97706',
			'warnActive': '#b45309',
			'surface': '#1f1515',
			'border': '#4a4141',
			'text': '#e5e7eb',
		}
	# DEFAULT palette (blue accents similar to current app)
	return {
		'primary': '#6366f1',
		'primaryHover': '#4f46e5',
		'primaryActive': '#4338ca',
		'danger': '#ef4444',
		'dangerHover': '#dc2626',
		'dangerActive': '#b91c1c',
		'success': '#22c55e',
		'successHover': '#16a34a',
		'successActive': '#15803d',
		'info': '#0ea5e9',
		'infoHover': '#0284c7',
		'infoActive': '#0369a1',
		'warn': '#f59e0b',
		'warnHover': '#d97706',
		'warnActive': '#b45309',
		'surface': '#ffffff',
		'border': '#e2e8f0',
		'text': '#1e293b',
	}


def button_style(role: str, *, radius: int = 10, padding: str = '14px 26px') -> str:
	"""Return a QPushButton style for the given semantic role using the current palette."""
	p = get_palette()
	if role == 'primary':
		bg, hov, act = p['primary'], p['primaryHover'], p['primaryActive']
	elif role == 'danger':
		bg, hov, act = p['danger'], p['dangerHover'], p['dangerActive']
	elif role == 'success':
		bg, hov, act = p['success'], p['successHover'], p['successActive']
	elif role == 'info':
		bg, hov, act = p['info'], p['infoHover'], p['infoActive']
	elif role == 'warn':
		bg, hov, act = p['warn'], p['warnHover'], p['warnActive']
	else:
		bg, hov, act = p['primary'], p['primaryHover'], p['primaryActive']
	# Dark theme: use subtle gradient and border for visibility
	try:
		key = get_current_theme_key()
	except Exception:
		key = None
	if key == Theme.DARK:
		return f"""
			QPushButton {{
				background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
					stop: 0 {_rgba_str(bg, 0.65)},
					stop: 1 {_rgba_str(hov, 0.50)});
				color: #f5f7fa;
				border: 1px solid {_rgba_str(bg, 0.30)};
				border-radius: {radius}px;
				padding: {padding};
				font-weight: 600;
			}}
			QPushButton:hover {{
				background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
					stop: 0 {_rgba_str(hov, 0.60)},
					stop: 1 {_rgba_str(bg, 0.55)});
				border-color: {_rgba_str(hov, 0.40)};
			}}
			QPushButton:pressed {{
				background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
					stop: 0 {_rgba_str(act, 0.60)},
					stop: 1 {_rgba_str(hov, 0.50)});
				border-color: {_rgba_str(act, 0.50)};
			}}
		"""
	return f"""
		QPushButton {{
			background: {bg};
			color: #ffffff;
			border: none;
			border-radius: {radius}px;
			padding: {padding};
			font-weight: 600;
		}}
		QPushButton:hover {{
			background: {hov};
		}}
		QPushButton:pressed {{
			background: {act};
		}}
	"""


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
	"""Convert #rrggbb to (r,g,b)."""
	hex_color = hex_color.lstrip('#')
	return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _rgba_str(hex_color: str, alpha: float) -> str:
	"""Return rgba(r,g,b,a) from hex and alpha [0,1]."""
	r, g, b = _hex_to_rgb(hex_color)
	# clamp alpha
	if alpha < 0: alpha = 0
	if alpha > 1: alpha = 1
	return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def icon_button_style(role: str = 'info', *, radius: int = 12) -> str:
	"""Return a fully transparent icon-style QPushButton (no background in any state)."""
	return f"""
		QPushButton {{
			background: transparent;
			border: none;
			border-radius: {radius}px;
			padding: 0px;
			margin: 0px 4px 0px 0px;
		}}
		QPushButton:hover {{
			background: transparent;
		}}
		QPushButton:pressed {{
			background: transparent;
		}}
		QPushButton:disabled {{
			background: transparent;
		}}
	""" 


def load_svg_icon(path: str, hex_color: str | None = None, size: int = 20) -> QIcon:
    """Render an SVG to a QIcon without tint, centered, transparent background.

    - path: filesystem path to SVG
    - hex_color: ignored (kept for API compatibility)
    - size: icon square size in px
    """
    try:
        if QSvgRenderer is None:
            raise RuntimeError("QtSvg not available")
        renderer = QSvgRenderer(path)
        # Render at device pixel ratio for crisp results (retina/HiDPI)
        try:
            from PyQt6.QtGui import QGuiApplication
            dpr = float(QGuiApplication.primaryScreen().devicePixelRatio()) if QGuiApplication.primaryScreen() else 1.0
            if dpr < 1.0:
                dpr = 1.0
        except Exception:
            dpr = 2.0  # sensible default for crispness
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        # Center the SVG preserving aspect ratio within the target square
        try:
            vb = renderer.viewBoxF()
            src_w = vb.width() if vb.width() > 0 else renderer.defaultSize().width()
            src_h = vb.height() if vb.height() > 0 else renderer.defaultSize().height()
            if src_w <= 0 or src_h <= 0:
                # Fallback: render full
                renderer.render(p)
            else:
                scale = min((size * dpr) / src_w, (size * dpr) / src_h)
                target_w = src_w * scale
                target_h = src_h * scale
                x = ((size * dpr) - target_w) / 2.0
                y = ((size * dpr) - target_h) / 2.0
                from PyQt6.QtCore import QRectF
                renderer.render(p, QRectF(x, y, target_w, target_h))
        finally:
            p.end()
        try:
            pm.setDevicePixelRatio(dpr)
        except Exception:
            pass
        icon = QIcon()
        icon.addPixmap(pm)
        return icon
    except Exception:
        try:
            return QIcon(path)
        except Exception:
            return QIcon() 