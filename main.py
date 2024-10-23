## Entry point for the script
import logging
import csv
import json
import argparse
from collections import defaultdict
from qc_checks import (
    lowercase_first_word, format_roles, lowercase_specimen_field, title_case_resource , validate_format, check_conditional_logic, check_required_fields, validate_terminology
)
#  logging configuration
logging.basicConfig(
    filename='qc_report.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
) 

def check_id_consistency(id_records):
    '''Rows with same id must have consistent valeus'''
    fields_to_check = [
        'biomarker',
        'assessed_biomarker_entity',
        'assessed_biomarker_entity_id',
        'assessed_entity_type',
        'condition',
        'condition_id'
    ]
    for id, rows in id_records.items():
        # Use first row's values as reference
        reference = rows[0]
        for row in rows[1:]:
            for field in fields_to_check:
                if row[field] != reference[field]:
                    logging.warning(
                        f"ID {id}: Inconsistent value for '{field}'. "
                        f"Expected '{reference[field]}', found '{row[field]}'."
                    )

def normalize_row(row):
    """Normalize a row by stripping spaces and converting to lowercase."""
    return {k: (v.strip().lower() if isinstance(v, str) else v) for k, v in row.items()}

def check_duplicate_rows(seen_rows, row, row_num):
    """Flag duplicate rows."""
    normalized_row = normalize_row(row)  # Normalize the row
    row_tuple = tuple(sorted(normalized_row.items()))  # Sort and convert to tuple for comparison

    if row_tuple in seen_rows:
        logging.warning(f"Row {row_num}: Duplicate row found.")
    else:
        seen_rows.add(row_tuple)

def process_row(row, row_num, seen_rows):
    row['biomarker'] = lowercase_first_word(row.get('biomarker', ''), row_num)
    row['best_biomarker_role'] = format_roles(row.get('best_biomarker_role', ''), row_num)
    row['specimen'] = lowercase_specimen_field(row.get('specimen', ''), row_num)
    row['evidence_source'] = title_case_resource(row.get('evidence_source', ''), row_num)
    
    # Validate 'assessed_biomarker_entity_id' format
    validate_format(row.get('assessed_biomarker_entity_id', ''), 'assessed_biomarker_entity_id', row_num)

    # Validate 'condition_id' format
    validate_format(row.get('condition_id', ''), 'condition_id', row_num)

    # Check for required fields and conditional logic
    check_required_fields(row, row_num)
    check_conditional_logic(row, row_num)

# Validate terminology for below fields
    validate_terminology(row.get('best_biomarker_role', ''), 'best_biomarker_role', row_num)
    validate_terminology(row.get('assessed_entity_type', ''), 'assessed_entity_type', row_num)

    # Check for duplicate rows
    check_duplicate_rows(seen_rows, row, row_num)

def main():
    parser = argparse.ArgumentParser(description='QC Script for Biomarker Data')
    parser.add_argument('--panel', action='store_true', help='Expect panel biomarkers')
    args = parser.parse_args()
    input_file = 'dataset/oncomx.tsv' #write the correct path
    id_records = defaultdict(list)
#Initialize the set to track duplicate rows
    seen_rows = set()
    with open(input_file, mode='r') as file:
        reader = csv.DictReader(file, delimiter='\t')
        for row_num, row in enumerate(reader, start=1):
            process_row(row, row_num, seen_rows)

        #If panel biomarkers are not expected, store rows by ID for consistency check
            if not args.panel:
                id_records[row['biomarker_id']].append(row)
    if not args.panel:
        check_id_consistency(id_records)
    print("QC process completed. Check 'qc_report.log' for details.")

if __name__ == "__main__":
    main()

'''Without Panel Biomarkers (ID consistency enforced): run python main.py
With Panel Biomarkers (ID consistency check skipped): run python main.py --panel

 '''