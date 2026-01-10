# Changelog

All notable changes to Logarithmic will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Auto-Update Notifications** - Application checks GitHub releases on startup and notifies when updates are available
  - Background thread for non-blocking version checks
  - "Check for Updates" button in Settings tab
  - Smart dev version detection (shows `X.Y.Z-dev` for uncommitted changes)
  - Dialog with link to release page when update available
- **Log Filtering** - Real-time text filtering for log content
  - Filter input box in log viewer and group windows
  - Case-insensitive toggle option
  - Clear filter button to restore full view
  - Status bar shows filtered/total line counts
- **About Section** in Settings tab showing current version

### Changed
- Combined view mode now defaults for new groups
- Group mode preference persisted per group and restored on app launch

### Fixed
- MCP server shutdown race condition resolved for clean termination
- Legacy watcher system removed (all tracking now uses provider system)

### Removed
- Dead compatibility methods from `log_group_window.py`
- Unused `FileWatcherThread` and `WildcardFileWatcher` imports

---

## [1.2.8] - 2025-01-XX

### Added
- MCP Server improvements
  - `get_log_last_lines` tool for retrieving last 500, 1000, or 5000 lines
  - `list_groups` tool for listing log groups
  - `get_group_content` tool for retrieving combined view content
  - Combined view prioritization when content is available

### Fixed
- MCP server graceful shutdown

---

## [1.2.0] - 2025-XX-XX

### Added
- **MCP Server** - Model Context Protocol server for AI agent integration
  - Claude Desktop support
  - Log listing, searching, and content retrieval tools
  - Thread-safe architecture with async operation
- **Combined View Mode** - Merge multiple logs into interleaved stream
- **Log Groups** - Organize related logs with tabbed or combined views

---

## [1.1.0] - 2025-XX-XX

### Added
- **Wildcard Support** - Track log files with patterns like `app-*.log`
- **Session Management** - Save and restore complete log tracking sessions
- **Window Snapping** - Auto-snap windows together for multi-monitor layouts
- **F3 Window Recovery** - Move all windows to cursor position

---

## [1.0.0] - 2025-XX-XX

### Added
- Initial release
- Real-time log tailing with syntax highlighting
- Multi-window design with independent log viewers
- Pause/Resume functionality
- Go Live button for jumping to latest logs
- Custom font support (Michroma, Oxanium, Red Hat Mono)
- Adjustable font sizes for content, UI, and status bars
- File state management (handles rotation, deletion, creation)
- Persistent settings and window positions

---

[Unreleased]: https://github.com/Nitecon/logarithmic/compare/v1.2.8...HEAD
[1.2.8]: https://github.com/Nitecon/logarithmic/compare/v1.2.0...v1.2.8
[1.2.0]: https://github.com/Nitecon/logarithmic/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Nitecon/logarithmic/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Nitecon/logarithmic/releases/tag/v1.0.0
