#!/bin/bash

# Get host timezone (optional)
TIMEZONE=$(cat /etc/timezone 2>/dev/null || echo "UTC")

# Base Docker run command with mounts
CMD=(docker run --rm -it \
  -v "$(pwd)/config":/app/config \
  -v "$(pwd)/data":/app/data \
  -v /etc/localtime:/etc/localtime:ro \
  -e TZ="$TIMEZONE" \
  googlarr:latest)

# Check if arguments are passed (e.g. "regenerate 12345")
if [[ $# -gt 0 ]]; then
  # Append Python command for manual mode
  CMD+=("python" "-m" "googlarr.$1")

  # Shift "regenerate" off the args and append remaining ones
  shift
  CMD+=("$@")
fi

# Execute the composed command
"${CMD[@]}"

