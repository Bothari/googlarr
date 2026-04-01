# Per-Item Apply/Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Apply and Restore buttons to each poster card in the web UI so a single item's prank poster can be pushed to or pulled from Emby immediately.

**Architecture:** Two new Flask endpoints (`POST /api/items/<item_id>/apply` and `/restore`) handle the upload and DB status update. The web UI renders small action buttons inside each poster card that appear on hover, call the endpoints, and update the card's status badge inline without a page reload.

**Tech Stack:** Python/Flask (backend), vanilla JS/HTML/CSS (frontend), SQLite (status tracking)

---

## File Map

| File | Change |
|---|---|
| `googlarr/web.py` | Add `api_item_apply` and `api_item_restore` endpoints |
| `googlarr/web_ui.html` | Add CSS for action buttons + JS handlers + render buttons in poster cards |

---

## Task 1: Add backend endpoints to `web.py`

**Files:**
- Modify: `googlarr/web.py`

- [ ] **Step 1: Add the two endpoints after `api_poster_prank` (around line 200)**

Insert the following two functions into `googlarr/web.py`, after the `api_poster_prank` function and before `api_apply_now`:

```python
@app.route('/api/items/<item_id>/apply', methods=['POST'])
def api_item_apply(item_id):
    """Apply prank poster to a single item immediately."""
    config = get_config()
    db_path = get_db()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM library_items WHERE item_id = ?", (item_id,))
        item = c.fetchone()

    if not item:
        return jsonify({'success': False, 'error': 'Item not found'}), 404

    item = dict(item)
    prank_path = os.path.join(APP_ROOT, item['prank_path'])
    if not os.path.exists(prank_path):
        return jsonify({'success': False, 'error': 'Prank poster not generated yet'}), 400

    try:
        from googlarr.server import create_server
        from googlarr.db import update_item_status
        server = create_server(config)
        server.upload_poster(item_id, prank_path)
        update_item_status(db_path, item_id, 'PRANK_APPLIED')
        return jsonify({'success': True, 'status': 'PRANK_APPLIED'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/items/<item_id>/restore', methods=['POST'])
def api_item_restore(item_id):
    """Restore original poster for a single item immediately."""
    config = get_config()
    db_path = get_db()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM library_items WHERE item_id = ?", (item_id,))
        item = c.fetchone()

    if not item:
        return jsonify({'success': False, 'error': 'Item not found'}), 404

    item = dict(item)
    original_path = os.path.join(APP_ROOT, item['original_path'])
    if not os.path.exists(original_path):
        return jsonify({'success': False, 'error': 'Original poster not found'}), 400

    try:
        from googlarr.server import create_server
        from googlarr.db import update_item_status
        server = create_server(config)
        server.upload_poster(item_id, original_path)
        update_item_status(db_path, item_id, 'PRANK_GENERATED')
        return jsonify({'success': True, 'status': 'PRANK_GENERATED'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 2: Verify Flask can import with the new endpoints**

```bash
cd /home/jeremy/GitHub/JPT62089/googlarr
python -c "from googlarr.web import app; print([r.rule for r in app.url_map.iter_rules() if 'items' in r.rule])"
```

Expected output:
```
['/api/items/<item_id>/apply', '/api/items/<item_id>/restore']
```

- [ ] **Step 3: Commit**

```bash
git add googlarr/web.py
git commit -m "feat: add per-item apply/restore API endpoints"
```

---

## Task 2: Add CSS for action buttons to `web_ui.html`

**Files:**
- Modify: `googlarr/web_ui.html`

- [ ] **Step 1: Add CSS for the action buttons**

Find the `.poster-status-prank-hover` CSS block (around line 299). Insert the following CSS block immediately after it (after the closing `}`):

```css
        .poster-item-actions {
            position: absolute;
            bottom: 28px;
            left: 0; right: 0;
            display: flex;
            justify-content: center;
            gap: 6px;
            z-index: 5;
            opacity: 0;
            transition: opacity 0.2s ease;
            padding: 0 6px;
        }

        .poster-item:hover .poster-item-actions {
            opacity: 1;
        }

        .poster-action-btn {
            font-size: 10px;
            font-weight: 700;
            padding: 3px 8px;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }

        .poster-action-btn.apply {
            background: rgba(33, 150, 243, 0.92);
            color: #fff;
        }

        .poster-action-btn.apply:hover {
            background: rgba(33, 150, 243, 1);
        }

        .poster-action-btn.restore {
            background: rgba(76, 175, 80, 0.92);
            color: #fff;
        }

        .poster-action-btn.restore:hover {
            background: rgba(76, 175, 80, 1);
        }

        .poster-action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
```

- [ ] **Step 2: Commit**

```bash
git add googlarr/web_ui.html
git commit -m "feat: add CSS for per-item action buttons"
```

---

## Task 3: Add JS handler and render buttons in poster cards

**Files:**
- Modify: `googlarr/web_ui.html`

- [ ] **Step 1: Add the `itemAction` JS function**

Find the `applyNow` function (around line 584). Insert the following function immediately before it:

```javascript
        async function itemAction(itemId, action, btn) {
            btn.disabled = true;
            const original = btn.textContent;
            btn.textContent = '...';
            try {
                const resp = await fetch(`${API_BASE}/items/${itemId}/${action}`, { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    // Update the status badge on this card
                    const card = btn.closest('.poster-item');
                    const badge = card.querySelector('.poster-status');
                    const statusConfig = {
                        'PRANK_APPLIED':   { cls: 'status-prank-live',  label: 'Live' },
                        'PRANK_GENERATED': { cls: 'status-prank-ready', label: 'Ready' },
                    };
                    const cfg = statusConfig[data.status];
                    if (cfg && badge) {
                        badge.className = `poster-status ${cfg.cls}`;
                        badge.textContent = cfg.label;
                    }
                    // Swap which button is visible
                    const actions = card.querySelector('.poster-item-actions');
                    if (actions) {
                        actions.innerHTML = '';
                        if (data.status === 'PRANK_GENERATED') {
                            actions.appendChild(makeActionBtn(itemId, 'apply', 'Apply'));
                        } else if (data.status === 'PRANK_APPLIED') {
                            actions.appendChild(makeActionBtn(itemId, 'restore', 'Restore'));
                        }
                    }
                } else {
                    btn.textContent = 'Error';
                    setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 2000);
                }
            } catch (e) {
                btn.textContent = 'Error';
                setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 2000);
            }
        }

        function makeActionBtn(itemId, action, label) {
            const btn = document.createElement('button');
            btn.className = `poster-action-btn ${action}`;
            btn.textContent = label;
            btn.onclick = (e) => { e.stopPropagation(); itemAction(itemId, action, btn); };
            return btn;
        }
```

- [ ] **Step 2: Render action buttons inside each poster card**

Find this block in the poster card rendering loop (around line 713):

```javascript
                // Hover badge (shown when viewing prank)
                if (hasPrank(item.status)) {
                    const hoverBadge = document.createElement('div');
                    hoverBadge.className = 'poster-status-prank-hover';
                    hoverBadge.textContent = 'Viewing Prank';
                    wrapper.appendChild(hoverBadge);
                }
```

Replace it with:

```javascript
                // Hover badge (shown when viewing prank)
                if (hasPrank(item.status)) {
                    const hoverBadge = document.createElement('div');
                    hoverBadge.className = 'poster-status-prank-hover';
                    hoverBadge.textContent = 'Viewing Prank';
                    wrapper.appendChild(hoverBadge);
                }

                // Per-item action buttons (Apply or Restore)
                if (item.status === 'PRANK_GENERATED' || item.status === 'PRANK_APPLIED') {
                    const actions = document.createElement('div');
                    actions.className = 'poster-item-actions';
                    if (item.status === 'PRANK_GENERATED') {
                        actions.appendChild(makeActionBtn(item.item_id, 'apply', 'Apply'));
                    } else {
                        actions.appendChild(makeActionBtn(item.item_id, 'restore', 'Restore'));
                    }
                    wrapper.appendChild(actions);
                }
```

- [ ] **Step 3: Verify the HTML is well-formed (no syntax errors)**

```bash
python -c "
from googlarr.web import app
client = app.test_client()
resp = client.get('/')
print('OK' if resp.status_code == 200 else f'ERROR {resp.status_code}')
"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add googlarr/web_ui.html
git commit -m "feat: render per-item Apply/Restore buttons in poster grid"
```

---

## Task 4: Rebuild Docker image and verify

- [ ] **Step 1: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Rebuild and restart the container**

```bash
cd /home/jeremy/GitHub/JPT62089/googlarr
./googlarr.sh rebuild
```

- [ ] **Step 3: Verify endpoints exist**

```bash
sleep 5
curl -s -X POST http://localhost:8721/api/items/INVALID_ID/apply | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('error', 'unexpected'))"
```

Expected: `Item not found`

- [ ] **Step 4: Verify web UI loads**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8721/
```

Expected: `200`
