#!/usr/bin/env python3
"""
Validate Galaxy error jobs JSON file structure.
Checks required fields and data types.
"""

import json
import gzip
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    'id': (int, type(None)),
    'create_time': str,
    'tool_id': (str, type(None)),
    'state': str,
}

OPTIONAL_FIELDS = {
    'exit_code': (int, float, type(None)),
    'tool_stderr': (str, type(None)),
    'tool_stdout': (str, type(None)),
    'tool_version': (str, type(None)),
    'destination_id': (str, type(None)),
    'user_id': (int, float, type(None)),
    'job_stderr': (str, type(None)),
    'job_stdout': (str, type(None)),
    'handler': (str, type(None)),
    'update_time': (str, type(None)),
    'session_id': (int, type(None)),
    'history_id': (int, type(None)),
}

def load_json(filepath):
    """Load JSON from file (supports .json and .json.gz)"""
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if filepath.suffix == '.gz':
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

def validate_record(record, index):
    """Validate a single record, return list of errors"""
    errors = []

    if not isinstance(record, dict):
        return [f"Record {index}: not a dictionary"]

    # Check required fields
    for field, expected_types in REQUIRED_FIELDS.items():
        if field not in record:
            errors.append(f"Record {index}: missing required field '{field}'")
        elif not isinstance(record[field], expected_types):
            errors.append(f"Record {index}: field '{field}' has wrong type "
                         f"(got {type(record[field]).__name__}, expected {expected_types})")

    # Check optional fields have correct types if present
    for field, expected_types in OPTIONAL_FIELDS.items():
        if field in record and record[field] is not None:
            if not isinstance(record[field], expected_types):
                errors.append(f"Record {index}: field '{field}' has wrong type "
                             f"(got {type(record[field]).__name__})")

    # Validate create_time format (ISO8601)
    if 'create_time' in record and record['create_time']:
        ct = record['create_time']
        if not (len(ct) >= 19 and ct[4] == '-' and ct[7] == '-' and ct[10] == 'T'):
            errors.append(f"Record {index}: create_time not in ISO8601 format: {ct[:30]}")

    return errors

def validate_file(filepath, sample_size=1000, verbose=True):
    """
    Validate JSON file structure.

    Args:
        filepath: Path to JSON file
        sample_size: Number of records to fully validate (0 = all)
        verbose: Print progress

    Returns:
        (is_valid, stats, errors)
    """
    if verbose:
        print(f"Loading {filepath}...")

    try:
        data = load_json(filepath)
    except json.JSONDecodeError as e:
        return False, {}, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, {}, [f"Error loading file: {e}"]

    if not isinstance(data, list):
        return False, {}, ["JSON root must be an array of records"]

    total = len(data)
    if verbose:
        print(f"Found {total:,} records")

    errors = []
    fields_found = set()
    states_found = set()

    # Validate records
    check_count = total if sample_size == 0 else min(sample_size, total)

    for i in range(check_count):
        record = data[i]
        record_errors = validate_record(record, i)
        errors.extend(record_errors)

        if isinstance(record, dict):
            fields_found.update(record.keys())
            if 'state' in record:
                states_found.add(record['state'])

        # Stop early if too many errors
        if len(errors) > 100:
            errors.append(f"... (stopped after 100 errors)")
            break

    # Check remaining records for basic structure (just dict check)
    if sample_size > 0 and total > sample_size:
        for i in range(sample_size, total):
            if not isinstance(data[i], dict):
                errors.append(f"Record {i}: not a dictionary")
                if len(errors) > 100:
                    break

    stats = {
        'total_records': total,
        'records_validated': check_count,
        'fields_found': sorted(fields_found),
        'states_found': sorted(states_found),
        'required_fields_present': all(f in fields_found for f in REQUIRED_FIELDS),
    }

    is_valid = len(errors) == 0 and stats['required_fields_present']

    return is_valid, stats, errors

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate.py <json_file> [--full]")
        print("")
        print("Options:")
        print("  --full    Validate all records (default: first 1000)")
        print("")
        print("Example:")
        print("  python validate.py error-jobs.json")
        print("  python validate.py data/errors.json.gz --full")
        sys.exit(1)

    filepath = sys.argv[1]
    full_check = '--full' in sys.argv
    sample_size = 0 if full_check else 1000

    is_valid, stats, errors = validate_file(filepath, sample_size=sample_size)

    print("")
    print("=" * 50)
    print("VALIDATION RESULTS")
    print("=" * 50)
    print(f"File: {filepath}")
    print(f"Total records: {stats.get('total_records', 0):,}")
    print(f"Records validated: {stats.get('records_validated', 0):,}")
    print(f"Required fields present: {stats.get('required_fields_present', False)}")
    print(f"States found: {', '.join(stats.get('states_found', []))}")
    print("")
    print(f"Fields found: {', '.join(stats.get('fields_found', []))}")
    print("")

    if errors:
        print("ERRORS:")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        print("")

    if is_valid:
        print("✓ VALID - File is ready for processing")
        sys.exit(0)
    else:
        print("✗ INVALID - Please fix errors before processing")
        sys.exit(1)

if __name__ == '__main__':
    main()
