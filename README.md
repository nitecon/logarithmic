# Logarithmic

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.10.0-green)](https://pypi.org/project/PySide6/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

**The ultimate cross-platform log tailing application with intelligent grouping, syntax highlighting, and session management.**

![Main Window](images/main_window.png)

## 🚀 Why Logarithmic is the Best Log Tailing Application Ever

### 🎯 **Intelligent Log Management**
- **Session Management** - Save and restore complete log tracking sessions with window positions
- **Wildcard Support** - Track log files with patterns like `app-*.log` and automatically switch to newest files
- **Smart Grouping** - Organize related logs into groups with tabbed or combined views
- **Window Snapping** - Auto-snap windows together for perfect multi-monitor layouts

### 🎨 **Beautiful & Customizable Interface**
- **Syntax Highlighting** - Automatic colorization of errors (red), warnings (orange), and verbose logs (gray)
- **Custom Fonts** - Modern, readable typography with Michroma, Oxanium, and Red Hat Mono
- **Adjustable Font Sizes** - Separate controls for log content, UI elements, and status bars
- **Theme Support** - Customizable color schemes for different log levels

### ⚡ **Powerful Real-Time Features**
- **Live Mode** - Auto-scroll to latest logs with visual indicators
- **Pause/Resume** - Freeze updates while keeping the tail active in background
- **Go Live Button** - Instantly jump back to the latest logs
- **Clear on Demand** - Clear display without affecting the underlying log stream

### 🔧 **Advanced Capabilities**
- **Multi-Window Design** - Each log opens in its own independent window
- **File State Management** - Handles creation, deletion, rotation, and missing files gracefully
- **Combined View** - Merge multiple logs into a single interleaved stream with source labels
- **Tabbed View** - View multiple logs in tabs with individual controls
- **Persistent Settings** - All preferences, window positions, and sessions saved automatically

### 🤖 **AI Integration (NEW!)**
- **MCP Server** - Built-in Model Context Protocol server for AI agent integration
- **Claude Desktop Support** - Connect Claude to your logs for intelligent analysis
- **Log Metadata** - Add human-readable IDs and descriptions for better AI understanding
- **Search & Query Tools** - AI agents can list, search, and retrieve log content
- **Thread-Safe Architecture** - MCP server runs asynchronously without blocking the UI

## Quick Links

- **[Release Process](.github/RELEASE.md)** - How to build and release
- **[Coding Guidelines](Docs/CodingGuidelines.md)** - Python development standards
- **[MCP Server Quick Start](Docs/MCP_QUICKSTART.md)** - Get started with AI integration
- **[MCP Server Details](Docs/MCP_Details.md)** - Technical documentation for MCP server

## 📸 Screenshots

### Single Log Window - Live Tailing
![Single Window](images/single_window.png)
*Real-time log tailing with syntax highlighting, pause/resume, and live mode indicator*

### Grouped Logs - Tabbed View
![Grouped Tabbed](images/grouped_tabbed.png)
*Multiple related logs organized in tabs with individual controls for each*

### Grouped Logs - Combined View
![Grouped Combined](images/grouped_combined.png)
*Interleaved log streams with source labels for easy correlation*

## 🤖 AI Integration with MCP Server

Logarithmic now includes a built-in **Model Context Protocol (MCP) server** that allows AI agents like Claude Desktop to directly access and analyze your logs!

### Quick Start

1. **Enable MCP Server**: Go to Settings tab → Check "Enable MCP Server"
2. **Restart Application**: Changes take effect after restart
3. **Configure Claude Desktop**: Add Logarithmic to your Claude Desktop MCP servers
4. **Ask Claude**: "List all available logs" or "Search for errors in my application logs"

### What You Can Do

- 📋 **List Logs**: AI can see all your tracked logs with descriptions
- 🔍 **Search**: Find patterns across all logs instantly
- 📖 **Read Content**: AI can retrieve and analyze full log content
- 🐛 **Debug**: Ask AI to find errors, analyze patterns, or suggest fixes

**Learn More**: See [MCP Quick Start Guide](Docs/MCP_QUICKSTART.md) for detailed setup instructions.

## 📦 Installation

### Download Pre-Built Binaries

Download the latest release for your platform from the [Releases](https://github.com/YOUR_USERNAME/logarithmic/releases) page:

- **Windows**: `Logarithmic-Windows.zip` - Extract and run `Logarithmic.exe`
- **macOS**: `Logarithmic-macOS.zip` - Extract and run `Logarithmic.app`
- **Linux**: `Logarithmic-Linux.tar.gz` - Extract and run `./Logarithmic`

No installation required - just download, extract, and run!

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd logarithmic
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Install development dependencies** (optional)
   ```bash
   pip install -e ".[dev]"
   ```

## Running the Application

```bash
python -m logarithmic
```

Or from the source directory:

```bash
python src/logarithmic/__main__.py
```

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=src/logarithmic --cov-report=term-missing
```

## 📖 Usage Guide

### Getting Started

1. **Add a log file**: 
   - Enter the path to a log file in the input box
   - Click "Add" or press Enter
   - Supports wildcards: `C:\logs\app-*.log` or `/var/log/app-*.log`

2. **Open a viewer**: 
   - Double-click a log file in the list to open its viewer window
   - Windows automatically position themselves with smart snapping

### Session Management

Located at the top of the main window:

- **Save Session**: Preserves all tracked logs, groups, and window positions
- **Duplicate Session**: Create a copy of the current session
- **Delete Session**: Remove a saved session
- **Session Dropdown**: Quickly switch between saved sessions

### Log Groups

Organize related logs together:

1. **Create a Group**: Click "New Group" and give it a name
2. **Assign Logs**: Right-click a log → "Assign to Group"
3. **View Group**: Double-click the group to open the group window
4. **Switch Modes**: Toggle between Tabbed and Combined view

**Tabbed Mode**: Each log in its own tab with individual controls  
**Combined Mode**: All logs merged into one stream with source labels

### Window Controls

Every log window includes:

- **Pause Button**: Freeze updates while keeping the tail active
- **Clear Button**: Clear the display (history preserved in tabbed mode)
- **Go Live Button**: Appears when scrolled up - click to jump to latest logs
- **Status Bar**: Shows line count, live/scroll mode, and pause status
- **Set Default Size**: Save current window size as default for new windows

### Settings Tab

Customize your experience:

- **Log Content Font Size**: 6-24pt for log text
- **UI Elements Font Size**: 6-18pt for buttons and labels
- **Status Bar Font Size**: 6-14pt for status text
- **MCP Server**: Enable AI agent integration (see [MCP Quick Start](Docs/MCP_QUICKSTART.md))
  - Enable/disable MCP server
  - Configure binding address (default: 127.0.0.1)
  - Configure port (default: 3000)
- **Theme Colors**: Customize error, warning, verbose, and default colors (coming soon)

### Keyboard Shortcuts

- **Enter**: Add log file from input box
- **Double-Click**: Open log viewer or group window
- **Scroll Up**: Exit live mode (shows Go Live button)
- **Scroll to Bottom**: Re-enter live mode automatically

### Syntax Highlighting

Logs are automatically colorized based on keywords:

- **🔴 Red**: error, fatal, critical, exception, fail, failed, failure
- **🟠 Orange**: warning, warn, caution, deprecated
- **⚪ Gray**: verbose, debug, trace
- **Default**: Normal log text

## 🏗️ Architecture

The application follows a clean architecture with separation of concerns:

### Core Components

- **`main_window.py`**: Main control window with session and group management
- **`log_viewer_window.py`**: Individual log viewer windows with ContentController
- **`log_group_window.py`**: Group windows with tabbed and combined modes
- **`content_controller.py`**: Unified content display and control management
- **`log_manager.py`**: Centralized log buffer and subscriber management
- **`file_watcher.py`**: File watching and tailing logic using watchdog
- **`wildcard_watcher.py`**: Wildcard pattern matching and file switching
- **`log_highlighter.py`**: Syntax highlighting for log content
- **`settings.py`**: Session, preferences, and theme management
- **`fonts.py`**: Custom font loading and management

### MCP Server Components

- **`mcp_server.py`**: Model Context Protocol server for AI agent integration
- **`mcp_bridge.py`**: Thread-safe bridge between LogManager and MCP server
- Exposes logs as MCP resources with tools for listing, searching, and retrieving content
- Runs asynchronously in separate thread without blocking the UI
- See [MCP Server Details](Docs/MCP_Details.md) for architecture details

### File State Management

The file watcher implements a robust three-state system:

1. **Non-Existent**: Watch parent directory for file creation
2. **Exists**: Tail the file and watch for deletion/move
3. **Deleted/Moved**: Close handles and return to state 1

This ensures graceful handling of log rotation, file system changes, and wildcard pattern matching.

### Subscriber Pattern

The `LogManager` implements a publisher-subscriber pattern:
- Log viewers and group windows subscribe to specific log files
- New content is broadcast to all subscribers
- Efficient memory management with centralized buffering
- Supports multiple subscribers per log file

## ✨ Key Features in Detail

### Session Management
- **Auto-save**: Last used session loads automatically on startup
- **Multiple Sessions**: Switch between different project configurations
- **Complete State**: Saves logs, groups, window positions, and settings
- **Duplicate & Delete**: Easily manage your session library

### Wildcard Support
- **Pattern Matching**: Use `*` and `?` in file paths
- **Auto-Switch**: Automatically follows the newest matching file
- **Rotation Handling**: Seamlessly handles log rotation
- **Visual Indicator**: Shows current file in window title

### Log Grouping
- **Flexible Organization**: Group related logs by project, service, or environment
- **Two View Modes**: Tabbed for individual focus, Combined for correlation
- **Independent Controls**: Each tab has its own pause/clear/live controls
- **Source Labels**: Combined mode prefixes each line with the source filename

### Smart Window Management
- **Auto-Snapping**: Windows snap to each other within 20 pixels
- **Position Memory**: Window positions saved per log/group
- **Default Sizing**: Set your preferred default window size
- **Multi-Monitor**: Works seamlessly across multiple displays

### Syntax Highlighting
- **Real-Time**: Applied as logs stream in
- **Customizable**: Theme colors configurable per session
- **Performance**: Efficient Qt-based syntax highlighter
- **Keyword-Based**: Matches common logging patterns

## 📁 Project Structure

```
logarithmic/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # Continuous integration
│   │   └── release.yml         # Automated releases
│   └── RELEASE.md              # Release documentation
├── Docs/
│   ├── CodingGuidelines.md     # Development standards
│   ├── MCP_QUICKSTART.md       # MCP server quick start guide
│   └── MCP_Details.md          # MCP server technical details
├── fonts/
│   ├── Michroma/               # Title font
│   ├── Oxanium/                # UI font
│   └── Red_Hat_Mono/           # Monospace log font
├── images/
│   ├── main_window.png         # Screenshots
│   ├── single_window.png
│   ├── grouped_tabbed.png
│   └── grouped_combined.png
├── src/
│   └── logarithmic/
│       ├── __init__.py
│       ├── __main__.py         # Application entry point
│       ├── content_controller.py   # Unified content display
│       ├── exceptions.py       # Custom exceptions
│       ├── file_watcher.py     # File tailing logic
│       ├── fonts.py            # Font management
│       ├── log_group_window.py # Group window UI
│       ├── log_highlighter.py  # Syntax highlighting
│       ├── log_manager.py      # Log buffer management
│       ├── log_viewer_window.py    # Single log window
│       ├── main_window.py      # Main control window
│       ├── mcp_bridge.py       # MCP server bridge
│       ├── mcp_server.py       # MCP server implementation
│       ├── settings.py         # Session & preferences
│       └── wildcard_watcher.py # Wildcard pattern support
├── .gitignore
├── LICENSE                     # Apache 2.0
├── Logarithmic.spec           # PyInstaller configuration
├── pyproject.toml             # Project metadata
├── requirements.txt           # Dependencies
└── README.md
```

## 🎯 Use Cases

Logarithmic is perfect for:

- **Software Development**: Monitor application logs during development and debugging
- **DevOps**: Track multiple service logs across microservices architectures
- **System Administration**: Watch system logs, web server logs, and application logs simultaneously
- **Game Development**: Monitor Unreal Engine, Unity, or custom game engine logs
- **CI/CD Pipelines**: Track build and deployment logs in real-time
- **Testing**: Monitor test execution logs with automatic error highlighting
- **Production Monitoring**: Keep an eye on production logs with session-based organization
- **AI-Assisted Debugging**: Use Claude or other AI agents to analyze logs and find issues faster

## 🤝 Contributing

All contributions must follow the standards defined in [Docs/CodingGuidelines.md](Docs/CodingGuidelines.md).

Key requirements:
- Use `ruff` for linting and formatting
- Use `mypy` for type checking
- Include type hints for all functions
- Write tests for new functionality
- Follow Google-style docstrings

## 📄 License

Copyright 2025 Willem J Hattingh

Licensed under the Apache License, Version 2.0 - See [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

### Fonts

Logarithmic uses three beautiful open-source fonts:

- **[Michroma](https://github.com/googlefonts/Michroma-font)** - Window titles (SIL OFL 1.1)
- **[Oxanium](https://github.com/sevmeyer/oxanium)** - UI elements (SIL OFL 1.1)
- **[Red Hat Mono](https://github.com/RedHatOfficial/RedHatFont)** - Log content (SIL OFL 1.1)

All fonts are licensed under the SIL Open Font License 1.1.

---

**Made with ❤️ for developers who love clean, powerful log tailing.**
