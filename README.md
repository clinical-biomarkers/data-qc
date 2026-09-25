# Biomarker QC Preprocessing

This repository contains the code for preprocessing and validating biomarker data. The main objective is to ensure data quality through case normalization, duplicate detection, and format validation. The dataset used is from **OncoMX**, which provides information on cancer biomarkers.

---

## Project Overview
The QC preprocessing script performs various quality control checks on the input dataset, including:
- **Case consistency** checks for fields.
- **Validation** of biomarker roles and assessed entity types against a standard terminology.
- **Duplicate detection** across rows.
- **ID consistency checks** if panel biomarkers are not present.
- **DOID merge** — collapses rows that represent the same biomarker finding annotated against a disease and one of its subtypes, keeping the more specific (child/descendant) term and dropping the broader (parent/ancestor) term.
---

## Folder Structure
dataset/: Folder to store your dataset. The oncomx.tsv file should be placed here.

main.py: Main script to run QC checks on the dataset.

qc_checks.py: Contains the QC functions used in the main script.

doid_merge.py: Post-processing step that detects and removes redundant condition rows using the Disease Ontology hierarchy. Runs after per-row QC is complete. Caches OLS4 API responses to doid_cache.json to speed up subsequent runs.

doid_cache.json: Auto-generated cache of DOID ancestor lookups. Safe to delete if you want to force a fresh fetch from OLS4.

config.json: Stores terminology and other configurations.

dev_debug.log and report.log: Log files that stores issues found during QC checks.

README.md: Documentation file (this one).
