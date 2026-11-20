# python process_biomarkers.py --input-file ../dataset/corrected_output.tsv --dataset-name biomarkers_salivadb --output-dir ../dataset/
import os
import json
import glob
import argparse


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "biomarker_index",
    "component_index",
    "entity_index",
    "assessed_biomarker_entity",
    "assessed_biomarker_entity_id",
    "assessed_entity_type",
    "condition",
    "condition_id",
    "best_biomarker_role",
    "specimen",
    "specimen_id",
    "loinc_code",
    "evidence_source",
    "evidence",
]
IGNORE_FIELDS = {"component_group", "biomarker_id"}
EXTRA_COLS    = ["change_type_vocab", "aspect_type_vocab", "mod_type_vocab", "legacy_biomarker_id"]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Process biomarker TSV files into schema-conformant outputs enriched with "
            "controlled-vocabulary fields (change_type_vocab, aspect_type_vocab, mod_type_vocab).\n\n"
            "MODES:\n"
            "  Batch mode   – processes all (or selected) datasets listed in datasets.json.\n"
            "  Single-file  – processes one new TSV that is not yet in a release; "
            "pass --input-file, --dataset-name, and --output-dir."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Single-file / new-dataset mode ---
    new_grp = parser.add_argument_group("Single-file mode (new/external dataset)")
    new_grp.add_argument(
        "--input-file", metavar="FILE",
        help="Path to the input TSV file.  Activates single-file mode.",
    )
    new_grp.add_argument(
        "--dataset-name", metavar="NAME",
        help="Dataset name, e.g. 'biomarkers_mydata' (required with --input-file).",
    )
    new_grp.add_argument(
        "--output-dir", metavar="DIR",
        help="Directory to write the output file (required with --input-file).",
    )
    new_grp.add_argument(
        "--vocab-file", metavar="FILE",
        help=(
            "Path to a per-dataset controlled-vocabulary JSON "
            "(same format as vocabdb/<dataset>.json).  Optional."
        ),
    )

    # --- Batch mode ---
    batch_grp = parser.add_argument_group("Batch mode (existing datasets from a release)")
    batch_grp.add_argument(
        "--rel", default="3.5.1", metavar="VERSION",
        help="Release version string used to locate the release directory (default: 3.5.1).",
    )
    batch_grp.add_argument(
        "--downloads-dir",
        default="/data/shared/biomarkerdb/downloads/",
        metavar="DIR",
        help="Base downloads directory (default: /data/shared/biomarkerdb/downloads/).",
    )
    batch_grp.add_argument(
        "--release-dir", metavar="DIR",
        help=(
            "Release data directory containing 'unreviewed/biomarkers_*.tsv' and "
            "'misc/datasets.json'.  Defaults to "
            "/data/shared/biomarkerdb/releases/data/v-{rel}/."
        ),
    )
    batch_grp.add_argument(
        "--vocabdb-dir",
        default="/data/shared/biomarkerdb/vocabdb/",
        metavar="DIR",
        help="Directory containing per-dataset vocab JSON files (default: /data/shared/biomarkerdb/vocabdb/).",
    )
    batch_grp.add_argument(
        "--output-date-tag", default="2026_08_20_legacy", metavar="TAG",
        help=(
            "Subdirectory name appended under downloads/<source>/ for batch output "
            "(default: 2026_08_20_legacy)."
        ),
    )
    batch_grp.add_argument(
        "--datasets", nargs="+", metavar="DS",
        help="Specific dataset name(s) to process.  Default: all datasets in datasets.json.",
    )
    batch_grp.add_argument(
        "--ptrn-list", default="temp/ptrn_list.json", metavar="FILE",
        help="Path to pattern-list JSON (reserved for future use; default: temp/ptrn_list.json).",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Vocab loading
# ---------------------------------------------------------------------------

def load_vocab_dict(release_dir):
    """
    Build a lookup keyed by 'source|bmk_idx|cmp_idx|ent_idx|condition_id'
    from all unreviewed TSV files in the release directory.
    """
    tmp_dict = {}
    pattern  = os.path.join(release_dir, "unreviewed", "biomarkers_*.tsv")
    for in_file in glob.glob(pattern):
        source = os.path.basename(in_file).replace("biomarkers_", "").replace(".tsv", "")
        f_list = []
        with open(in_file, "r") as fh:
            for lcount, line in enumerate(fh, start=1):
                line = line.replace("assesed_biomarker_entity", "assessed_biomarker_entity")
                row  = line.replace("\n", "").replace('"', "'").split("\t")
                if lcount == 1:
                    f_list = row
                else:
                    c_vocab         = row[f_list.index("biomarker_controlled_vocab")]
                    biomarker_index = row[f_list.index("biomarker_index")]
                    component_index = row[f_list.index("component_index")]
                    entity_index    = row[f_list.index("entity_index")]
                    condition_id    = row[f_list.index("condition_id")]
                    key = "%s|%s|%s|%s|%s" % (
                        source, biomarker_index, component_index, entity_index, condition_id
                    )
                    tmp_dict[key] = c_vocab.lower()
    return tmp_dict


# ---------------------------------------------------------------------------
# Core file processor
# ---------------------------------------------------------------------------

def process_file(in_file, source, out_file, vocab_dict, cv_dict, bmkid2idx):
    """
    Read one input TSV, enrich with index columns and controlled-vocab fields,
    write enriched rows to *out_file*.

    Parameters
    ----------
    in_file     : str   – input TSV path
    source      : str   – dataset source name (e.g. 'gwas', not 'biomarkers_gwas')
    out_file    : str   – output TSV path
    vocab_dict  : dict  – release-level controlled-vocab lookup (may be empty for new datasets)
    cv_dict     : dict  – per-dataset biomarker→{change_type, aspect_type, mod_type} mapping
    bmkid2idx   : dict  – mutable shared mapping of biomarker_id → biomarker_index,
                          passed in so multiple files for the same dataset keep consistent indices
    """
    f_list, f_list_new = [], []
    ent_dict = {}
    bmk_idx  = 0
    row_list = []

    with open(in_file, "r") as fh:
        for lcount, line in enumerate(fh, start=1):
            line = line.replace("assesed_biomarker_entity", "assessed_biomarker_entity")
            row  = line.replace("\n", "").replace('"', "'").split("\t")

            # ---- header row ----
            if lcount == 1:
                f_list     = row
                f_list_new = list(REQUIRED_FIELDS)
                for f in f_list:
                    if f not in f_list_new and f not in IGNORE_FIELDS:
                        f_list_new.append(f)
                row_list.append(f_list_new + EXTRA_COLS)
                continue

            # ---- data row ----
            val_dict = {f: (row[f_list.index(f)] if f in f_list else "") for f in f_list}

            # Resolve CV entry for this biomarker string
            selected_o = {}
            biomarker  = val_dict.get("biomarker", "not_given")
            if cv_dict and biomarker in cv_dict:
                selected_o = cv_dict[biomarker]

            # ------------------------------------------------------------------
            # Assign / carry-forward biomarker / component / entity indices
            # ------------------------------------------------------------------
            if "biomarker_index" in val_dict and val_dict["biomarker_index"] != "":
                # Indices already present – keep them as-is
                pass

            elif "biomarker_id" in val_dict:
                biomarker_id = val_dict["biomarker_id"]
                entity_id    = val_dict["assessed_biomarker_entity_id"]

                if biomarker_id != "":
                    if biomarker_id not in ent_dict:
                        bmk_idx += 1
                        ent_dict[biomarker_id] = {}
                        bmkid2idx[biomarker_id] = bmk_idx
                    ent_dict[biomarker_id][entity_id] = True
                    val_dict["biomarker_index"]  = bmkid2idx[biomarker_id]
                    val_dict["component_index"]  = len(ent_dict[biomarker_id])
                    val_dict["entity_index"]     = 1

                elif "component_group" in val_dict:
                    # biomarker_id empty – fall back to component_group
                    biomarker_id = val_dict["component_group"]
                    if biomarker_id not in ent_dict:
                        ent_dict[biomarker_id] = {}
                        bmk_idx += 1
                    ent_dict[biomarker_id][entity_id] = True
                    val_dict["biomarker_index"]  = bmk_idx
                    val_dict["component_index"]  = len(ent_dict[biomarker_id])
                    val_dict["entity_index"]     = 1

            elif "component_group" in val_dict:
                biomarker_id = val_dict["component_group"]
                entity_id    = val_dict["assessed_biomarker_entity_id"]
                if biomarker_id not in ent_dict:
                    ent_dict[biomarker_id] = {}
                    bmk_idx += 1
                ent_dict[biomarker_id][entity_id] = True
                val_dict["biomarker_index"]  = bmk_idx
                val_dict["component_index"]  = len(ent_dict[biomarker_id])
                val_dict["entity_index"]     = 1

            # ------------------------------------------------------------------
            # Reconcile biomarker_controlled_vocab with release vocab_dict
            # ------------------------------------------------------------------
            key = "|".join([source] + [
                str(val_dict.get(cc, ""))
                for cc in ("biomarker_index", "component_index", "entity_index", "condition_id")
            ])
            if key in vocab_dict:
                val_dict["biomarker_controlled_vocab"] = vocab_dict[key]
            elif "biomarker_controlled_vocab" in val_dict:
                # Normalise existing value (mirrors original typo fix)
                val_dict["biomarker_controlled_vocab"] = (
                    val_dict["biomarker_controlled_vocab"]
                    .lower()
                    .replace("presense", "presence")
                )

            # ------------------------------------------------------------------
            # Build output row
            # ------------------------------------------------------------------
            newrow = [str(val_dict[f]) if f in val_dict else "" for f in f_list_new]

            # change_type_vocab / aspect_type_vocab / mod_type_vocab
            extra_row = []
            for k in ("change_type", "aspect_type", "mod_type"):
                val = selected_o.get(k) or "not_specified"
                extra_row.append(val)

            # legacy_biomarker_id
            legacy_id = val_dict.get("biomarker_id") or "no_legacy_biomarker_id"
            extra_row.append(legacy_id)

            row_list.append(newrow + extra_row)

    # Write output
    out_dir = os.path.dirname(os.path.abspath(out_file))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_file, "w") as fw:
        for row in row_list:
            fw.write("%s\n" % "\t".join(row))

    print("  wrote %d data rows → %s" % (len(row_list) - 1, out_file))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    # ======================================================================
    # Single-file / new-dataset mode
    # ======================================================================
    if args.input_file:
        if not args.dataset_name:
            raise SystemExit("Error: --dataset-name is required with --input-file.")
        if not args.output_dir:
            raise SystemExit("Error: --output-dir is required with --input-file.")
        if not os.path.isfile(args.input_file):
            raise SystemExit("Error: input file not found: %s" % args.input_file)

        ds     = args.dataset_name
        source = ds.replace("biomarkers_", "")

        cv_dict = {}
        if args.vocab_file:
            if not os.path.isfile(args.vocab_file):
                raise SystemExit("Error: vocab file not found: %s" % args.vocab_file)
            cv_dict = json.load(open(args.vocab_file))

        # New datasets have no release TSVs to pull a vocab_dict from
        vocab_dict = {}
        bmkid2idx  = {}

        out_file = os.path.join(args.output_dir, os.path.basename(args.input_file))
        print("Single-file mode: processing new dataset '%s'" % ds)
        process_file(args.input_file, source, out_file, vocab_dict, cv_dict, bmkid2idx)
        return

    # ======================================================================
    # Batch mode  (existing datasets from a release)
    # ======================================================================
    rel          = args.rel
    downloads_dir = args.downloads_dir
    release_dir  = args.release_dir or os.path.join(
        "/data/shared/biomarkerdb/releases/data", "v-%s" % rel
    )
    vocabdb_dir  = args.vocabdb_dir
    date_tag     = args.output_date_tag

    # ptrn_list reserved for future use
    ptrn_list = []
    if os.path.isfile(args.ptrn_list):
        ptrn_list = json.load(open(args.ptrn_list))

    # Maps each dataset to the date sub-directory where its source files live
    dir_map = {
        "biomarkers_cadsr":                "2026_07_21",
        "biomarkers_cgi":                  "2026_02_05",
        "biomarkers_civic":                "2026_02_05",
        "biomarkers_civic_metakb":         "2026_02_05",
        "biomarkers_clinvar":              "2026_02_05",
        "biomarkers_edrn":                 "2026_02_05",
        "biomarkers_exposure_agents":      "2026_04_16",
        "biomarkers_gwas":                 "2026_02_05",
        "biomarkers_llm_glycan":           "2026_08_20",
        "biomarkers_markerdb":             "2026_01_29",
        "biomarkers_microplastics":        "2026_04_09",
        "biomarkers_mw_loinc":             "2026_05_07",
        "biomarkers_mw_newborn_screening": "2026_05_07",
        "biomarkers_oncomx":               "2026_02_26",
        "biomarkers_opentargets":          "2026_02_05",
        "biomarkers_PMC_biomarker_sets":   "2026_02_05",
        "biomarkers_sennet":               "2026_02_05",
        "biomarkers_top_50":               "2026_02_05",
        "biomarkers_upkb_reviewed_v2":     "2026_02_26",
        "biomarkers_user_submitted":       "2026_02_26",
    }

    print("Loading release vocab from: %s" % release_dir)
    vocab_dict = load_vocab_dict(release_dir)

    datasets_json = os.path.join(release_dir, "misc", "datasets.json")
    ds_dict       = json.load(open(datasets_json))
    ds_list       = args.datasets if args.datasets else list(ds_dict["biomarkers"].keys())

    bmkid2idx = {}  # shared across all datasets in this run (preserves original behaviour)

    for ds in ds_list:
        source = ds.replace("biomarkers_", "")

        # Load per-dataset CV JSON when available
        cv_dict = {}
        cv_file = os.path.join(vocabdb_dir, "%s.json" % ds)
        if os.path.isfile(cv_file):
            cv_dict = json.load(open(cv_file))

        if ds not in dir_map:
            print("WARNING: '%s' has no entry in dir_map — skipping." % ds)
            continue

        for file_name in ds_dict["biomarkers"][ds]:
            in_file  = os.path.join(downloads_dir, source, dir_map[ds], file_name)
            out_dir  = os.path.join(downloads_dir, source, date_tag)
            out_file = os.path.join(out_dir, file_name)

            if not os.path.isfile(in_file):
                print("WARNING: input file not found, skipping: %s" % in_file)
                continue

            print("Processing %s / %s" % (ds, file_name))
            process_file(in_file, source, out_file, vocab_dict, cv_dict, bmkid2idx)


if __name__ == "__main__":
    main()
