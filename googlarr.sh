#!/bin/bash
set -e

# Googlarr Docker Helper Script
# Usage: ./googlarr.sh [build|run|stop|logs|shell]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="googlarr"
CONTAINER_NAME="googlarr"
PORT="8721"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}=== Googlarr ===${NC}"
}

print_error() {
    echo -e "${RED}Error: $1${NC}" >&2
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

build() {
    print_header
    print_info "Building Docker image: $IMAGE_NAME"
    docker build -t "$IMAGE_NAME:latest" "$SCRIPT_DIR"
    print_success "Image built successfully"
}

run() {
    print_header
    print_info "Starting Googlarr container..."

    # Get host timezone
    TIMEZONE=$(cat /etc/timezone 2>/dev/null || echo "UTC")

    # Check if container is already running
    if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_info "Container already running. Use 'stop' to stop it first."
        return 1
    fi

    # Run the container
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "${PORT}:8721" \
        -v "$(pwd)/config:/app/config" \
        -v "$(pwd)/data:/app/data" \
        -v /etc/localtime:/etc/localtime:ro \
        -e TZ="$TIMEZONE" \
        -e PYTHONUNBUFFERED=1 \
        --restart unless-stopped \
        "$IMAGE_NAME:latest"

    print_success "Container started"
    print_info "Web UI: http://localhost:${PORT}"
    print_info "View logs: ./googlarr.sh logs"
    print_info "Stop container: ./googlarr.sh stop"
}

run_fg() {
    print_header
    print_info "Starting Googlarr container (foreground)..."

    # Get host timezone
    TIMEZONE=$(cat /etc/timezone 2>/dev/null || echo "UTC")

    docker run --rm -it \
        --name "${CONTAINER_NAME}-fg" \
        -p "${PORT}:8721" \
        -v "$(pwd)/config:/app/config" \
        -v "$(pwd)/data:/app/data" \
        -v /etc/localtime:/etc/localtime:ro \
        -e TZ="$TIMEZONE" \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME:latest"
}

stop() {
    print_header
    if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_info "Stopping Googlarr container..."
        docker stop "$CONTAINER_NAME"
        docker rm "$CONTAINER_NAME"
        print_success "Container stopped and removed"
    else
        print_info "Container is not running"
    fi
}

logs() {
    print_header
    if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker logs -f "$CONTAINER_NAME"
    else
        print_error "Container is not running"
        return 1
    fi
}

shell() {
    print_header
    if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker exec -it "$CONTAINER_NAME" /bin/bash
    else
        print_error "Container is not running"
        return 1
    fi
}

status() {
    print_header
    if docker ps --filter "name=$CONTAINER_NAME" --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_success "Container is running"
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        print_info "Container is not running"
    fi
}

rebuild() {
    print_header
    print_info "Rebuilding and restarting..."
    stop || true
    build
    run
    print_success "Rebuild complete"
}

usage() {
    cat << EOF
${GREEN}Googlarr Docker Helper${NC}

Usage: ./googlarr.sh [command]

Commands:
    build       Build Docker image
    run         Start container in background (daemon mode)
    run-fg      Start container in foreground (for testing)
    stop        Stop and remove container
    logs        View container logs
    shell       Open bash shell in running container
    status      Check container status
    rebuild     Stop, rebuild, and restart

Examples:
    ./googlarr.sh build          # Build the image
    ./googlarr.sh run            # Start daemon
    ./googlarr.sh logs           # View logs
    ./googlarr.sh stop           # Stop daemon
    ./googlarr.sh rebuild        # Full rebuild and restart

Environment:
    Config: ./config
    Data:   ./data
    Web UI: http://localhost:8721

EOF
}

# Main
case "${1:-}" in
    build)
        build
        ;;
    run)
        run
        ;;
    run-fg)
        run_fg
        ;;
    stop)
        stop
        ;;
    logs)
        logs
        ;;
    shell)
        shell
        ;;
    status)
        status
        ;;
    rebuild)
        rebuild
        ;;
    *)
        usage
        exit 1
        ;;
esac
