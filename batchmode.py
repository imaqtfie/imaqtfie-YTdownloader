import os
import re
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from yt_dlp import YoutubeDL
from settings import AppSettings
from urllib.parse import urlparse, parse_qs


class PlaylistInfoExtractor(QThread):
    """Extract basic playlist information quickly."""
    playlist_info_extracted = pyqtSignal(dict)  # playlist info
    extraction_failed = pyqtSignal(str)  # error message

    def __init__(self, url, max_items: int | None = None):
        super().__init__()
        self.url = url
        self.max_items = max_items if isinstance(max_items, int) and max_items > 0 else None

    def run(self):
        try:
            # Extract first N entries efficiently
            ydl_opts_full = {
                'extract_flat': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 20,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'android']
                    }
                }
            }
            if self.max_items is not None:
                # Set playlist range
                ydl_opts_full['playliststart'] = 1
                ydl_opts_full['playlistend'] = int(self.max_items)

            with YoutubeDL(ydl_opts_full) as ydl_full:
                full_info = ydl_full.extract_info(self.url, download=False)

            if 'entries' not in full_info:
                self.extraction_failed.emit("This is a single video, not a playlist")
                return

            # Build entry URLs list
            entry_urls = []
            try:
                for e in full_info.get('entries', []) or []:
                    if isinstance(e, dict):
                        if e.get('url'):
                            entry_urls.append(e['url'])
                        elif e.get('id'):
                            entry_urls.append(f"https://www.youtube.com/watch?v={e['id']}")
                    elif isinstance(e, str):
                        entry_urls.append(e)
            except Exception:
                entry_urls = []

            # Get total count
            total_count = None
            try:
                total_count = (
                    full_info.get('playlist_count')
                    or full_info.get('n_entries')
                    or full_info.get('requested_entries')
                )
            except Exception:
                total_count = None

            # Check if YouTube Mix
            try:
                parsed = urlparse(self.url)
                qs = parse_qs(parsed.query)
                list_id_from_url = ""
                if qs.get('list'):
                    list_id_from_url = qs.get('list')[0] if qs.get('list') else ""
                is_mix = isinstance(list_id_from_url, str) and list_id_from_url.upper().startswith('RD')
            except Exception:
                list_id_from_url = ""
                is_mix = False

            playlist_data = {
                'title': full_info.get('title', 'Unknown Playlist'),
                'uploader': full_info.get('uploader', 'Unknown Channel'),
                'video_count': int(total_count) if isinstance(total_count, int) and total_count > 0 else len(entry_urls),
                'url': self.url,
                'id': full_info.get('id', ''),
                'entries': entry_urls,
                'list_id': list_id_from_url,
                'is_mix': is_mix,
            }

            self.playlist_info_extracted.emit(playlist_data)

        except Exception as e:
            self.extraction_failed.emit(f"Failed to extract playlist info: {str(e)}")


class BatchModeManager(QObject):
    """Enhanced batch mode manager with sequential playlist processing."""
    batch_status_changed = pyqtSignal(bool)  # batch mode enabled
    batch_progress_updated = pyqtSignal(int, int)  # current, total
    batch_completed = pyqtSignal(int, int)  # successful, total
    playlist_detected = pyqtSignal(dict)  # playlist info
    playlist_loading = pyqtSignal(str)  # status message
    queue_updated = pyqtSignal()  # queue changed
    queue_limit_reached = pyqtSignal(int)  # limit reached
    queue_limit_warning = pyqtSignal(int, int)  # approaching limit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_batch_mode = False
        self.batch_queue = []
        self.current_batch_index = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.batch_settings = {
            'resolution': '720p',
            'download_subs': False,
            'download_path': '',
            'container_override': None,
            'audio_override': None,
        }

        # Playlist support
        self.extractor = None
        self.current_playlist_info = None
        self.playlist_current_index = 0
        self.playlist_max_items = None

    def is_playlist_url(self, url):
        """Check if URL is a playlist, including YouTube Mix (list=RD...)."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path.lower()
            qs = parse_qs(parsed.query)
            list_id = None
            if qs.get('list'):
                list_id = qs.get('list')[0] if qs.get('list') else None
            if 'youtube.com' in host and '/playlist' in path and list_id:
                return True
            if 'youtube.com' in host and '/watch' in path and list_id:
                # Treat playlists and Mix as playlists
                return True
            return False
        except Exception:
            return False

    def handle_playlist_url(self, url, queue_limit=None):
        """Process playlist URL - get basic info only"""
        if not self.is_playlist_url(url):
            return False

        self.playlist_loading.emit("Getting playlist information...")

        # Start extraction in background
        # Compute effective cap
        eff_cap = None
        try:
            if isinstance(queue_limit, int) and queue_limit > 0:
                eff_cap = queue_limit
            if isinstance(self.playlist_max_items, int) and self.playlist_max_items > 0:
                eff_cap = min(eff_cap, self.playlist_max_items) if eff_cap else self.playlist_max_items
        except Exception:
            pass
        self.extractor = PlaylistInfoExtractor(url, eff_cap)
        self.extractor.playlist_info_extracted.connect(lambda info: self.on_playlist_info_extracted(info, queue_limit))
        self.extractor.extraction_failed.connect(self.on_playlist_extraction_failed)
        self.extractor.start()

        return True

    def on_playlist_info_extracted(self, playlist_info, queue_limit):
        """Handle successful playlist info extraction"""
        self.current_playlist_info = playlist_info
        self.playlist_current_index = 0
        self.playlist_detected.emit(playlist_info)

        # Auto-enable batch mode if not enabled
        if not self.is_batch_mode:
            self.enable_batch_mode()

        # Generate videos on-demand
        self.batch_queue = []

        # Add placeholder entries
        try:
            total = int(playlist_info.get('video_count', 0))
        except Exception:
            total = len(playlist_info.get('entries', [])) if isinstance(playlist_info.get('entries'), list) else 0
        # Apply limits
        max_items = total
        if isinstance(queue_limit, int) and queue_limit > 0:
            max_items = min(max_items, queue_limit)
        if isinstance(self.playlist_max_items, int) and self.playlist_max_items > 0:
            max_items = min(max_items, self.playlist_max_items)
        for i in range(max_items):
            # Store index instead of URL - we'll generate URLs on demand
            self.batch_queue.append(f"PLAYLIST_ITEM_{i + 1}")

        title = playlist_info['title']
        count = max_items
        self.playlist_loading.emit(f"Playlist '{title}' ready: {count} videos queued for download")
        self.queue_updated.emit()

        # Check queue limit if provided
        if queue_limit is not None and len(self.batch_queue) >= queue_limit:
            self.queue_limit_reached.emit(len(self.batch_queue))

    def on_playlist_extraction_failed(self, error_msg):
        """Handle playlist extraction failure"""
        self.playlist_loading.emit(f"Playlist extraction failed: {error_msg}")

    def get_playlist_video_url(self, index):
        """Generate URL for specific playlist video index"""
        if not self.current_playlist_info:
            return None

        # Prefer exact entry URL if available
        try:
            entries = self.current_playlist_info.get('entries') or []
            if 0 <= index < len(entries):
                entry_url = entries[index]
            else:
                entry_url = None
        except Exception:
            entry_url = None

        # Prefer the explicit list_id captured from URL; fall back to extractor id
        list_id = (
            self.current_playlist_info.get('list_id')
            or self.current_playlist_info.get('id')
            or ''
        )
        if entry_url:
            # Append list context if available
            sep = '&' if '?' in entry_url else '?'
            if list_id:
                return f"{entry_url}{sep}list={list_id}&index={index + 1}"
            return entry_url

        # Fallback to playlist URL with index hint
        playlist_url = self.current_playlist_info.get('url', '')
        if playlist_url:
            sep = '&' if '?' in playlist_url else '?'
            if list_id:
                return f"{playlist_url}{sep}list={list_id}&index={index + 1}"
            return f"{playlist_url}{sep}index={index + 1}"
        return None

    def enable_batch_mode(self, resolution='720p', download_subs=False, download_path='', container_override=None, audio_override=None):
        """Enable batch mode with specified settings"""
        print(f"Batch mode: Enabling with resolution='{resolution}', subs={download_subs}, path='{download_path}'")
        
        self.is_batch_mode = True
        self.batch_settings = {
            'resolution': resolution,
            'download_subs': download_subs,
            'download_path': download_path,
            'container_override': (container_override or None),
            'audio_override': (audio_override or None),
        }
        self.batch_queue = []
        self.current_batch_index = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.batch_status_changed.emit(True)
        
        print(f"Batch mode: Enabled with settings {self.batch_settings}")

    def update_batch_settings(self, resolution=None, download_subs=None, download_path=None, container_override=None, audio_override=None):
        """Update batch mode settings"""
        if not self.is_batch_mode:
            return
            
        # Log the update for debugging
        print(f"Batch mode: Updating settings - resolution: {resolution}, subs: {download_subs}, path: {download_path}")
        
        if resolution is not None:
            old_res = self.batch_settings.get('resolution', 'Unknown')
            self.batch_settings['resolution'] = resolution
            print(f"Batch mode: Resolution updated from '{old_res}' to '{resolution}'")
        if download_subs is not None:
            self.batch_settings['download_subs'] = download_subs
        if download_path is not None:
            self.batch_settings['download_path'] = download_path
        if container_override is not None:
            self.batch_settings['container_override'] = container_override
        if audio_override is not None:
            self.batch_settings['audio_override'] = audio_override

    def disable_batch_mode(self):
        """Disable batch mode and clear queue"""
        self.is_batch_mode = False
        self.batch_queue = []
        self.current_batch_index = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.current_playlist_info = None
        self.playlist_current_index = 0
        self.batch_status_changed.emit(False)

    def add_to_batch(self, url, queue_limit=None):
        """Add a URL to the batch queue with optional limit checking"""
        if not url or not url.strip():
            return False

        url = url.strip()

        # Check queue limit if provided
        if queue_limit is not None and len(self.batch_queue) >= queue_limit:
            self.queue_limit_reached.emit(len(self.batch_queue))
            return False

        # Check if it's a playlist URL
        if self.is_playlist_url(url):
            return self.handle_playlist_url(url, queue_limit)

        # Check if URL is already in queue
        if url in self.batch_queue:
            return False

        self.batch_queue.append(url)
        self.queue_updated.emit()
        
        # Emit warning if approaching limit (at 80% of limit)
        if queue_limit is not None and len(self.batch_queue) >= int(queue_limit * 0.8):
            self.queue_limit_warning.emit(len(self.batch_queue), queue_limit)
            
        return True

    def _sanitize_folder_name(self, name: str) -> str:
        try:
            # Replace invalid path characters with underscore; trim length
            name = re.sub(r'[\\/:*?"<>|]+', '_', name or 'Playlist')
            name = name.strip().strip('.')
            return name[:100] if len(name) > 100 else name
        except Exception:
            return 'Playlist'

    def _resolve_playlist_download_path(self, base_download_path: str) -> str:
        """Return subfolder path for playlist items if setting is enabled."""
        try:
            settings = AppSettings()
            enabled = getattr(settings, 'get_save_playlists_to_subfolder', lambda: True)()
            if not enabled:
                return base_download_path
            title = None
            is_mix = False
            try:
                if self.current_playlist_info:
                    title = self.current_playlist_info.get('title')
                    is_mix = bool(self.current_playlist_info.get('is_mix', False))
            except Exception:
                title = None
                is_mix = False
            safe_title = self._sanitize_folder_name(title or 'Playlist')
            root_folder = 'Mixes' if is_mix else 'Playlists'
            return os.path.join(base_download_path, root_folder, safe_title)
        except Exception:
            return base_download_path

    def _build_batch_item_data(self, queue_item, is_playlist_item: bool, item_index: int):
        """Helper to build the data for the next batch item."""
        url = None
        resolution = self.batch_settings['resolution']
        download_subs = self.batch_settings['download_subs']
        download_path = self.batch_settings['download_path'] or ''
        container_override = self.batch_settings.get('container_override')
        audio_override = self.batch_settings.get('audio_override')

        if is_playlist_item:
            # Generate the actual URL for this playlist item
            actual_url = self.get_playlist_video_url(item_index)
            if not actual_url:
                # Skip this item if we can't generate URL
                return None
            url = actual_url
            self.playlist_current_index = item_index + 1
        else:
            # Regular URL
            url = queue_item

        # Decide download path (optionally route playlist items into a subfolder)
        if is_playlist_item and download_path:
            download_path = self._resolve_playlist_download_path(download_path)

        return {
            'url': url,
            'resolution': resolution,
            'download_subs': download_subs,
            'download_path': download_path,
            'container_override': container_override,
            'audio_override': audio_override,
        }

    def get_next_batch_item(self):
        """Get the next item in the batch queue"""
        if not self.is_batch_mode or self.current_batch_index >= len(self.batch_queue):
            return None

        queue_item = self.batch_queue[self.current_batch_index]
        self.current_batch_index += 1

        # Check if this is a playlist item
        is_playlist_item = False
        if isinstance(queue_item, str) and queue_item.startswith('PLAYLIST_ITEM_'):
            # Extract index from placeholder
            try:
                item_index = int(queue_item.split('_')[-1])
                is_playlist_item = True
            except (ValueError, IndexError):
                item_index = 0
        else:
            item_index = 0

        # Build the item data
        item_data = self._build_batch_item_data(queue_item, is_playlist_item, item_index)
        
        # Debug logging
        print(f"Batch mode: Next item - resolution='{item_data.get('resolution')}', subs={item_data.get('download_subs')}, path='{item_data.get('download_path')}'")
        
        return item_data

    def mark_download_completed(self, success=True):
        """Mark the current download as completed"""
        if success:
            self.successful_downloads += 1
        else:
            self.failed_downloads += 1

    def is_batch_complete(self):
        """Check if all batch items have been processed"""
        return self.current_batch_index >= len(self.batch_queue)

    def get_batch_status(self):
        """Get current batch status"""
        status = {
            'is_active': self.is_batch_mode,
            'queue_size': len(self.batch_queue),
            'current_index': self.current_batch_index,
            'successful': self.successful_downloads,
            'failed': self.failed_downloads,
            'remaining': len(self.batch_queue) - self.current_batch_index
        }

        # Add playlist info if available
        if self.current_playlist_info:
            status['playlist'] = {
                'title': self.current_playlist_info['title'],
                'total_videos': self.current_playlist_info['video_count'],
                'current_video': self.playlist_current_index
            }

        return status

    def get_batch_summary(self):
        """Get batch completion summary"""
        total = len(self.batch_queue)
        summary = {
            'total': total,
            'successful': self.successful_downloads,
            'failed': self.failed_downloads,
            'completion_rate': (self.successful_downloads / total * 100) if total > 0 else 0
        }

        # Add playlist info if available
        if self.current_playlist_info:
            summary['playlist'] = self.current_playlist_info['title']

        return summary

    def clear_batch_queue(self):
        """Clear the current batch queue"""
        self.batch_queue = []
        self.current_batch_index = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.current_playlist_info = None
        self.playlist_current_index = 0
        self.queue_updated.emit()

    def trim_queue_to_limit(self, limit: int):
        """Trim the batch queue to at most 'limit' items; adjust indices accordingly."""
        try:
            if limit is None or limit < 0:
                return
            # Persist this as a maximum for future extractions
            self.playlist_max_items = int(limit)
            if len(self.batch_queue) > limit:
                self.batch_queue = self.batch_queue[:limit]
                if self.current_batch_index > len(self.batch_queue):
                    self.current_batch_index = len(self.batch_queue)
                if self.playlist_current_index > len(self.batch_queue):
                    self.playlist_current_index = len(self.batch_queue)
                self.queue_updated.emit()
        except Exception:
            pass

    def enforce_playlist_limit(self, limit: int):
        """Set a persistent maximum items cap for the current playlist and apply it to the queue."""
        try:
            if isinstance(limit, int) and limit > 0:
                self.playlist_max_items = int(limit)
                self.trim_queue_to_limit(limit)
        except Exception:
            pass

    def remove_from_queue(self, index: int):
        """Remove an item from the queue by index and adjust indices."""
        if 0 <= index < len(self.batch_queue):
            del self.batch_queue[index]
            if index < self.current_batch_index:
                self.current_batch_index -= 1
            self.queue_updated.emit()

    def move_in_queue(self, from_index: int, to_index: int) -> bool:
        """Move an item within the queue to a new index."""
        if not (0 <= from_index < len(self.batch_queue)):
            return False
        if not (0 <= to_index < len(self.batch_queue)):
            return False
        if from_index == to_index:
            return True
        item = self.batch_queue.pop(from_index)
        self.batch_queue.insert(to_index, item)
        if self.current_batch_index == from_index:
            self.current_batch_index = to_index
        elif from_index < self.current_batch_index <= to_index:
            self.current_batch_index -= 1
        elif to_index <= self.current_batch_index < from_index:
            self.current_batch_index += 1
        self.queue_updated.emit()
        return True

    def get_queue_preview(self):
        """Get a simple preview of the current queue for UI display."""
        preview = []
        for i, queue_item in enumerate(self.batch_queue):
            item = {
                'index': i,
                'status': 'completed' if i < self.current_batch_index else 'pending'
            }
            if isinstance(queue_item, str) and queue_item.startswith('PLAYLIST_ITEM_'):
                try:
                    parts = queue_item.split('_')
                    item_index = int(parts[2]) if len(parts) >= 3 else (i + 1)
                except Exception:
                    item_index = i + 1
                item['title'] = f"Playlist Video #{item_index}"
                if self.current_playlist_info:
                    item['title'] = f"{self.current_playlist_info['title']} - Video #{item_index}"
                item['url'] = f"Playlist item {item_index}"
            else:
                item['url'] = queue_item
                item['title'] = f"Video: {queue_item}"
            preview.append(item)
        return preview

    def restart_batch(self):
        """Restart the batch processing counters."""
        self.current_batch_index = 0
        self.successful_downloads = 0
        self.failed_downloads = 0
        self.playlist_current_index = 0


class BatchModeUI:
    """
    UI helper class for batch mode functionality
    """

    @staticmethod
    def format_batch_status(status: dict) -> str:
        """Format batch status for display labels."""
        if not status.get('is_active'):
            return "Batch mode: Inactive"
        if status.get('queue_size', 0) == 0:
            return "Batch mode: No items in queue"
        if 'playlist' in status:
            playlist_title = status['playlist'].get('title', 'Playlist')
            current_video = status['playlist'].get('current_video', 0)
            total_videos = status['playlist'].get('total_videos', status.get('queue_size', 0))
            return f"Playlist: {current_video}/{total_videos} - {playlist_title}"
        return f"Batch: {status.get('current_index', 0)}/{status.get('queue_size', 0)} (✓{status.get('successful', 0)} ✗{status.get('failed', 0)})"

    @staticmethod
    def get_batch_progress_text(current: int, total: int) -> str:
        if total == 0:
            return "No items in batch"
        return f"Processing item {current}/{total}"