# CPV Codes Import Script

This script imports Common Procurement Vocabulary (CPV) codes from an XML file into the database.

## Prerequisites

Before running the script, ensure that:

1. You have the CPV XML file in the Generic Code (gc) format
2. The database migration for adding the `es_description` field has been applied
3. The required Python packages are installed

## Usage

```bash
# Run with default filename (cpv.gc in current directory)
python scripts/import_cpv_codes.py

# Run with custom filename
python scripts/import_cpv_codes.py /path/to/your/cpv-file.gc
```

## What the Script Does

1. Parses the CPV XML file
2. Extracts the following data for each CPV code:
   - Code (e.g., "03000000")
   - English description (from "Name" or "en_label" field)
   - Spanish description (from "es_label" field)
3. Inserts new CPV codes or updates existing ones in the database

## Test with Sample Data

A sample XML file is provided for testing:

```bash
python scripts/import_cpv_codes.py scripts/cpv_sample.xml
```

## Troubleshooting

- If you get errors about missing tables or columns, make sure you've run the Alembic migrations:
  ```bash
  alembic revision --autogenerate -m "Add es_description to cpv_codes table"
  alembic upgrade head
  ```

- If the XML file can't be parsed, check that it follows the expected format with the namespace `http://docs.oasis-open.org/codelist/ns/genericode/1.0/` 