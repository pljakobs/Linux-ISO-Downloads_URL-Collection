# Logging in distroget

## Overview

distroget now includes comprehensive logging to help diagnose issues with downloads, torrent support, and other operations.

## Log File Location

By default, logs are written to:
```
~/.config/distroget/distroget.log
```

## Log Levels

- **DEBUG**: Detailed diagnostic information (aria2c output, subprocess details, queue operations)
- **INFO**: General information about operations (downloads queued, completed, torrent detection)
- **WARNING**: Warning messages (sent to console and log file)
- **ERROR**: Error messages (sent to console and log file)

## What is Logged

### Download Operations
- When URLs are added to the download queue
- When worker threads pick up downloads
- Progress updates for regular and torrent downloads
- Download completion or failure
- Retry attempts and exponential backoff

### Torrent Downloads
- Torrent URL detection
- aria2c availability checks
- aria2c command execution
- Real-time aria2c output (stdout/stderr)
- aria2c process exit codes
- Torrent download progress and speed

### Application Lifecycle
- Application startup
- Configuration loading
- Download manager initialization
- Worker thread activity

## Viewing Logs

### View recent log entries:
```bash
tail -f ~/.config/distroget/distroget.log
```

### View logs during operation:
Open a second terminal and run:
```bash
tail -f ~/.config/distroget/distroget.log
```

Then run distroget in the first terminal.

### Search for specific events:
```bash
# Find all torrent-related logs
grep torrent ~/.config/distroget/distroget.log

# Find all errors
grep ERROR ~/.config/distroget/distroget.log

# Find aria2c output
grep aria2c ~/.config/distroget/distroget.log
```

## Testing Logging

Use the included test script to verify logging is working:
```bash
python3 test_logging.py
```

This will:
1. Initialize logging
2. Test torrent URL detection
3. Check aria2c availability
4. Write test entries to the log file

## Troubleshooting Torrent Downloads

When a torrent download fails:

1. **Check if torrent is detected:**
   ```bash
   grep "Detected torrent URL" ~/.config/distroget/distroget.log
   ```

2. **Check if aria2c is available:**
   ```bash
   grep "aria2c available" ~/.config/distroget/distroget.log
   ```

3. **View aria2c output:**
   ```bash
   grep "aria2c output" ~/.config/distroget/distroget.log
   ```

4. **Check for subprocess errors:**
   ```bash
   grep "aria2c failed" ~/.config/distroget/distroget.log
   ```

5. **View full download flow:**
   ```bash
   grep "eos-eos3.9" ~/.config/distroget/distroget.log
   ```

## Log Rotation

Currently, logs are appended to the same file. For production use, consider implementing log rotation:

```python
from logging.handlers import RotatingFileHandler

# In logger_config.py, replace FileHandler with:
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5            # Keep 5 old logs
)
```

## Debug Mode

The application currently runs in DEBUG mode by default (in `distroget.py`):
```python
log_file = setup_logging(log_level=logging.DEBUG)
```

For production use, change to INFO level:
```python
log_file = setup_logging(log_level=logging.INFO)
```

## Log Format

Each log entry includes:
- Timestamp (YYYY-MM-DD HH:MM:SS)
- Logger name (distroget.module)
- Log level (DEBUG, INFO, WARNING, ERROR)
- Message

Example:
```
2025-12-06 14:46:30 - distroget.torrent - INFO - Starting torrent download: https://example.com/file.torrent
2025-12-06 14:46:30 - distroget.torrent - DEBUG - Running command: aria2c --seed-time=0 ...
2025-12-06 14:46:31 - distroget.torrent - DEBUG - aria2c output: [#1 SIZE:0B/100MB CN:1 DL:1.5MB]
```

## Integration with Tests

The test suite respects the logging configuration. When running tests:

```bash
# Run tests with log output
pytest -v

# Run tests and view logs
tail -f ~/.config/distroget/distroget.log &
pytest -v
```

## Performance Considerations

- Log file writes are buffered by Python's logging module
- DEBUG level logging adds minimal overhead (~1-2% in typical cases)
- For maximum performance, switch to INFO or WARNING level
- Use `tail -f` instead of repeatedly reading the entire log file
