# Galaxy Job Error Analysis Dashboard

Static HTML dashboard for analyzing Galaxy job failures. Generates self-contained HTML files with embedded charts that can be hosted on GitHub Pages or viewed locally.

## Quick Start

```bash
# Install dependencies
pip install pandas altair vl-convert-python

# Full pipeline: validate → sanitize → generate dashboard
./run.sh error-jobs.json

# Or just regenerate from existing sanitized data
./run.sh --generate-only
```

## Project Structure

```
├── index.html                 # Main dashboard (self-contained, ~1.5MB)
├── tools/                     # Per-tool error pages (20 files)
│   ├── featurecounts.html
│   ├── snippy.html
│   └── ...
├── data/
│   └── error-jobs-sanitized.json.gz   # Sanitized error data
├── run.sh                     # Main orchestration script
├── validate.py                # JSON structure validator
├── sanitize.py                # Data sanitization script
├── generate_dashboard.py      # Dashboard generator
└── README.md
```

## Scripts

### run.sh - Main Entry Point

```bash
./run.sh <input.json>       # Full pipeline: validate → sanitize → generate
./run.sh --generate-only    # Regenerate dashboard from existing sanitized data
./run.sh --validate <json>  # Only validate JSON structure
./run.sh --sanitize <json>  # Only sanitize JSON (output: data/error-jobs-sanitized.json.gz)
./run.sh --help             # Show help
```

### validate.py - JSON Validator

Checks that input JSON has required fields and correct structure.

```bash
python validate.py error-jobs.json          # Validate first 1000 records
python validate.py error-jobs.json --full   # Validate all records
```

Exit codes: 0 = valid, 1 = invalid

### sanitize.py - Data Sanitizer

Removes/redacts sensitive information for public sharing:
- `user_id`: hashed with SHA256
- `session_id`, `history_id`: removed
- Emails in text fields: replaced with `[EMAIL]`
- `/home/username` paths: replaced with `/home/[USER]`

```bash
python sanitize.py raw-errors.json                          # Output: data/error-jobs-sanitized.json.gz
python sanitize.py raw-errors.json custom-output.json.gz    # Custom output path
```

### generate_dashboard.py - Dashboard Generator

Generates HTML dashboard from sanitized data. Reads from `data/error-jobs-sanitized.json.gz`.

```bash
python generate_dashboard.py
```

## Generating Dashboard from New Data

### Step 1: Export Error Jobs from Galaxy

Query your Galaxy database for failed jobs:

```sql
SELECT
    id, create_time, update_time, tool_id, state, exit_code,
    tool_stderr, tool_stdout, tool_version, destination_id,
    user_id, handler, job_stderr, job_stdout
FROM job
WHERE state = 'error'
  AND create_time >= '2025-11-01'
ORDER BY create_time;
```

Export to JSON array format.

### Step 2: Run Pipeline

```bash
./run.sh error-jobs-export.json
```

This will:
1. Validate the JSON structure
2. Sanitize sensitive data
3. Generate the dashboard

Output files:
- `data/error-jobs-sanitized.json.gz` - sanitized data
- `index.html` - main dashboard
- `tools/*.html` - per-tool error pages

## Input Data Format

The validator expects a JSON file containing an array of Galaxy job records.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Job ID |
| `create_time` | string | ISO8601 timestamp (e.g., `2025-11-01T00:01:34.814058`) |
| `tool_id` | string | Full tool ID |
| `state` | string | Job state (should be `error`) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `exit_code` | int/null | Process exit code |
| `tool_stderr` | string/null | Tool's stderr output |
| `tool_stdout` | string/null | Tool's stdout output |
| `tool_version` | string | Tool version |
| `destination_id` | string/null | Compute destination |
| `user_id` | int/null | User identifier |
| `job_stderr` | string/null | Job runner stderr |
| `handler` | string | Galaxy handler |

### Example Record

```json
{
  "id": 72111776,
  "create_time": "2025-11-01T00:01:34.814058",
  "tool_id": "toolshed.g2.bx.psu.edu/repos/devteam/vcffilter/vcffilter2/1.0.0_rc3+galaxy3",
  "state": "error",
  "exit_code": 1,
  "tool_stderr": "error: no VCF header\n",
  "tool_version": "1.0.0_rc3+galaxy3",
  "destination_id": "slurm_cluster",
  "user_id": 12345
}
```

## Dependencies

```
pandas>=2.0
altair>=5.0
vl-convert-python>=1.0
```

Install: `pip install pandas altair vl-convert-python`

## Dashboard Features

### Main Dashboard (index.html)
- Summary stats (total errors, unique tools, unique users)
- Top 20 failing tools chart + table with links to detail pages
- Exit code distribution
- Error pattern categories (memory, disk, permission, etc.)
- Failures by compute destination
- Daily error trend
- Day-of-week and hour heatmaps
- Top users by error count
- Anomaly section (exit code 0 failures)

### Tool Pages (tools/*.html)
- Total errors and unique error types
- Exit code breakdown for that tool
- Destination breakdown
- Complete list of unique error messages with counts
- Expandable full stderr samples

## Customization

### Change Number of Top Tools

In `generate_dashboard.py`, modify:
```python
top20_tools = df['tool_name'].value_counts().head(20)  # Change 20 to desired number
```

### Add New Error Pattern Categories

In `generate_dashboard.py`, edit the `error_patterns` dict:
```python
error_patterns = {
    'Invalid Input': r'invalid|not valid|malformed',
    'Memory/OOM': r'memory|MemoryError|out of memory',
    'Disk Space': r'No space left|quota exceeded',
    # Add more patterns here
}
```

### Change Color Scheme

In `generate_dashboard.py`, modify CSS variables in the `CSS_STYLE` string:
```css
:root {
    --bg: #1a1a2e;
    --card-bg: #16213e;
    --accent: #4a90d9;
}
```

## Hosting on GitHub Pages

1. Push to GitHub repository
2. Go to Settings > Pages
3. Select branch and root folder
4. Access at `https://username.github.io/repo-name/`

Note: GitHub Pages for private repos requires GitHub Pro/Team/Enterprise.

## License

MIT
