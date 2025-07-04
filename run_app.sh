#!/bin/bash

# ==============================================================================
# Comprehensive Utility Script for the EDI Lens Project
#
# Author: Your Name
# Version: 1.1.0
#
# Description:
# This script provides a simple command-line interface to manage the
# Docker-based development environment for the EDI Lens application,
# including the database, backend, and frontend services.
# ==============================================================================

# --- Configuration ---
# Color definitions for better readability
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper Functions ---
# Prints an informational message
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Prints a success message
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Prints a warning message
warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Prints an error message and exits
error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

# Checks if a required command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "'$1' command not found. Please install it to continue."
    fi
}

# Checks if required files exist before running commands
check_files() {
    if [ ! -f "docker-compose.yml" ]; then
        error "docker-compose.yml not found. Please run this script from the project root."
    fi
    if [ ! -f ".env" ]; then
        error ".env file not found. Please create it from the template."
    fi
}

# --- Main Functions ---
# Displays the help message
usage() {
    echo "EDI Lens Project Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  dev                 Start all services in watch mode (foreground). You will see live logs."
    echo "  start               Start all services in the background (detached). (Default)"
    echo "  stop                Stop and remove all running services."
    echo "  down                Alias for 'stop'."
    echo "  logs [service]      Follow logs for all services or a specific one (e.g., backend, frontend)."
    echo "  build [service]     Force a rebuild of all images or a specific service image."
    echo "  status              Show the status of running containers."
    echo ""
    echo "Service-specific Commands:"
    echo "  start:db            Start only the database service."
    echo "  start:backend       Start only the backend service (and its db dependency)."
    echo "  start:frontend      Start only the frontend service (and its backend dependency)."
    echo ""
    echo "Maintenance Commands:"
    echo "  clean               Stop all services AND permanently delete the database volume."
    echo "  clean:start         Run 'clean' and then 'start' for a fresh environment."
    echo "  standalone:backend  Start the DB and provide instructions to run the backend locally."
    echo "  test:backend        Run the backend tests using pytest."
    echo "  test:frontend       Run the frontend tests."
    echo ""
    echo "  -h, --help          Display this help message."
    echo ""
}

# Starts all services in foreground/watch mode
start_dev() {
    info "Starting all services in DEV (watch) mode..."
    info "Logs will be displayed in this terminal. Press Ctrl+C to stop."
    docker-compose up --build
}

# Starts all services in detached mode
start_all() {
    info "Starting all services (db, backend, frontend) in the background..."
    docker-compose up --build -d
    success "All services are starting up. Use './run_app.sh status' to check."
}

# Stops and removes all services
stop_app() {
    info "Stopping and removing all services..."
    docker-compose down
    success "All services have been stopped."
}

# Shows logs, optionally for a specific service
show_logs() {
    info "Following logs... (Press Ctrl+C to stop)"
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Builds images, optionally for a specific service
build_images() {
    info "Building images..."
    if [ -n "$1" ]; then
        docker-compose build "$1"
    else
        docker-compose build
    fi
    success "Image build complete."
}

# Deletes the database data for a clean start
clean_db() {
    warn "This will permanently delete the local database data in './postgres-data'."
    read -p "Are you sure you want to continue? (y/N): " -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Stopping services before cleaning..."
        stop_app
        info "Deleting database directory './postgres-data'..."
        rm -rf ./postgres-data
        success "Database cleaned successfully."
    else
        info "Clean operation cancelled."
        exit 0
    fi
}

# Runs the backend standalone
run_backend_standalone() {
    info "Starting database service for standalone backend..."
    docker-compose up -d db
    
    warn "To run the backend standalone, please do the following in another terminal:"
    echo "  1. In the '.env' file, change POSTGRES_SERVER from 'db' to 'localhost'."
    echo "  2. Navigate to the backend folder: cd backend"
    echo "  3. Run the server: poetry run uvicorn src.main:app --reload"
    echo ""
    info "Remember to change POSTGRES_SERVER back to 'db' before running the full stack again."
}

# Runs backend tests
run_backend_tests() {
    info "Running backend tests..."
    # We combine two solutions:
    # 1. The docker-compose.yml volume exclusion ensures /app/.venv exists.
    # 2. This command bypasses any entrypoint/PATH issues by calling pytest directly.
    #
    # The '--entrypoint ""' flag overrides the Dockerfile's entrypoint.
    # Then we provide the full command with the absolute path to pytest.
    docker-compose run --rm --entrypoint "" backend /app/.venv/bin/pytest
}

# Runs frontend tests
run_frontend_tests() {
    info "Running frontend tests..."
    docker-compose run --rm frontend npm test
    # The exit code of npm test will be the exit code of the script
}

# --- Script Execution ---
# Preamble checks
check_command "docker"
check_command "docker-compose"
check_files

# Main command dispatcher
COMMAND=$1
SERVICE=$2

case "$COMMAND" in
    dev)
        start_dev
        ;;
    start)
        start_all
        ;;
    stop|down)
        stop_app
        ;;
    logs)
        show_logs "$SERVICE"
        ;;
    build)
        build_images "$SERVICE"
        ;;
    status)
        docker-compose ps
        ;;
    start:db)
        info "Starting database service..."
        docker-compose up -d db
        success "Database service started."
        ;;
    start:backend)
        info "Starting backend service (and dependencies)..."
        docker-compose up --build -d backend
        success "Backend service started."
        ;;
    start:frontend)
        info "Starting frontend service (and dependencies)..."
        docker-compose up --build -d frontend
        success "Frontend service started."
        ;;
    clean)
        clean_db
        ;;
    clean:start)
        clean_db
        start_all
        ;;
    standalone:backend)
        run_backend_standalone
        ;;
    test:backend)
        run_backend_tests
        ;;
    test:frontend)
        run_frontend_tests
        ;;
    -h|--help)
        usage
        ;;
    "") # No command given, default action
        info "No command specified. Defaulting to 'start'."
        start_all
        ;;
    *) # Invalid command
        error "Invalid command: '$COMMAND'\nRun './run_app.sh --help' to see available commands."
        ;;
esac