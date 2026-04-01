# Design: Per-Item Apply/Restore

**Date:** 2026-04-01
**Status:** Approved

## Summary

Add per-item Apply and Restore buttons to the poster grid in the web UI. Clicking Apply on a poster immediately uploads the prank poster to Emby for that item; clicking Restore uploads the original back. Both actions update the item's DB status and refresh the card's status badge inline.

## Backend

Two new endpoints in `googlarr/web.py`:

```
POST /api/items/<item_id>/apply
POST /api/items/<item_id>/restore
```

Both endpoints:
1. Load config, call `create_server(config)` to get the adapter
2. Look up `prank_path` / `original_path` for the item from the SQLite DB
3. Call `server.upload_poster(item_id, path)`
4. Call `update_item_status(db, item_id, new_status)` — Apply sets `PRANK_APPLIED`, Restore sets `PRANK_GENERATED`
5. Return `{"success": true, "status": "<new_status>"}` or `{"success": false, "error": "..."}` with HTTP 500

Return 404 if `item_id` not found in DB. Return 400 if the item has no prank poster on disk (apply only).

## Frontend

In `web_ui.html`, the poster card hover currently shows a prank-preview badge. Add two small buttons at the bottom of the card that appear on hover:

- **Apply** — visible when item status is `PRANK_GENERATED` (prank ready but not live)
- **Restore** — visible when item status is `PRANK_APPLIED` (prank currently live)

On click:
1. Button shows a loading state (disabled + spinner text)
2. POST to the relevant endpoint
3. On success: update the card's status badge to the new status without reloading the page
4. On error: show a brief error message on the card

## Files Changed

| File | Change |
|---|---|
| `googlarr/web.py` | Add `api_item_apply` and `api_item_restore` endpoints |
| `googlarr/web_ui.html` | Add Apply/Restore hover buttons to poster cards, add JS handlers |

## Out of Scope

- Bulk per-library apply/restore (already exists as "Apply Now" / "Restore Now")
- Generating the prank poster on demand (item must already be in `PRANK_GENERATED` or `PRANK_APPLIED` state)
