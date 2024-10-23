##QC Logic

import logging
import re
import json
# Setup logging configuration
logging.basicConfig(
    filename='qc_report.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
) 
def lowercase_first_word(text , row_num):
    #"""the first word of the text should be lowercase."""
    if text and text[0].isupper():
        new_text = text[0].lower() + text[1:]
        logging.warning(f"Row {row_num}: Field 'biomarker' must be corrected to '{new_text}'")
        return new_text


    return text

def format_roles(role_field , row_num):
    if ';' in role_field:
        roles= role_field.split(';')

    else:
        roles = [role_field]

    # Format each role to be lowercase and stripped of leading/trailing spaces
    formatted_roles = [role.strip().lower() for role in roles]

    if role_field != ';'.join(formatted_roles):
        logging.warning(f"Row {row_num}: Field 'best_biomarker_role' must be corrected to '{';'.join(formatted_roles)}'")

    
    return ';'.join(formatted_roles)


def lowercase_specimen_field(specimen, row_num):
    #if present, it must be lowercase
    if specimen:
        new_specimen = specimen.lower()
        if specimen != new_specimen:
            logging.warning(f" Row {row_num}: 'specimen' must be corrected to '{new_specimen}'")
            return new_specimen
        
    return specimen

def title_case_resource(evidence_source , row_num):
    if ':' in evidence_source:
        before_colon, after_colon = evidence_source.split(':', 1)
        new_resource = f"{before_colon.title()}:{after_colon.strip()}"
        if evidence_source != new_resource:
            logging.warning(f"Row {row_num}: 'evidence_source' must be corrected to '{new_resource}'")
        return new_resource
    return evidence_source

def validate_format(value, field_name, row_num):
    """Check if the value follows the 'resource:id' format."""
    pattern = r"^\w+:\w+$"  # Regex for 'resource:id' format
    if not re.match(pattern, value):
        logging.warning(
            f"Row {row_num}: Invalid format for '{field_name}'. "
            f"Found '{value}', expected 'resource:id' format."
        )

#  required fields
REQUIRED_FIELDS = [
    'biomarker_id', 'biomarker', 'assessed_biomarker_entity', 'assessed_biomarker_entity_id',
    'assessed_entity_type', 'best_biomarker_role'
]

def check_required_fields(row, row_num):
    """ all required fields must be present."""
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            logging.warning(f"Row {row_num}: Missing required field '{field}'.")

def check_conditional_logic(row, row_num):
    """Check conditional presence of exposure and condition fields."""
    exposure_present = row.get('exposure_agent') and row.get('exposure_agent_id')
    condition_present = row.get('condition') and row.get('condition_id')

    # If neither exposure fields nor condition fields are  present,we log a warning
    if not exposure_present and not condition_present:
        logging.warning(
            f"Row {row_num}: Either both 'exposure_agent' and 'exposure_agent_id' "
            f"or both 'condition' and 'condition_id' must be present."
        )

# Load terminology from JSON configuration
def load_terminology():
    """Load terminology from JSON configuration."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)['terminology']
    except json.JSONDecodeError as e:
        logging.error(f"Failed to load JSON: {e}")
        raise SystemExit("Invalid JSON format.  check 'config.json'.")
    except FileNotFoundError:
        logging.error("config.json not found.")
        raise SystemExit("Configuration file 'config.json' is missing.")

# Call the load function during setup
terminology = load_terminology()

def validate_terminology(value, field_name, row_num):
    """Checking if the value matches the allowed terminology."""
    allowed_values = terminology.get(field_name, [])
    if value not in allowed_values:
        logging.warning(
            f"Row {row_num}: Invalid value for '{field_name}'. "
            f"Found '{value}', expected one of {allowed_values}."
        )

