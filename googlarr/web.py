"""
Simple web interface for Googlarr.
Run alongside the daemon to provide a UI on port 8721.
"""

import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from croniter import croniter
from googlarr.config import load_config
from googlarr.prank import apply_pranks, restore_originals
from googlarr.db import reset_failed_items

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


def get_db():
    """Get database path from config."""
    config = load_config()
    return config['database']


def get_config():
    """Get current config."""
    return load_config()


def is_prank_active(config):
    """Check if prank window is currently active."""
    now = datetime.now()
    cron_on = croniter(config['schedule']['start'], now)
    cron_off = croniter(config['schedule']['stop'], now)
    last_on = cron_on.get_prev(datetime)
    last_off = cron_off.get_prev(datetime)
    return last_on > last_off


@app.route('/')
def index():
    """Serve the main HTML page."""
    try:
        html_path = os.path.join(os.path.dirname(__file__), 'web_ui.html')
        with open(html_path, 'r') as f:
            html = f.read()
        return html
    except Exception as e:
        return f"<h1>Error loading UI: {str(e)}</h1>", 500


@app.route('/api/status')
def api_status():
    """Get daemon status."""
    config = get_config()
    db_path = get_db()

    now = datetime.now()
    cron_on = croniter(config['schedule']['start'], now)
    cron_off = croniter(config['schedule']['stop'], now)

    next_on = cron_on.get_next(datetime)
    next_off = cron_off.get_next(datetime)

    # Get item counts by status
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT status, COUNT(*) FROM library_items GROUP BY status")
        status_counts = {row[0]: row[1] for row in c.fetchall()}

        # Get failed items
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT item_id, title, retry_count FROM library_items WHERE status = 'FAILED' ORDER BY retry_count DESC LIMIT 5"
        )
        failed_items = [dict(row) for row in c.fetchall()]

    return jsonify({
        'prank_active': is_prank_active(config),
        'next_apply': next_on.isoformat(),
        'next_restore': next_off.isoformat(),
        'items': {
            'total': sum(status_counts.values()),
            **status_counts
        },
        'failed_items': failed_items,
        'last_updated': datetime.now().isoformat()
    })


@app.route('/api/libraries')
def api_libraries():
    """Get list of configured libraries."""
    config = get_config()
    db_path = get_db()

    libraries = []
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        for lib_name in config['plex']['libraries']:
            c.execute("SELECT COUNT(*) FROM library_items WHERE library = ?", (lib_name,))
            count = c.fetchone()[0]
            libraries.append({
                'name': lib_name,
                'count': count
            })

    return jsonify({'libraries': libraries})


@app.route('/api/library/<library_name>')
def api_library(library_name):
    """Get items in a library with pagination."""
    db_path = get_db()
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=20, type=int)

    offset = (page - 1) * limit

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get total count
        c.execute("SELECT COUNT(*) FROM library_items WHERE library = ?", (library_name,))
        total = c.fetchone()[0]

        # Get items for this page
        c.execute(
            "SELECT item_id, title, status FROM library_items WHERE library = ? ORDER BY title LIMIT ? OFFSET ?",
            (library_name, limit, offset)
        )
        items = [dict(row) for row in c.fetchall()]

    return jsonify({
        'library': library_name,
        'page': page,
        'limit': limit,
        'total': total,
        'items': items
    })


@app.route('/api/posters/<item_id>/original')
def api_poster_original(item_id):
    """Serve original poster image."""
    config = get_config()
    db_path = get_db()

    # Get poster path from database
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT original_path FROM library_items WHERE item_id = ?", (item_id,))
        row = c.fetchone()

    if not row:
        return jsonify({'error': 'Item not found'}), 404

    original_path = row[0]
    if not os.path.exists(original_path):
        return jsonify({'error': 'Original poster not found'}), 404

    return send_file(original_path, mimetype='image/jpeg')


@app.route('/api/posters/<item_id>/prank')
def api_poster_prank(item_id):
    """Serve prank poster image."""
    config = get_config()
    db_path = get_db()

    # Get poster path from database
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("SELECT prank_path FROM library_items WHERE item_id = ?", (item_id,))
        row = c.fetchone()

    if not row:
        return jsonify({'error': 'Item not found'}), 404

    prank_path = row[0]
    if not os.path.exists(prank_path):
        return jsonify({'error': 'Prank poster not found'}), 404

    return send_file(prank_path, mimetype='image/jpeg')


@app.route('/api/apply-now', methods=['POST'])
def api_apply_now():
    """Override: Apply all PRANK_GENERATED items immediately."""
    config = get_config()
    try:
        from plexapi.server import PlexServer
        plex = PlexServer(config['plex']['url'], config['plex']['token'])
        count = apply_pranks(config, plex)
        return jsonify({
            'success': True,
            'applied_count': count,
            'message': f'Applied {count} prank poster(s) (override)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/restore-now', methods=['POST'])
def api_restore_now():
    """Override: Restore all PRANK_APPLIED items immediately."""
    config = get_config()
    try:
        from plexapi.server import PlexServer
        plex = PlexServer(config['plex']['url'], config['plex']['token'])
        count = restore_originals(config, plex)
        return jsonify({
            'success': True,
            'restored_count': count,
            'message': f'Restored {count} original poster(s) (override)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/reload', methods=['POST'])
def api_config_reload():
    """Signal daemon to reload config."""
    try:
        from googlarr.main import signal_config_reload
        signal_config_reload()
        return jsonify({
            'success': True,
            'message': 'Config reload signaled to daemon'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


