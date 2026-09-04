##QC Logic

import logging
import re
import json
# Setup logging configuration
dev_logger = logging.getLogger('dev')
data_logger = logging.getLogger('data_qc')

def lowercase_first_word(text, row_num):
    #"""the first word of the text should be lowercase."""
    if text and text[0].isupper():
        new_text = text[0].lower() + text[1:]
        logging.getLogger('dev').warning(f"Row {row_num}: Field 'biomarker' must be corrected to '{new_text}'")
        return new_text


    return text

def format_roles(role_field, row_num):
    if ';' in role_field:
        roles= role_field.split(';')

    else:
        roles = [role_field]

    # Format each role to be lowercase and stripped of leading/trailing spaces
    formatted_roles = [role.strip().lower() for role in roles]

    if role_field != ';'.join(formatted_roles):
        logging.getLogger('dev').warning(f"Row {row_num}: Field 'best_biomarker_role' must be corrected to '{';'.join(formatted_roles)}'")

    
    return ';'.join(formatted_roles)

def lowercase_field(value, field_name, row_num):
    if value:
        new_value = value.lower()
        if value != new_value:
            logging.getLogger('dev').warning(f"Row {row_num}: '{field_name}' must be corrected to '{new_value}'")
            return new_value
    return value

def title_case_resource(evidence_source, row_num):
    # Bare numeric string: assume PubMed
    if evidence_source and ':' not in evidence_source and evidence_source.strip().isdigit():
        new_resource = f"PubMed:{evidence_source.strip()}"
        logging.getLogger('dev').warning(f"Row {row_num}: 'evidence_source' missing resource, corrected to '{new_resource}'")
        return new_resource

    if ':' in evidence_source:
        before_colon, after_colon = evidence_source.split(':', 1)
        after_colon = after_colon.strip()  # strips whitespace after colon
        if before_colon in known_evidence_sources:
            return f"{before_colon}:{after_colon}"
        new_resource = f"{before_colon.title()}:{after_colon}"
        if evidence_source != new_resource:
            logging.getLogger('dev').warning(f"Row {row_num}: 'evidence_source' must be corrected to '{new_resource}'")
        return new_resource

    return evidence_source

def validate_format(value, field_name, row_num):
    """Check if the value follows the 'resource:id' format."""
    pattern = r"^\w+:[\w-]+$" # Regex for 'resource:id' format
    if not re.match(pattern, value):
        logging.getLogger('data_qc').warning(
            f"Row {row_num}: Invalid format for '{field_name}'. "
            f"Found '{value}', expected 'resource:id' format."
        )

#  required headers
ALL_EXPECTED_HEADERS = [
    'biomarker_index', 'component_index', 'entity_index', 'biomarker', 'biomarker_controlled_vocab', 'assessed_biomarker_entity', 'assessed_biomarker_entity_id',
    'assessed_entity_type', 'best_biomarker_role', 'specimen', 'specimen_id', 'loinc_code', 'evidence_source', 'evidence',
    'condition', 'condition_id', 'exposure_agent', 'exposure_agent_id', 'tag', 'change_type_vocab', 'aspect_type_vocab', 'mod_type_vocab'
]

def check_all_headers(row, row_num):
    """Ensure all expected headers are present in the row; add missing ones as empty."""
    for header in ALL_EXPECTED_HEADERS:
        if header not in row:
            row[header] = ''
            logging.getLogger('dev').warning(f"Row {row_num}: Missing header '{header}', added as empty.")

#  required fields
REQUIRED_FIELDS = [
    'biomarker', 'assessed_biomarker_entity', 'assessed_biomarker_entity_id',
    'assessed_entity_type'
]

def check_required_fields(row, row_num):
    """ all required fields must be present."""
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            logging.getLogger('data_qc').warning(f"Row {row_num}: Missing required field '{field}'.")

def validate_biomarker_index(value, row_num):
    """Check if biomarker_index is a valid integer."""
    if value is not None and value != '':
        try:
            int(value)
        except (ValueError, TypeError):
            logging.getLogger('data_qc').warning(
                f"Row {row_num}: Invalid value for 'biomarker_index'. "
                f"Found '{value}', expected an integer."
            )

def check_conditional_logic(row, row_num):
    """Check conditional presence of exposure and condition fields."""
    exposure_present = row.get('exposure_agent') and row.get('exposure_agent_id')
    condition_present = row.get('condition') and row.get('condition_id')

    # If neither exposure fields nor condition fields are  present,we log a warning
    if not exposure_present and not condition_present:
        logging.getLogger('dev').warning(
            f"Row {row_num}: Either both 'exposure_agent' and 'exposure_agent_id' "
            f"or both 'condition' and 'condition_id' must be present."
        )

# Load terminology and known_evidence_sources from JSON configuration
def load_terminology():
    """Load terminology from JSON configuration."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config['terminology'], config.get('known_evidence_sources', [])
    except json.JSONDecodeError as e:
        logging.error(f"Failed to load JSON: {e}")
        raise SystemExit("Invalid JSON format.  check 'config.json'.")
    except FileNotFoundError:
        logging.error("config.json not found.")
        raise SystemExit("Configuration file 'config.json' is missing.")

# Call the load function during setup
terminology, known_evidence_sources = load_terminology()

def validate_terminology(value, field_name, row_num):
    """Checking if the value matches the allowed terminology."""
    allowed_values = terminology.get(field_name, [])
    if value not in allowed_values:
        logging.getLogger('data_qc').warning(
            f"Row {row_num}: Invalid value for '{field_name}'. "
            f"Found '{value}', expected one of {allowed_values}."
        )

