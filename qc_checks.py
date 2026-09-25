##QC Logic

import re
import json
import requests
from utils.logging import dev_logger, data_logger, log_once

"""deprecated (handled downstream)
def lowercase_first_word(text, row_num):
    #the first word of the text should be lowercase.
    if text and text[0].isupper():
        new_text = text[0].lower() + text[1:]
        dev_logger.warning(f"Row {row_num}: Field 'biomarker' must be corrected to '{new_text}'")
        return new_text
    return text

def lowercase_field(value, field_name, row_num):
    if value:
        new_value = value.lower()
        if value != new_value:
            dev_logger.warning(f"Row {row_num}: '{field_name}' must be corrected to '{new_value}'")
            return new_value
    return value
"""

def load_namespace_map() -> dict:
    """Load namespace map from JSON."""
    try:
        with open('namespace_map.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        dev_logger.warning(f"Could not load namespace_map.json: {e}")
        return {}

def load_terminology():
    """Load terminology from JSON configuration."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config['terminology'], config.get('known_evidence_sources', [])
    except json.JSONDecodeError as e:
        dev_logger.error(f"Failed to load JSON: {e}")
        raise SystemExit("Invalid JSON format.  check 'config.json'.")
    except FileNotFoundError:
        dev_logger.error("config.json not found.")
        raise SystemExit("Configuration file 'config.json' is missing.")

namespace_map = load_namespace_map()
terminology, known_evidence_sources = load_terminology()

ROLE_ALIASES = {
    "susceptibility": "risk",
}
ALL_EXPECTED_HEADERS = [
    'biomarker_index', 'component_index', 'entity_index', 'biomarker', 'biomarker_controlled_vocab', 'assessed_biomarker_entity', 'assessed_biomarker_entity_id',
    'assessed_entity_type', 'best_biomarker_role', 'specimen', 'specimen_id', 'loinc_code', 'evidence_source', 'evidence',
    'condition', 'condition_id', 'exposure_agent', 'exposure_agent_id', 'tag'
]
REQUIRED_FIELDS = [
    'biomarker', 'assessed_biomarker_entity', 'assessed_biomarker_entity_id',
    'assessed_entity_type'
]
_api_cache: dict[str, str] = {}  # keyed by "resource:accession"

def format_roles(role_field, row_num):
    if ';' in role_field:
        roles = role_field.split(';')
    else:
        roles = [role_field]

    formatted_roles = []
    for role in roles:
        role = role.strip().lower()
        if role in ROLE_ALIASES:
            canonical = ROLE_ALIASES[role]
            dev_logger.warning(
                f"Row {row_num}: 'best_biomarker_role' value '{role}' "
                f"replaced with canonical term '{canonical}'"
            )
            role = canonical
        formatted_roles.append(role)

    result = ';'.join(formatted_roles)
    return result

def title_case_resource(evidence_source, row_num):
    # Bare numeric string: assume PubMed
    if evidence_source and ':' not in evidence_source and evidence_source.strip().isdigit():
        new_resource = f"PubMed:{evidence_source.strip()}"
        dev_logger.warning(f"Row {row_num}: 'evidence_source' missing resource, corrected to '{new_resource}'")
        return new_resource

    if ':' in evidence_source:
        before_colon, after_colon = evidence_source.split(':', 1)
        after_colon = after_colon.strip()  # strips whitespace after colon
        if before_colon in known_evidence_sources:
            return f"{before_colon}:{after_colon}"
        new_resource = f"{before_colon.title()}:{after_colon}"
        if evidence_source != new_resource:
            dev_logger.warning(f"Row {row_num}: 'evidence_source' must be corrected to '{new_resource}'")
        return new_resource

    return evidence_source

def validate_format(value, field_name, row_num):
    """Check if the value follows the 'resource:id' format."""
    pattern = r"^\w+:[\w-]+$" # Regex for 'resource:id' format
    if not re.match(pattern, value):
        data_logger.warning(
            f"Row {row_num}: Invalid format for '{field_name}'. "
            f"Found '{value}', expected 'resource:id' format."
        )

def check_all_headers(row, row_num):
    """Ensure all expected headers are present in the row; add missing ones as empty."""
    for header in ALL_EXPECTED_HEADERS:
        if header not in row:
            row[header] = ''
            dev_logger.warning(f"Row {row_num}: Missing header '{header}', added as empty.")

def check_required_fields(row, row_num):
    """ all required fields must be present."""
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            data_logger.warning(f"Row {row_num}: Missing required field '{field}'.")

def validate_biomarker_index(value, row_num, index_map):
    """Assign a consistent integer (1..N) to each unique biomarker_index value."""
    if value is None or value == '':
        return value
    if value not in index_map:
        index_map[value] = len(index_map) + 1
    new_value = str(index_map[value])
    if value != new_value:
        log_once(dev_logger, "'biomarker_index' values corrected from original IDs to sequential integers.")
    return new_value

def check_conditional_logic(row, row_num):
    """Check conditional presence of exposure and condition fields."""
    exposure_present = row.get('exposure_agent') and row.get('exposure_agent_id')
    condition_present = row.get('condition') and row.get('condition_id')

    # If neither exposure fields nor condition fields are  present,we log a warning
    if not exposure_present and not condition_present:
        dev_logger.warning(
            f"Row {row_num}: Either both 'exposure_agent' and 'exposure_agent_id' "
            f"or both 'condition' and 'condition_id' must be present."
        )

def check_specimen_pair(row, row_num):
    """If specimen or specimen_id is present, both must be present."""
    specimen_present = bool(row.get('specimen'))
    specimen_id_present = bool(row.get('specimen_id'))

    if specimen_present != specimen_id_present:
        missing = 'specimen_id' if specimen_present else 'specimen'
        data_logger.warning(
            f"Row {row_num}: 'specimen' and 'specimen_id' must both be present or both be absent. "
            f"Missing '{missing}'."
        )

def validate_terminology(value, field_name, row_num):
    """Checking if the value matches the allowed terminology."""
    allowed_values = terminology.get(field_name, [])
    if value not in allowed_values:
        data_logger.warning(
            f"Row {row_num}: Invalid value for '{field_name}'. "
            f"Found '{value}', expected one of {allowed_values}."
        )

def validate_specimen_name(specimen: str, specimen_id: str, row_num: int) -> str:
    if not specimen or not specimen_id or ':' not in specimen_id:
        return specimen

    resource, accession = specimen_id.split(':', 1)
    resource = resource.strip().lower()
    accession = accession.strip()

    resource_data = namespace_map.get(resource)
    if not resource_data or not resource_data.get('api_endpoint'):
        return specimen

    cache_key = f"{resource}:{accession}"
    if cache_key in _api_cache:
        recommended_name = _api_cache[cache_key]
    else:
        api_url = resource_data['api_endpoint'].replace('{id}', accession)
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            terms = response.json().get('_embedded', {}).get('terms', [])
            if not terms:
                dev_logger.warning(f"Row {row_num}: No terms found in API response for '{specimen_id}'")
                return specimen
            recommended_name = terms[0].get('label', '').lower()
            _api_cache[cache_key] = recommended_name
        except Exception as e:
            dev_logger.warning(f"Row {row_num}: Could not fetch recommended name for '{specimen_id}': {e}")
            return specimen

    if specimen != recommended_name:
        log_once(
            dev_logger,
            f"'specimen' corrected from '{specimen}' to '{recommended_name}'"
        )
        return recommended_name

    return specimen
