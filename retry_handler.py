import time
import os
from typing import Callable, Any, Optional
from PyQt6.QtCore import QObject, pyqtSignal


class RetryHandler(QObject):
    """
    Handles retry logic for failed downloads with exponential backoff
    """
    retry_attempt = pyqtSignal(int, int, str)  # current_attempt, max_attempts, error_msg
    retry_success = pyqtSignal(str)  # success message
    retry_failed = pyqtSignal(str)  # final failure message

    def __init__(self, max_retries=3, retry_delays=None):
        super().__init__()
        self.max_retries = max_retries
        # Custom delay schedule: 30s, 1min, 3min
        self.retry_delays = retry_delays or [30, 60, 180]
        self._is_cancelled = False

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic using custom delay schedule

        Args:
            func: Function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of successful function execution

        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):  # +1 for the initial attempt
            if self._is_cancelled:
                raise Exception("Retry cancelled by user")

            try:
                if attempt > 0:
                    # Get delay for this retry attempt (attempt-1 because array is 0-indexed)
                    delay = self.retry_delays[min(attempt - 1, len(self.retry_delays) - 1)]
                    self.retry_attempt.emit(attempt, self.max_retries, str(last_exception))

                    # Wait with the custom delay
                    time.sleep(delay)

                result = func(*args, **kwargs)

                if attempt > 0:
                    self.retry_success.emit(f"Download succeeded after {attempt} retry attempts")

                return result

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error
                if not self._is_retryable_error(e):
                    raise e

                if attempt == self.max_retries:
                    self.retry_failed.emit(f"Download failed after {self.max_retries} retry attempts: {str(e)}")
                    raise e

        # This should never be reached, but just in case
        raise last_exception

    def _is_retryable_error(self, exception: Exception) -> bool:
        """
        Determine if an error is worth retrying

        Args:
            exception: The exception that occurred

        Returns:
            True if the error might be temporary and worth retrying
        """
        error_msg = str(exception).lower()

        # Network-related errors that are worth retrying
        retryable_patterns = [
            'connection', 'timeout', 'network', 'unreachable',
            'temporary failure', 'service unavailable', 'bad gateway',
            'gateway timeout', 'connection reset', 'connection refused',
            'dns', 'resolve', 'interrupted', 'broken pipe',
            'http error 5', 'http error 429',  # Server errors and rate limiting
            'unable to download', 'download error'
        ]

        # Non-retryable errors (permanent failures)
        non_retryable_patterns = [
            'video unavailable', 'private video', 'video removed',
            'copyright', 'blocked', 'not found', 'invalid url',
            'unsupported url', 'age restricted', 'login required',
            'cancelled by user', 'sign in to confirm you\'re not a bot'
        ]

        # Check for non-retryable errors first
        for pattern in non_retryable_patterns:
            if pattern in error_msg:
                return False

        # Check for retryable errors
        for pattern in retryable_patterns:
            if pattern in error_msg:
                return True

        # Default to retrying unknown errors (they might be temporary)
        return True

    def cancel(self):
        """Cancel the retry process"""
        self._is_cancelled = True

    def reset(self):
        """Reset the retry handler for a new operation"""
        self._is_cancelled = False


class NetworkStatusChecker:
    """
    Simple network connectivity checker
    """

    @staticmethod
    def is_connected(test_urls=None) -> bool:
        """
        Check if network is available by trying to connect to test URLs

        Args:
            test_urls: List of URLs to test (defaults to common sites)

        Returns:
            True if network appears to be available
        """
        import urllib.request
        import socket

        if test_urls is None:
            test_urls = [
                'https://www.google.com',
                'https://www.youtube.com',
                'https://httpbin.org/status/200'
            ]

        for url in test_urls:
            try:
                urllib.request.urlopen(url, timeout=5)
                return True
            except (urllib.error.URLError, socket.timeout, socket.error):
                continue

        return False

    @staticmethod
    def wait_for_connection(max_wait_time=30, check_interval=2) -> bool:
        """
        Wait for network connection to be restored

        Args:
            max_wait_time: Maximum time to wait in seconds
            check_interval: How often to check in seconds

        Returns:
            True if connection was restored, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            if NetworkStatusChecker.is_connected():
                return True
            time.sleep(check_interval)

        return False


# Utility function to create a configured retry handler
def create_download_retry_handler(max_retries=3, retry_delays=None) -> RetryHandler:
    """
    Create a pre-configured retry handler for downloads

    Args:
        max_retries: Maximum number of retry attempts
        retry_delays: List of delays in seconds for each retry attempt

    Returns:
        Configured RetryHandler instance
    """
    if retry_delays is None:
        retry_delays = [30, 60, 180]  # 30s, 1min, 3min
    return RetryHandler(max_retries, retry_delays)