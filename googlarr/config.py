import yaml
from croniter import croniter


def load_config(path='config/config.yml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def validate_config(config):
    """Validate config and raise ValueError if invalid."""
    # Check required server keys
    required_server_keys = ['type', 'url', 'token', 'libraries']
    if 'server' not in config:
        raise ValueError("Missing required key: 'server'")
    for key in required_server_keys:
        if key not in config['server']:
            raise ValueError(f"Missing required key: 'server.{key}'")
    valid_types = ('plex', 'emby', 'jellyfin')
    if config['server']['type'] not in valid_types:
        raise ValueError(f"'server.type' must be one of: {', '.join(valid_types)}")

    # Check required schedule keys
    required_schedule_keys = ['start', 'stop']
    if 'schedule' not in config:
        raise ValueError("Missing required key: 'schedule'")
    for key in required_schedule_keys:
        if key not in config['schedule']:
            raise ValueError(f"Missing required key: 'schedule.{key}'")

    # Validate cron expressions
    for key in required_schedule_keys:
        cron_expr = config['schedule'][key]
        if not croniter.is_valid(cron_expr):
            raise ValueError(f"Invalid cron expression: 'schedule.{key}' = '{cron_expr}'")

    # Check required paths keys
    required_paths_keys = ['originals_dir', 'prank_dir']
    if 'paths' not in config:
        raise ValueError("Missing required key: 'paths'")
    for key in required_paths_keys:
        if key not in config['paths']:
            raise ValueError(f"Missing required key: 'paths.{key}'")

    # Check database key
    if 'database' not in config:
        raise ValueError("Missing required key: 'database'")

    # Check required detection keys
    required_detection_keys = ['face_detection_confidence', 'landmark_detection_confidence', 'max_faces']
    if 'detection' not in config:
        raise ValueError("Missing required key: 'detection'")
    for key in required_detection_keys:
        if key not in config['detection']:
            raise ValueError(f"Missing required key: 'detection.{key}'")

