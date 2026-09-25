"""
doid_merge.py
-------------
Post-processing step that collapses rows whose condition DOIDs are in an
ancestor/descendant relationship.  Runs after per-row QC is complete.
"""

import urllib.parse
import requests
from collections import defaultdict
from utils.logging import dev_logger, data_logger

_doid_cache: dict[str, set] = {}  # keyed by "doid_ancestors:<DOID:XXXX>"

_MERGE_EXCLUDE_FIELDS = {'condition', 'condition_id', 'biomarker_index', 'legacy_biomarker_id'}


def _doid_to_iri(doid_str: str) -> str:
    return "http://purl.obolibrary.org/obo/" + doid_str.replace(":", "_")


def _fetch_doid_ancestors(doid_str: str) -> set:
    """Return the set of ancestor DOID strings for doid_str via OLS4, cached."""
    if doid_str in _doid_cache:
        return _doid_cache[doid_str]

    iri = _doid_to_iri(doid_str)
    double_encoded = urllib.parse.quote(urllib.parse.quote(iri, safe=''), safe='')
    url = (
        f"https://www.ebi.ac.uk/ols4/api/ontologies/doid/terms/"
        f"{double_encoded}/ancestors?size=500"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        terms = response.json().get('_embedded', {}).get('terms', [])
        ancestors = {t['obo_id'] for t in terms if t.get('obo_id', '').startswith('DOID:')}
    except Exception as e:
        dev_logger.warning(f"Could not fetch DOID ancestors for '{doid_str}': {e}")
        ancestors = set()

    _doid_cache[doid_str] = ancestors
    return ancestors


def _is_ancestor(candidate_ancestor: str, candidate_descendant: str) -> bool:
    return candidate_ancestor in _fetch_doid_ancestors(candidate_descendant)


def merge_parent_child_condition_rows(rows: list) -> list:
    """
    Trigger condition
    -----------------
    Two rows share identical values for every field except condition and condition_id, AND one row's condition_id is an ancestor of the other's in the Disease Ontology.

    Resolution
    ----------
    Keep the more specific (child / descendant) term; drop the broader
    (parent / ancestor) term.  The child carries finer-grained biological
    meaning and semantically implies its parents.
    """
    groups: dict = defaultdict(list)
    for idx, row in enumerate(rows):
        key = tuple(
            (k, row.get(k, ''))
            for k in sorted(row.keys())
            if k not in _MERGE_EXCLUDE_FIELDS
        )
        groups[key].append(idx)

    to_drop: set = set()

    for indices in groups.values():
        if len(indices) < 2:
            continue
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                row_i, row_j = rows[indices[a]], rows[indices[b]]
                cid_i = row_i.get('condition_id', '')
                cid_j = row_j.get('condition_id', '')
                if not (cid_i.startswith('DOID:') and cid_j.startswith('DOID:')):
                    continue
                if _is_ancestor(cid_i, cid_j):
                    data_logger.warning(
                        f"DOID merge: dropping '{row_i.get('biomarker_index')}' "
                        f"({cid_i}) — subsumed by '{row_j.get('biomarker_index')}' ({cid_j})."
                    )
                    to_drop.add(indices[a])
                elif _is_ancestor(cid_j, cid_i):
                    data_logger.warning(
                        f"DOID merge: dropping '{row_j.get('biomarker_index')}' "
                        f"({cid_j}) — subsumed by '{row_i.get('biomarker_index')}' ({cid_i})."
                    )
                    to_drop.add(indices[b])

    if to_drop:
        dropped_ids = {rows[idx].get('biomarker_index') for idx in to_drop}
        dev_logger.info(
            f"DOID merge step dropped {len(to_drop)} row(s) "
            f"across {len(dropped_ids)} unique biomarker_index value(s)."
        )

    return [row for idx, row in enumerate(rows) if idx not in to_drop]
