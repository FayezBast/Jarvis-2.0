#!/bin/bash
# ==============================================================================
# Jarvis Container - Setup & Run Script
# ==============================================================================
# This script sets up the secure container environment and starts Jarvis
#
# Usage:
#   ./run-container.sh          # Build and start
#   ./run-container.sh stop     # Stop container
#   ./run-container.sh logs     # View logs
#   ./run-container.sh shell    # Shell into container (debug)
#   ./run-container.sh clean    # Remove container and images
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# ==============================================================================
# Pre-flight checks
# ==============================================================================
preflight_checks() {
    log_info "Running pre-flight security checks..."
    
    # Check Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed!"
        exit 1
    fi
    
    # Check docker compose is available
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available!"
        exit 1
    fi
    
    # Check .env file exists
    if [ ! -f ".env" ]; then
        log_error ".env file not found!"
        echo ""
        echo "Create .env with:"
        echo "  GEMINI_API_KEY=your_key"
        echo "  TELEGRAM_BOT_TOKEN=your_token"
        echo "  TELEGRAM_AUTHORIZED_USERS=your_user_id"
        exit 1
    fi
    
    # Check required env vars
    if ! grep -q "TELEGRAM_BOT_TOKEN" .env; then
        log_error "TELEGRAM_BOT_TOKEN not found in .env!"
        exit 1
    fi
    
    if ! grep -q "TELEGRAM_AUTHORIZED_USERS" .env; then
        log_error "TELEGRAM_AUTHORIZED_USERS not found in .env!"
        echo "Get your ID from @userinfobot on Telegram"
        exit 1
    fi
    
    if ! grep -q "GEMINI_API_KEY" .env; then
        log_error "GEMINI_API_KEY not found in .env!"
        exit 1
    fi
    
    log_success "Pre-flight checks passed"
}

# ==============================================================================
# Setup directories
# ==============================================================================
setup_directories() {
    log_info "Setting up secure directories..."
    
    # Create workspace directory (the ONLY writable area for Jarvis)
    mkdir -p jarvis_workdir
    chmod 755 jarvis_workdir
    
    # Create logs directory
    mkdir -p logs
    chmod 755 logs
    
    # Create memory file if not exists
    if [ ! -f ".agent_memory.json" ]; then
        echo "{}" > .agent_memory.json
    fi
    chmod 644 .agent_memory.json
    
    log_success "Directories ready"
}

# ==============================================================================
# Build container
# ==============================================================================
build_container() {
    log_info "Building secure container..."
    docker compose build --no-cache
    log_success "Container built"
}

# ==============================================================================
# Start container
# ==============================================================================
start_container() {
    log_info "Starting Jarvis container..."
    docker compose up -d
    
    echo ""
    log_success "Jarvis Telegram Bot is running!"
    echo ""
    echo "🔒 Security Status:"
    echo "   • Container filesystem: READ-ONLY"
    echo "   • User: non-root (UID 1000)"
    echo "   • Capabilities: ALL dropped"
    echo "   • Network: Isolated"
    echo "   • Workspace: ./jarvis_workdir only"
    echo ""
    echo "📋 Commands:"
    echo "   • View logs: ./run-container.sh logs"
    echo "   • Stop: ./run-container.sh stop"
    echo "   • Shell (debug): ./run-container.sh shell"
    echo ""
    echo "📱 Open Telegram and message your bot!"
}

# ==============================================================================
# Stop container
# ==============================================================================
stop_container() {
    log_info "Stopping Jarvis container..."
    docker compose down
    log_success "Container stopped"
}

# ==============================================================================
# View logs
# ==============================================================================
view_logs() {
    docker compose logs -f
}

# ==============================================================================
# Shell into container (for debugging)
# ==============================================================================
shell_container() {
    log_warn "Opening shell in container (debug mode)"
    docker compose exec jarvis-telegram /bin/bash || \
    docker compose run --rm jarvis-telegram /bin/bash
}

# ==============================================================================
# Clean up
# ==============================================================================
clean_up() {
    log_warn "Cleaning up containers and images..."
    docker compose down --rmi all --volumes
    log_success "Cleaned up"
}

# ==============================================================================
# Security audit
# ==============================================================================
security_audit() {
    log_info "Running security audit..."
    echo ""
    
    echo "📋 Container Security Settings:"
    docker compose config | grep -E "(read_only|user:|cap_drop|no-new-privileges)" || true
    
    echo ""
    echo "📋 Mounted Volumes:"
    docker compose config | grep -A1 "volumes:" || true
    
    echo ""
    echo "📋 Environment Variables (redacted):"
    docker compose config | grep -E "^\s+\-\s+" | sed 's/=.*/=[REDACTED]/' || true
    
    echo ""
    if docker compose ps | grep -q "jarvis-telegram"; then
        echo "📋 Running Container Info:"
        docker inspect jarvis-telegram --format='
User: {{.Config.User}}
ReadOnly: {{.HostConfig.ReadonlyRootfs}}
Privileged: {{.HostConfig.Privileged}}
CapDrop: {{.HostConfig.CapDrop}}
Memory Limit: {{.HostConfig.Memory}}
' 2>/dev/null || true
    fi
    
    log_success "Audit complete"
}

# ==============================================================================
# Main
# ==============================================================================
case "${1:-start}" in
    start|up)
        preflight_checks
        setup_directories
        build_container
        start_container
        ;;
    stop|down)
        stop_container
        ;;
    logs)
        view_logs
        ;;
    shell|sh|bash)
        shell_container
        ;;
    clean|cleanup)
        clean_up
        ;;
    build)
        preflight_checks
        build_container
        ;;
    audit|security)
        security_audit
        ;;
    restart)
        stop_container
        start_container
        ;;
    *)
        echo "Usage: $0 {start|stop|logs|shell|clean|build|audit|restart}"
        exit 1
        ;;
esac
