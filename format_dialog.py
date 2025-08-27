from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHBoxLayout, QPushButton, QComboBox, QLineEdit, QCheckBox, QTabWidget, QWidget, QGraphicsOpacityEffect, QProgressBar
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QThread, pyqtSignal
from yt_dlp import YoutubeDL
from settings import AppSettings


class FormatChooserDialog(QDialog):
	"""Simple pre-download format chooser dialog."""
	def __init__(self, url: str, parent=None):
		super().__init__(parent)
		self.url = url
		self.settings = AppSettings()
		self.setWindowTitle("Choose Format")
		self.resize(720, 560)
		try:
			self.setMinimumSize(640, 520)
		except Exception:
			pass
		self.setStyleSheet("""
			QDialog { background: #ffffff; }
			QLabel { color: #1e293b; }
			QTableWidget { background: #ffffff; color: #1e293b; gridline-color: #e2e8f0; }
			QHeaderView::section { background: #f1f5f9; color: #111827; padding: 6px; border: 1px solid #e2e8f0; }
			QComboBox { background: #ffffff; color: #111827; border: 1px solid #e2e8f0; padding: 6px 8px; border-radius: 6px; }
			QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1, stop:1 #4338ca); color: #ffffff; border: none; padding: 8px 14px; border-radius: 8px; font-weight: 600; }
			QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #818cf8, stop:1 #6366f1); }
			QTabWidget::pane { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }
			QTabBar::tab { background: #f8fafc; color: #1e293b; border: 1px solid #e2e8f0; padding: 8px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; }
			QTabBar::tab:selected { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #e0e7ff, stop:1 #c7d2fe); color: #111827; border: #c7d2fe; }
			QTabBar::tab:hover { background: #eef2ff; }
		""")
		self.selected_resolution = None
		self.selected_container = None
		self.proceed_with_defaults = False
		self._formats = []
		self.selected_audio_format = None
		self._tab_anim = None
		self._audio_row_index = None
		self.available_rows = []  # (label, resolution_key, container, size_text)
		self._loader = None
		self._cookie_file_for_ydl = self._resolve_cookiefile()
		# Loading indicator state
		self._loading_row = None
		self._loading_label = None
		self._loading_bar = None
		self._countdown_label = None
		self._countdown_timer = None
		self._countdown_secs = 0
		# No auto-close timer: dialog stays until user chooses
		self._build_ui()
		self._load_formats_async()

	def showEvent(self, event):
		"""Ensure proper initialization when dialog is shown"""
		super().showEvent(event)
		# Ensure the first row is selected and selection change event fires
		if self.table.rowCount() > 0:
			self.table.selectRow(0)
			# Force the selection change event to fire
			self._on_simple_selection_changed()

	class _FormatLoader(QThread):
		result_ready = pyqtSignal(list)
		failed = pyqtSignal(str)

		def __init__(self, url: str, cookiefile: str | None = None):
			super().__init__()
			self._url = url or ""
			self._cookiefile = cookiefile

		def run(self):
			try:
				if not self._url:
					self.result_ready.emit([])
					return
				opts = {
					'quiet': True,
					'no_warnings': True,
					'skip_download': True,
					'extract_flat': False,
					'socket_timeout': 30,
				}
				# Apply cookies if provided
				try:
					if self._cookiefile:
						opts['cookiefile'] = self._cookiefile
				except Exception:
					pass
				with YoutubeDL(opts) as ydl:
					info = ydl.extract_info(self._url, download=False)
				formats = (info.get('formats') or []) if isinstance(info, dict) else []
				self.result_ready.emit(formats)
			except Exception as e:
				self.failed.emit(str(e))

	def _build_ui(self):
		layout = QVBoxLayout(self)
		info = QLabel("Select a resolution and container. Estimates are approximate.")
		info.setStyleSheet("color: #64748b; font-weight: 600;")
		layout.addWidget(info)

		# Loading indicator (hidden by default)
		loading_row = QHBoxLayout()
		self._loading_label = QLabel("Loading formats…")
		self._loading_label.setStyleSheet("color: #64748b;")
		self._loading_bar = QProgressBar()
		try:
			self._loading_bar.setRange(0, 0)  # Indeterminate
			self._loading_bar.setTextVisible(False)
		except Exception:
			pass
		self._countdown_label = QLabel("")
		self._countdown_label.setStyleSheet("color: #94a3b8;")
		loading_row.addWidget(self._loading_label)
		loading_row.addWidget(self._loading_bar)
		loading_row.addWidget(self._countdown_label)
		loading_row.addStretch()
		container_loading = QWidget()
		container_loading.setLayout(loading_row)
		layout.addWidget(container_loading)
		container_loading.hide()
		self._loading_row = container_loading

		# Tabs for Simple and Advanced
		self.tabs = QTabWidget()
		layout.addWidget(self.tabs)

		# Simple tab
		self.simple_tab = QWidget()
		simple_layout = QVBoxLayout(self.simple_tab)
		simple_layout.setContentsMargins(0, 0, 0, 0)
		simple_layout.setSpacing(8)

		container_row = QHBoxLayout()
		container_label = QLabel("Container:")
		self.container_combo = QComboBox()
		self.container_combo.addItems(["mp4", "webm"])  # common safe options
		self.container_combo.setCurrentText(self.settings.get_preferred_video_format())
		self.container_combo.currentTextChanged.connect(self._on_container_combo_changed)
		self.container_combo.setMinimumWidth(140)
		container_row.addWidget(container_label)
		container_row.addWidget(self.container_combo)
		container_row.addStretch()
		simple_layout.addLayout(container_row)

		audio_row = QHBoxLayout()
		audio_label = QLabel("Audio:")
		self.audio_combo = QComboBox()
		self.audio_combo.addItems(["m4a", "mp3", "opus"])  # common audio choices
		try:
			self.audio_combo.setCurrentText(self.settings.get_preferred_audio_format())
		except Exception:
			self.audio_combo.setCurrentText("m4a")
		self.audio_combo.setMinimumWidth(140)
		audio_row.addWidget(audio_label)
		audio_row.addWidget(self.audio_combo)
		audio_row.addStretch()
		simple_layout.addLayout(audio_row)

		self.table = QTableWidget(0, 3)
		self.table.setHorizontalHeaderLabels(["Option", "Container", "Est. Size"])
		self.table.horizontalHeader().setStretchLastSection(True)
		try:
			self.table.setColumnWidth(0, 360)
			self.table.setColumnWidth(1, 140)
			self.table.setColumnWidth(2, 140)
			self.table.verticalHeader().setDefaultSectionSize(36)
		except Exception:
			pass
		self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
		self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
		self.table.setAlternatingRowColors(True)
		self.table.itemSelectionChanged.connect(self._on_simple_selection_changed)
		simple_layout.addWidget(self.table)

		# Keep audio row in sync with audio dropdown
		self.audio_combo.currentTextChanged.connect(self._on_audio_combo_changed)

		self.tabs.addTab(self.simple_tab, "Simple")

		# Advanced tab
		self.advanced_tab = QWidget()
		advanced_layout = QVBoxLayout(self.advanced_tab)
		advanced_layout.setContentsMargins(0, 0, 0, 0)
		advanced_layout.setSpacing(8)

		adv_filter_row = QHBoxLayout()
		self.adv_filter = QLineEdit()
		self.adv_filter.setPlaceholderText("Filter (e.g., 1080p, av1, 60fps, webm)")
		self.adv_filter.textChanged.connect(self._refresh_advanced_table)
		self.adv_filter.setMinimumHeight(30)
		adv_filter_row.addWidget(QLabel("Search:"))
		adv_filter_row.addWidget(self.adv_filter)
		advanced_layout.addLayout(adv_filter_row)

		self.adv_table = QTableWidget(0, 6)
		self.adv_table.setHorizontalHeaderLabels(["Res", "FPS", "Ext", "Codec", "Size", "Tags"])
		self.adv_table.horizontalHeader().setStretchLastSection(True)
		try:
			self.adv_table.setColumnWidth(0, 120)  # Res
			self.adv_table.setColumnWidth(1, 60)   # FPS
			self.adv_table.setColumnWidth(2, 70)   # Ext
			self.adv_table.setColumnWidth(3, 220)  # Codec
			self.adv_table.setColumnWidth(4, 100)  # Size
			self.adv_table.verticalHeader().setDefaultSectionSize(34)
		except Exception:
			pass
		self.adv_table.setSelectionBehavior(self.adv_table.SelectionBehavior.SelectRows)
		self.adv_table.setSelectionMode(self.adv_table.SelectionMode.SingleSelection)
		self.adv_table.setAlternatingRowColors(True)
		self.adv_table.itemSelectionChanged.connect(self._on_advanced_selection_changed)
		advanced_layout.addWidget(self.adv_table)

		self.tabs.addTab(self.advanced_tab, "Advanced")
		self.tabs.currentChanged.connect(self._on_tab_changed)

		# Buttons
		btn_row = QHBoxLayout()
		btn_row.addStretch()
		self.back_btn = QPushButton("Back")
		self.use_defaults_btn = QPushButton("Use Defaults")
		self.ok_btn = QPushButton("Download")
		self.back_btn.clicked.connect(self.reject)
		self.use_defaults_btn.clicked.connect(self._use_defaults)
		self.ok_btn.clicked.connect(self._accept)
		btn_row.addWidget(self.back_btn)
		btn_row.addWidget(self.use_defaults_btn)
		btn_row.addWidget(self.ok_btn)
		layout.addLayout(btn_row)

	def _load_formats_async(self):
		# Show defaults immediately to keep UI responsive
		self._populate_rows_from_formats([])
		# Start background loader
		try:
			# Show loading indicator with countdown (30s)
			if self._loading_row:
				self._loading_row.show()
				self._countdown_secs = 30
				try:
					self._countdown_label.setText(f"(~{self._countdown_secs}s)")
				except Exception:
					pass
				# Kick off a 1s timer to update countdown
				if not self._countdown_timer:
					self._countdown_timer = QTimer(self)
					self._countdown_timer.timeout.connect(self._tick_countdown)
				self._countdown_timer.start(1000)

			self._loader = self._FormatLoader(self.url, cookiefile=self._cookie_file_for_ydl)
			self._loader.result_ready.connect(self._on_formats_loaded)
			self._loader.failed.connect(self._on_formats_failed)
			self._loader.start()
		except Exception:
			pass

		# Safety timeout to hide indicator even if yt-dlp stalls beyond socket timeout
		try:
			QTimer.singleShot(31000, self._stop_loading_indicator)
		except Exception:
			pass

	def _on_formats_loaded(self, formats: list):
		self._formats = formats or []
		self._stop_loading_indicator()
		# Rebuild table: clear then populate based on formats
		try:
			self.table.setRowCount(0)
		except Exception:
			pass
		self._populate_rows_from_formats(self._formats)

	def _on_formats_failed(self, err: str):
		# Hide loading UI and keep defaults shown
		self._stop_loading_indicator()
		try:
			self._formats = []
		except Exception:
			pass

	def _stop_loading_indicator(self):
		try:
			if self._countdown_timer and self._countdown_timer.isActive():
				self._countdown_timer.stop()
		except Exception:
			pass
		try:
			if self._countdown_label:
				self._countdown_label.setText("")
		except Exception:
			pass
		try:
			if self._loading_row:
				self._loading_row.hide()
		except Exception:
			pass

	def _tick_countdown(self):
		try:
			self._countdown_secs = max(0, int(self._countdown_secs) - 1)
			if self._countdown_label:
				self._countdown_label.setText(f"(~{self._countdown_secs}s)")
			if self._countdown_secs <= 0:
				self._stop_loading_indicator()
		except Exception:
			self._stop_loading_indicator()

	def _populate_rows_from_formats(self, formats: list):
		# Build default list first; then enhance with formats when present
		self.available_rows = []
		default_res_list = ["1080p", "720p", "480p", "360p", "Audio"]
		heights = {}
		best_audio = None
		try:
			for f in formats:
				size = f.get('filesize') or f.get('filesize_approx') or 0
				size_text = self._format_size(size) if size else "~"
				ext = (f.get('ext') or '').lower()
				height = f.get('height') or 0
				vcodec = f.get('vcodec')
				acodec = f.get('acodec')
				if vcodec and vcodec != 'none' and height:
					key = f"{int(height)}p"
					if key not in heights:
						heights[key] = {}
					heights[key][ext] = size_text
				elif (not vcodec or vcodec == 'none') and acodec and acodec != 'none':
					if not best_audio:
						best_audio = (ext or 'm4a', size_text)
		except Exception:
			pass
		# Add rows for found heights (descending)
		try:
			for res in sorted(heights.keys(), key=lambda r: int(r[:-1]), reverse=True):
				cont = self.container_combo.currentText()
				size_text = heights[res].get(cont, next(iter(heights[res].values()), "~"))
				self._add_row(f"Video {res}", res, cont, size_text)
		except Exception:
			pass
		# Ensure default entries exist
		for res in default_res_list:
			if res != 'Audio' and not any(r[1] == res for r in getattr(self, 'available_rows', [])):
				self._add_row(f"Video {res}", res, self.container_combo.currentText(), "~")
		if best_audio:
			self._add_row("Audio (best)", "Audio", self.audio_combo.currentText().lower(), best_audio[1])
		else:
			self._add_row("Audio (best)", "Audio", self.audio_combo.currentText().lower(), "~")
		
		# Ensure proper selection and update the UI
		if self.table.rowCount() > 0:
			self.table.selectRow(0)
			# Force the selection change event to fire
			self._on_simple_selection_changed()

	def _extract_formats(self):
		# Deprecated: kept for compatibility; not used directly after async change
		try:
			opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'extract_flat': False, 'socket_timeout': 30}
			if getattr(self, '_cookie_file_for_ydl', None):
				opts['cookiefile'] = self._cookie_file_for_ydl
			with YoutubeDL(opts) as ydl:
				info = ydl.extract_info(self.url, download=False)
				return info.get('formats') or []
		except Exception:
			return []

	def _resolve_cookiefile(self) -> str | None:
		"""Attempt to get a usable Netscape-format cookie file for yt-dlp.
		Order: parent's current_cookie_file -> settings cookie txt -> convert JSON paths/strings via cookie_manager.
		"""
		try:
			parent = self.parent()
			# 1) Controller-provided active cookie file
			try:
				if parent and hasattr(parent, 'current_cookie_file'):
					cf = getattr(parent, 'current_cookie_file')
					if cf:
						import os
						return cf if os.path.exists(cf) else None
			except Exception:
				pass
			# 2) Settings manual cookie txt path
			try:
				cf = self.settings.get_cookie_file_path()
				if cf:
					import os
					if os.path.exists(cf) and cf.lower().endswith('.txt'):
						return cf
			except Exception:
				pass
			# 3) JSON cookie file path -> convert
			try:
				jpath = self.settings.get_json_cookie_file_path()
				if jpath:
					from cookie_manager import CookieManager
					cm = CookieManager()
					temp_txt = cm.convert_json_to_yt_dlp_format(jpath)
					import os
					return temp_txt if (temp_txt and os.path.exists(temp_txt)) else None
			except Exception:
				pass
			# 4) Pasted JSON string in settings -> convert
			try:
				pdata = getattr(self.settings, 'get_pasted_json_data', None)
				if callable(pdata):
					json_str = pdata() or ""
					if json_str.strip().startswith('{') or json_str.strip().startswith('['):
						from cookie_manager import CookieManager
						cm = CookieManager()
						temp_txt = cm.convert_json_string_to_yt_dlp_format(json_str)
						import os
						return temp_txt if (temp_txt and os.path.exists(temp_txt)) else None
			except Exception:
				pass
		except Exception:
			pass
		return None

	def _add_row(self, label: str, res_key: str, container: str, size_text: str):
		row = self.table.rowCount()
		self.table.insertRow(row)
		self.table.setItem(row, 0, QTableWidgetItem(label))
		self.table.setItem(row, 1, QTableWidgetItem(container))
		self.table.setItem(row, 2, QTableWidgetItem(size_text))
		self.available_rows.append((label, res_key, container, size_text))
		if res_key == 'Audio':
			self._audio_row_index = row

	def _accept(self):
		try:
			if hasattr(self, '_safety_timer') and self._safety_timer.isActive():
				self._safety_timer.stop()
		except Exception:
			pass
		# If a loader is running, let it finish in background; we proceed now
		# If Advanced tab is active, use advanced selection first
		if getattr(self, 'tabs', None) and self.tabs.currentIndex() == 1:
			arow = self.adv_table.currentRow()
			if arow >= 0 and self.adv_table.rowCount() > 0:
				# Use advanced selection to set resolution/container
				res = self.adv_table.item(arow, 0).text() if self.adv_table.item(arow, 0) else ""
				fps = self.adv_table.item(arow, 1).text() if self.adv_table.item(arow, 1) else ""
				ext = self.adv_table.item(arow, 2).text() if self.adv_table.item(arow, 2) else ""
				# Map res to resolution key or Audio
				if not res or res.lower() in ("audio", "none"):
					self.selected_resolution = "Audio"
					# For audio, prefer ext from the row, else audio combo
					self.selected_audio_format = (ext or self.audio_combo.currentText()).lower()
				else:
					# Expect formats like 1920x1080; map to 1080p
					if "x" in res:
						try:
							self.selected_resolution = f"{int(res.split('x')[1])}p"
						except Exception:
							self.selected_resolution = None
					else:
						self.selected_resolution = res
				self.selected_container = (ext or self.container_combo.currentText()).lower()
				self.accept()
				return
			# If no advanced selection, fall through to simple handling

		# Simple tab handling - improved selection logic
		row = self.table.currentRow()
		
		# If no explicit row selection, try to use the first available row
		if row < 0 and self.table.rowCount() > 0:
			row = 0
			# Ensure the first row is visually selected
			self.table.selectRow(0)
		
		# If still no valid row, fall back to defaults
		if row < 0 or row >= len(self.available_rows):
			self._use_defaults()
			return
			
		# Get the resolution from the selected row
		label, res_key, container, _ = self.available_rows[row]
		self.selected_resolution = res_key
		
		# Log the selection for debugging
		print(f"Format chooser: Selected resolution '{self.selected_resolution}' from row {row}")
		print(f"Format chooser: Row data - label='{label}', res_key='{res_key}', container='{container}'")
		
		if self.selected_resolution == "Audio":
			self.selected_audio_format = (self.audio_combo.currentText() or "m4a").lower()
			self.selected_container = None
		else:
			self.selected_container = self.container_combo.currentText() or container
			
		# Log final selection before accept
		print(f"Format chooser: Final selection - resolution='{self.selected_resolution}', container='{self.selected_container}', audio='{self.selected_audio_format}'")
		
		# Persist container choice
		try:
			if self.selected_resolution != 'Audio':
				self.settings.set_preferred_video_format(self.selected_container)
			else:
				# keep audio format preference as is
				pass
		except Exception:
			pass
		self.accept()

	def _use_defaults(self):
		self.proceed_with_defaults = True
		try:
			if hasattr(self, '_safety_timer') and self._safety_timer.isActive():
				self._safety_timer.stop()
		except Exception:
			pass
		
		# Try to get the current resolution from the parent UI if available
		try:
			if hasattr(self.parent(), 'resolution_box'):
				current_res = self.parent().resolution_box.currentText()
				if current_res in ["360p", "480p", "720p", "1080p", "Audio"]:
					self.selected_resolution = current_res
					print(f"Format chooser: Using fallback resolution '{self.selected_resolution}' from UI")
					self.selected_container = self.container_combo.currentText()
					self.accept()
					return
		except Exception:
			pass
		
		# If no fallback available, try to use the first available resolution from the table
		try:
			if self.table.rowCount() > 0 and len(self.available_rows) > 0:
				first_res = self.available_rows[0][1]  # Get resolution from first row
				if first_res in ["360p", "480p", "720p", "1080p", "Audio"]:
					self.selected_resolution = first_res
					print(f"Format chooser: Using first available resolution '{self.selected_resolution}' as fallback")
					self.selected_container = self.container_combo.currentText()
					self.accept()
					return
		except Exception:
			pass
		
		# Last resort: use a default resolution
		self.selected_resolution = "720p"  # Default fallback
		print(f"Format chooser: Using hardcoded fallback resolution '{self.selected_resolution}'")
		self.selected_container = self.container_combo.currentText()
		self.accept()

	def _on_tab_changed(self, idx: int):
		# Resize and refresh when switching to Advanced
		if idx == 1:
			self.resize(780, 600)
			# Ensure formats are loaded for Advanced view without blocking
			try:
				if not self._formats and not getattr(self, '_loader', None):
					self._load_formats_async()
			except Exception:
				pass
			self._refresh_advanced_table()
		else:
			self.resize(720, 560)
		# Smooth fade-in for current tab widget
		try:
			w = self.tabs.currentWidget()
			effect = QGraphicsOpacityEffect(w)
			w.setGraphicsEffect(effect)
			anim = QPropertyAnimation(effect, b"opacity")
			anim.setDuration(180)
			anim.setStartValue(0.0)
			anim.setEndValue(1.0)
			anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
			self._tab_anim = anim
			anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
		except Exception:
			pass

	def _refresh_advanced_table(self):
		# Only refresh when Advanced tab is active
		if getattr(self, 'tabs', None) and self.tabs.currentIndex() != 1:
			return
		self.adv_table.setRowCount(0)
		q = (self.adv_filter.text() or "").lower()
		formats = self._formats or []
		if not formats:
			# Placeholder row
			self.adv_table.setRowCount(1)
			self.adv_table.setItem(0, 0, QTableWidgetItem(""))
			self.adv_table.setItem(0, 1, QTableWidgetItem(""))
			self.adv_table.setItem(0, 2, QTableWidgetItem(""))
			self.adv_table.setItem(0, 3, QTableWidgetItem(""))
			self.adv_table.setItem(0, 4, QTableWidgetItem("~"))
			self.adv_table.setItem(0, 5, QTableWidgetItem("No formats yet"))
			return
		for f in formats:
			ext = (f.get('ext') or '').lower()
			vcodec = (f.get('vcodec') or '').lower()
			acodec = (f.get('acodec') or '').lower()
			fps = str(f.get('fps') or '')
			height = f.get('height') or 0
			width = f.get('width') or 0
			res = f"{width}x{height}" if height and width else ("audio" if (not vcodec or vcodec=='none') and acodec else "")
			note = (f.get('format_note') or '').lower()
			size_val = f.get('filesize') or f.get('filesize_approx') or 0
			size_text = self._format_size(size_val) if size_val else "~"
			# Build concise tags
			tags = []
			if 'av1' in vcodec:
				tags.append('AV1')
			elif 'vp9' in vcodec:
				tags.append('VP9')
			elif '264' in vcodec or 'avc' in vcodec:
				tags.append('H.264')
			if 'hdr' in note:
				tags.append('HDR')
			if fps and fps.isdigit() and int(fps) >= 60:
				tags.append('60fps')
			codec_combo = (vcodec or '')
			if acodec and acodec != 'none':
				codec_combo = f"{codec_combo}+{acodec}"
			row_text = " ".join([ext, res, fps, vcodec, acodec, size_text, note] + tags).lower()
			if q and q not in row_text:
				continue
			row = self.adv_table.rowCount()
			self.adv_table.insertRow(row)
			self.adv_table.setItem(row, 0, QTableWidgetItem(res))
			self.adv_table.setItem(row, 1, QTableWidgetItem(fps))
			self.adv_table.setItem(row, 2, QTableWidgetItem(ext))
			self.adv_table.setItem(row, 3, QTableWidgetItem(codec_combo))
			self.adv_table.setItem(row, 4, QTableWidgetItem(size_text))
			self.adv_table.setItem(row, 5, QTableWidgetItem(" ".join(tags)))

	def _on_simple_selection_changed(self):
		row = self.table.currentRow()
		if row < 0:
			return
		# Column 1 is container in simple table
		container_item = self.table.item(row, 1)
		if container_item and container_item.text():
			self.container_combo.setCurrentText(container_item.text())
		# If the row label indicates Audio, disable container combo
		label_item = self.table.item(row, 0)
		label_text = label_item.text().lower() if label_item and label_item.text() else ""
		if "audio" in label_text:
			self.container_combo.setEnabled(False)
			# Ensure the audio row shows the audio format, not the video container
			if self._audio_row_index is not None and self._audio_row_index == row:
				ai = self.table.item(row, 1)
				if ai:
					ai.setText(self.audio_combo.currentText().lower())
		else:
			self.container_combo.setEnabled(True)

	def _on_advanced_selection_changed(self):
		if not self.adv_table.isVisible():
			return
		row = self.adv_table.currentRow()
		if row < 0:
			return
		# Columns: 0 Res, 1 FPS, 2 Ext, 3 Codec, 4 Size, 5 Tags
		ext_item = self.adv_table.item(row, 2)
		res_item = self.adv_table.item(row, 0)
		res_text = res_item.text().lower() if res_item and res_item.text() else ""
		ext_text = ext_item.text().lower() if (ext_item and ext_item.text()) else ""
		# Update container/audio combo based on selection
		if not res_text or res_text in ("audio", "none"):
			# Audio-only
			if ext_text in ("m4a", "mp3", "opus"):
				self.audio_combo.setCurrentText(ext_text)
			self.container_combo.setEnabled(False)
		else:
			if ext_text in ("mp4", "webm"):
				self.container_combo.setCurrentText(ext_text)
			self.container_combo.setEnabled(True)

	def _on_container_combo_changed(self, text: str):
		# Update the simple table's container column to reflect the dropdown
		container = (text or '').lower()
		for row in range(self.table.rowCount()):
			# Skip audio row to avoid overwriting its format
			if self._audio_row_index is not None and row == self._audio_row_index:
				continue
			item = self.table.item(row, 1)
			if item:
				item.setText(container)

	def _on_audio_combo_changed(self, text: str):
		# Keep audio row's column in sync with chosen audio format
		if self._audio_row_index is None:
			return
		item = self.table.item(self._audio_row_index, 1)
		if item:
			item.setText((text or '').lower())
		# Update available_rows entry for audio row
		try:
			idx = self._audio_row_index
			label, res_key, _, size_text = self.available_rows[idx]
			self.available_rows[idx] = (label, res_key, (text or '').lower(), size_text)
		except Exception:
			pass

	def get_selection(self):
		# Debug logging to see what's being returned
		print(f"Format chooser get_selection: resolution='{self.selected_resolution}', container='{self.selected_container}', audio='{self.selected_audio_format}'")
		return self.selected_resolution, self.selected_container, self.selected_audio_format

	@staticmethod
	def _format_size(size):
		units = ['B', 'KB', 'MB', 'GB']
		val = float(size)
		for u in units:
			if val < 1024.0 or u == units[-1]:
				if u == 'B':
					return f"{int(val)} {u}"
				return f"{val:.1f} {u}"
			val /= 1024.0
		return f"{val:.1f} TB" 