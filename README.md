# Googlarr

> A chaotic and deeply unnecessary tool that applies googly eyes to your Plex posters on a schedule.  
> You were warned.

---

## WARNING — THIS PROJECT MAY RUIN YOUR POSTERS

Googlarr uses the Plex API to modify the posters for your Plex media items **in place**. It tries to save and restore the originals, but:

- It might miss a poster
- It might fail to restore properly
- Plex might cache something weird
- You might regret everything

**Use at your own risk. This project is for prank purposes only. I cannot provide support in case of failure.**

---

## What It Does

Googlarr is a scheduled prank daemon that:

1. Scans your Plex libraries for movies and/or shows
2. Detects faces and eye positions in poster images
3. Applies googly eyes using image overlays
4. Swaps the posters on a cron-based schedule
5. Restores the originals after the prank window

---

## Setup

1. Copy `config/config.example.yml` to `config/config.yml` and fill in your Plex URL, token, and libraries
2. Build and run via `./googlarr.sh build && ./googlarr.sh run` (or `docker compose up -d`)
3. Pray

---

## Example Config

```yaml
plex:
  url: http://your.plex.server:32400
  token: your_plex_token
  libraries:
    - Movies
    - TV Shows

paths:
  originals_dir: data/originals
  prank_dir: data/prank

database: "data/googlarr.db"

schedule:
  start: "0 9 * * *"    # Apply prank at 9am daily (cron format)
  stop: "0 17 * * *"    # Restore at 5pm daily (cron format)

detection:
  face_detection_confidence: 0.5
  landmark_detection_confidence: 0.5
  max_faces: 10
  scale_by_face_size: true
  face_based_eye_scale: 0.35
  use_same_size_for_both_eyes: true
  debug_draw_faces: false
```

---

## CLI Tools

### Check Status
```bash
python -m googlarr.status              # Show summary + schedule + failed items
python -m googlarr.status <item_id>    # Show details for specific item
```

### Manual Poster Control
```bash
python -m googlarr.apply               # Manually apply prank posters
python -m googlarr.restore             # Manually restore original posters
```

### Retry Failed Items
```bash
python -m googlarr.reset               # Reset all failed items back to NEW
python -m googlarr.reset <item_id>     # Reset specific item only
```

### Regenerate Prank (Single Item)
```bash
python -m googlarr.regenerate <item_id>  # Download + regenerate prank for one item
```

---

## Web UI

Googlarr includes a lightweight web interface running on **port 8721**. Access it at:
```
http://your-host:8721
```

The web UI starts automatically when you run the daemon and provides:

### Status Page
- **Current Status**: Shows if prank window is ACTIVE or INACTIVE
- **Schedule Info**: Next apply and restore times
- **Statistics**: Breakdown of items by status with human-readable labels
- **Failed Items**: List of failed items with retry counts
- **Override Controls**:
  - `Apply Now` - Immediately apply all ready pranks (bypass schedule)
  - `Restore Now` - Immediately restore all applied pranks (bypass schedule)
  - `↻ Reload Config` - Signal daemon to reload config instantly
- **Auto-Refresh**: Updates every 5 seconds

### Library Page
- **Browse**: Select which library to view from dropdown
- **Status Filter**: Filter posters by status (Prank Ready, Original, Failed, etc.)
- **Poster Grid**: Responsive grid with colour-coded status badges on each poster
- **Hover Preview**: Hover over a pranked poster to see the googly eye version — badge changes to "Viewing Prank"
- **Infinite Scroll**: Automatically loads more items as you scroll

### Features
- ✅ Dark theme, easy on the eyes
- ✅ Fully responsive (desktop, tablet, mobile)
- ✅ Real-time status updates
- ✅ No external dependencies (vanilla JavaScript)
- ✅ Integrates with daemon for instant control

---

## Config Validation

Googlarr validates your config on startup and will exit with a clear error message if anything is missing:

**Required keys:**
- `plex.url`, `plex.token`, `plex.libraries`
- `schedule.start`, `schedule.stop` (must be valid cron expressions)
- `paths.originals_dir`, `paths.prank_dir`
- `database`
- `detection.face_detection_confidence`, `detection.landmark_detection_confidence`, `detection.max_faces`

If any required key is missing or invalid, the daemon will not start.

## Architecture

### State Machine
Each poster goes through this state flow:
```
NEW → WORKING_DOWNLOAD → ORIGINAL_DOWNLOADED → WORKING_PRANKIFY → PRANK_GENERATED → PRANK_APPLIED
                                                                          ↑
                                                                   (restored to this)
```

Failed items retry up to 3 times automatically before staying in `FAILED` state.

### Key Components
- **main.py**: Async daemon with three concurrent tasks (sync, poster_worker, update_posters_task)
- **prank.py**: Core prank logic (face detection, overlay generation, poster upload)
- **db.py**: SQLite state management
- **config.py**: YAML config loader + validation
- **detect.py**: Face/eye detection using MediaPipe
- **overlay.py**: Image manipulation (googly eye overlay application)

---

## Responsive Daemon

The daemon is **responsive to config changes without requiring a restart**:

### How It Works
- All tasks reload config at each iteration
- Sleep durations capped at **60 seconds** (was hours)
- When config file is edited, changes are picked up **within 60 seconds**
- API signal (if frontend added) triggers **instant** reload
- Graceful error handling: continues with old config if validation fails

### Config Change Examples

**Edit config file:**
```bash
nano config/config.yml        # Change schedule, libraries, etc
# Daemon picks up changes within 60 seconds, no restart needed
```

**From API/Frontend:**
```python
from googlarr.main import signal_config_reload
signal_config_reload()  # Daemon recalculates immediately
```

### Responsiveness
| Task | Delay |
|------|-------|
| Config file changes | ~60 seconds |
| API signal | Instant |
| New items in Plex | ~60 seconds |


---

## Development

Portions of this project were created with AI code generation (ChatGPT and [Claude Code](https://claude.ai/code)). I am a veteran software engineer however, and have code inspected the output and run extensive testing on multiple libraries.

I also use Claude Code to manage git because I am bad at git.

### Recent Improvements
- **Improved face detection**: Fixed coordinate rescaling bug on large images, full 16-point eye contours for more accurate placement
- **Web UI**: Status dashboard + library browser with status filter on port 8721
- **Poster status badges**: Colour-coded per-poster status in library view, hover to preview prank
- **Unified code paths**: Apply/restore logic extracted to reusable functions (no more duplication)
- **Config validation**: Required keys checked on startup with clear error messages
- **CLI tools**: Manual control over apply/restore/reset operations
- **Enhanced status**: Shows schedule info, failed items, and retry counts
- **Retry system**: Failed items automatically retry up to 3 times
- **Responsive daemon**: Config changes picked up within 60s without restart
- **Override controls**: Apply/Restore buttons to bypass schedule from UI

## License
MIT. See `LICENSE`.

Portions of `overlay.py` and `detector.py` were adapted from MIT-licensed sources. See `LICENSES/` for attribution.
