# YouTube Downloader - Cookie Management

## Overview

The YouTube Downloader now includes automatic cookie management to handle YouTube's authentication requirements. This feature helps bypass age restrictions and bot detection by using your browser's cookies.

## Features

- **Automatic Detection**: Automatically detects and extracts YouTube cookies from your installed browsers
- **Multi-Browser Support**: Supports Chrome, Firefox, Edge, Brave, Opera, and Safari
- **Manual Setup**: Option to manually select a cookies.txt file
- **Cookie Testing**: Built-in validation to ensure cookies are valid
- **Settings Integration**: Cookie preferences are saved in the settings

## How It Works

### Automatic Detection

1. **On Startup**: The app automatically tries to detect cookies from your browsers if enabled
2. **When Needed**: If a download fails due to authentication, the app prompts for cookies
3. **Cross-Platform**: Works on Windows, macOS, and Linux

### Manual Setup

1. **Browser Extension Method** (Recommended):
   - Install "Get cookies.txt" extension for Chrome/Firefox
   - Go to YouTube and log in
   - Export cookies using the extension
   - Select the file in the settings

2. **Manual Export Method**:
   - Open browser DevTools (F12)
   - Go to Application → Cookies → youtube.com
   - Export cookies in Netscape format

## Installation

1. Install the required dependency:
   ```bash
   pip install browser-cookie3
   ```

2. Or install all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Automatic Mode (Default)

1. Open the YouTube Downloader
2. Go to Settings → Authentication Settings
3. Ensure "Auto-detect browser cookies" is checked
4. The app will automatically detect cookies on startup

### Manual Mode

1. Go to Settings → Authentication Settings
2. Uncheck "Auto-detect browser cookies"
3. Click "Browse" to select a cookies.txt file
4. Click "Test" to validate the cookies

### When Authentication is Required

If you encounter the "Sign in to confirm you're not a bot" error:

1. The app will automatically show a cookie detection dialog
2. Click "Auto-Detect All" to try automatic detection
3. Or click "Manual Setup" to select a cookies file
4. The download will retry with the provided cookies

## Settings

### Authentication Settings

- **Auto-detect browser cookies**: Enable automatic cookie detection
- **Preferred browser**: Choose which browser to try first
- **Cookie file path**: Manual path to a cookies.txt file
- **Test button**: Validate the selected cookie file
- **Auto-Detect Now**: Manually trigger cookie detection
- **Help**: Show detailed instructions

### Cookie Status

The settings show the current status of your cookies:
- ✅ Valid YouTube cookies
- ❌ Invalid or no YouTube cookies
- Not tested

## Supported Browsers

- **Chrome**: All platforms
- **Firefox**: All platforms  
- **Edge**: All platforms
- **Brave**: All platforms
- **Opera**: All platforms
- **Safari**: macOS only

## Security & Privacy

- **No Passwords**: Cookies don't contain passwords or personal data
- **Temporary Files**: Cookie files are stored temporarily and cleaned up automatically
- **Local Only**: All cookie processing happens locally on your machine
- **YouTube Only**: Only YouTube-specific cookies are extracted

## Troubleshooting

### "No supported browsers detected"

- Make sure you have at least one supported browser installed
- Ensure the browser is properly installed (not just a shortcut)

### "No valid cookies found"

- Make sure you're logged into YouTube in your browser
- Try refreshing your browser's YouTube session
- Check if cookies are enabled in your browser

### "Cookie file is invalid"

- Ensure the file is in the correct Netscape format
- Make sure it contains YouTube cookies
- Try exporting fresh cookies from your browser

### "browser-cookie3 not available"

- Install the required dependency: `pip install browser-cookie3`
- Or install all requirements: `pip install -r requirements.txt`

## Cookie Expiration

- YouTube cookies typically expire after 30-90 days
- You'll need to refresh cookies when downloads start failing
- The app will prompt you when cookies are needed

## Advanced Usage

### Command Line

You can also use the cookie management functions directly:

```python
from cookie_manager import auto_detect_cookies, test_cookies

# Auto-detect cookies
cookie_file, browser = auto_detect_cookies()

# Test a cookie file
is_valid = test_cookies("path/to/cookies.txt")
```

### Integration

The cookie management is automatically integrated into the download process:

```python
# Cookies are automatically used when available
# No additional code needed for basic usage
```

## Browser Extensions

### Chrome
- [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid)

### Firefox  
- [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

## Notes

- Cookies help bypass age restrictions and bot detection
- They don't contain sensitive information like passwords
- Cookie files should be kept private and not shared
- The feature works best when you're logged into YouTube in your browser



















