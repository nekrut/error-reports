#!/usr/bin/env python3
"""
Sanitize Galaxy error jobs JSON file for public sharing.

Removes/redacts:
- user_id: hashed with SHA256
- session_id: removed
- history_id: removed
- Emails in text fields: replaced with [EMAIL]
- /home/username paths: replaced with /home/[USER]
"""

import json
import gzip
import re
import hashlib
import sys
from pathlib import Path

# Patterns to redact
EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')
HOME_PATH_PATTERN = re.compile(r'/home/[a-zA-Z0-9_.-]+')
USER_PATH_PATTERN = re.compile(r'/users?/[a-zA-Z0-9_.-]+', re.IGNORECASE)

# Fields containing text to redact
TEXT_FIELDS = [
    'command_line',
    'tool_stderr',
    'tool_stdout',
    'job_stderr',
    'job_stdout',
    'traceback',
    'info',
]

# Fields to remove entirely
FIELDS_TO_REMOVE = [
    'session_id',
    'history_id',
]

def load_json(filepath):
    """Load JSON from file (supports .json and .json.gz)"""
    filepath = Path(filepath)

    if filepath.suffix == '.gz':
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

def save_json(data, filepath, compress=True):
    """Save JSON to file (optionally gzipped)"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if compress or filepath.suffix == '.gz':
        if not filepath.suffix == '.gz':
            filepath = Path(str(filepath) + '.gz')
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump(data, f)
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    return filepath

def hash_id(value):
    """Hash an ID to anonymize it while keeping it consistent"""
    if value is None:
        return None
    return int(hashlib.sha256(str(value).encode()).hexdigest()[:8], 16)

def redact_text(text):
    """Redact sensitive patterns from text"""
    if not text:
        return text

    text = str(text)
    text = EMAIL_PATTERN.sub('[EMAIL]', text)
    text = HOME_PATH_PATTERN.sub('/home/[USER]', text)
    text = USER_PATH_PATTERN.sub('/user/[USER]', text)

    return text

def sanitize_record(record):
    """Sanitize a single record in place"""
    # Hash user_id
    if 'user_id' in record:
        record['user_id'] = hash_id(record['user_id'])

    # Remove sensitive ID fields
    for field in FIELDS_TO_REMOVE:
        record.pop(field, None)

    # Redact text fields
    for field in TEXT_FIELDS:
        if field in record and record[field]:
            record[field] = redact_text(record[field])

    return record

def sanitize_file(input_path, output_path=None, verbose=True):
    """
    Sanitize a JSON file.

    Args:
        input_path: Path to input JSON file
        output_path: Path for output (default: data/error-jobs-sanitized.json.gz)
        verbose: Print progress

    Returns:
        output_path
    """
    input_path = Path(input_path)

    if output_path is None:
        output_path = Path('data/error-jobs-sanitized.json.gz')
    else:
        output_path = Path(output_path)

    if verbose:
        print(f"Loading {input_path}...")

    data = load_json(input_path)

    if verbose:
        print(f"Sanitizing {len(data):,} records...")

    for i, record in enumerate(data):
        sanitize_record(record)

        if verbose and (i + 1) % 25000 == 0:
            print(f"  {i + 1:,} / {len(data):,} processed")

    if verbose:
        print(f"Saving to {output_path}...")

    actual_path = save_json(data, output_path, compress=True)

    if verbose:
        size_mb = actual_path.stat().st_size / 1024 / 1024
        print(f"Done. Output: {actual_path} ({size_mb:.1f} MB)")

    return actual_path

def main():
    if len(sys.argv) < 2:
        print("Usage: python sanitize.py <input_json> [output_json]")
        print("")
        print("Sanitizes Galaxy error jobs JSON for public sharing.")
        print("")
        print("Actions performed:")
        print("  - user_id: hashed with SHA256")
        print("  - session_id, history_id: removed")
        print("  - Emails in text fields: replaced with [EMAIL]")
        print("  - /home/username paths: replaced with /home/[USER]")
        print("")
        print("Examples:")
        print("  python sanitize.py raw-errors.json")
        print("  python sanitize.py raw-errors.json data/sanitized.json.gz")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        sanitize_file(input_path, output_path)
        print("")
        print("✓ Sanitization complete")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
