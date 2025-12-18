#!/bin/bash
#
# Galaxy Error Reports Dashboard Generator
#
# Usage:
#   ./run.sh <input_json>           # Full pipeline: validate → sanitize → generate
#   ./run.sh --generate-only        # Just regenerate dashboard from existing sanitized data
#   ./run.sh --validate <json>      # Only validate JSON structure
#   ./run.sh --sanitize <json>      # Only sanitize JSON
#
# Examples:
#   ./run.sh error-jobs-november.json
#   ./run.sh --generate-only
#   ./run.sh --validate my-export.json
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found. Please install Python 3.8+"
        exit 1
    fi

    # Check required Python packages
    python3 -c "import pandas" 2>/dev/null || {
        log_error "pandas not installed. Run: pip install pandas"
        exit 1
    }

    python3 -c "import altair" 2>/dev/null || {
        log_error "altair not installed. Run: pip install altair"
        exit 1
    }

    python3 -c "import vl_convert" 2>/dev/null || {
        log_error "vl-convert-python not installed. Run: pip install vl-convert-python"
        exit 1
    }

    log_info "All dependencies found"
}

validate_json() {
    local input_file="$1"
    log_info "Validating $input_file..."
    python3 validate.py "$input_file"
}

sanitize_json() {
    local input_file="$1"
    local output_file="${2:-data/error-jobs-sanitized.json.gz}"

    log_info "Sanitizing $input_file..."
    python3 sanitize.py "$input_file" "$output_file"
}

generate_dashboard() {
    log_info "Generating dashboard..."

    if [ ! -f "data/error-jobs-sanitized.json.gz" ]; then
        log_error "Sanitized data not found at data/error-jobs-sanitized.json.gz"
        log_error "Run with input JSON first: ./run.sh <input.json>"
        exit 1
    fi

    python3 generate_dashboard.py

    log_info "Dashboard generated successfully!"
    echo ""
    echo "Output files:"
    echo "  - index.html (main dashboard)"
    echo "  - tools/*.html (per-tool error pages)"
    echo ""
    echo "To view: open index.html"
}

show_usage() {
    echo "Galaxy Error Reports Dashboard Generator"
    echo ""
    echo "Usage:"
    echo "  ./run.sh <input_json>           Full pipeline: validate → sanitize → generate"
    echo "  ./run.sh --generate-only        Regenerate dashboard from existing sanitized data"
    echo "  ./run.sh --validate <json>      Only validate JSON structure"
    echo "  ./run.sh --sanitize <json>      Only sanitize JSON"
    echo "  ./run.sh --help                 Show this help"
    echo ""
    echo "Examples:"
    echo "  ./run.sh error-jobs-november.json"
    echo "  ./run.sh --generate-only"
    echo "  ./run.sh --validate my-export.json"
    echo ""
    echo "Dependencies:"
    echo "  pip install pandas altair vl-convert-python"
}

# Main
case "${1:-}" in
    --help|-h)
        show_usage
        exit 0
        ;;
    --generate-only)
        check_dependencies
        generate_dashboard
        ;;
    --validate)
        if [ -z "${2:-}" ]; then
            log_error "Please specify input JSON file"
            exit 1
        fi
        validate_json "$2"
        ;;
    --sanitize)
        if [ -z "${2:-}" ]; then
            log_error "Please specify input JSON file"
            exit 1
        fi
        sanitize_json "$2"
        ;;
    "")
        show_usage
        exit 1
        ;;
    *)
        # Full pipeline
        INPUT_FILE="$1"

        if [ ! -f "$INPUT_FILE" ]; then
            log_error "File not found: $INPUT_FILE"
            exit 1
        fi

        echo "========================================"
        echo "Galaxy Error Reports Dashboard Generator"
        echo "========================================"
        echo ""

        check_dependencies
        echo ""

        # Step 1: Validate
        echo "Step 1/3: Validating input..."
        validate_json "$INPUT_FILE"
        echo ""

        # Step 2: Sanitize
        echo "Step 2/3: Sanitizing data..."
        sanitize_json "$INPUT_FILE"
        echo ""

        # Step 3: Generate
        echo "Step 3/3: Generating dashboard..."
        generate_dashboard

        echo ""
        echo "========================================"
        echo "✓ Pipeline complete!"
        echo "========================================"
        ;;
esac
