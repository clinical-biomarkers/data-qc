# Biomarker QC Preprocessing

This repository contains the code for preprocessing and validating biomarker data. The main objective is to ensure data quality through case normalization, duplicate detection, and format validation. The dataset used is from **OncoMX**, which provides information on cancer biomarkers.

---

## Project Overview
The QC preprocessing script performs various quality control checks on the input dataset, including:
- **Case consistency** checks for fields.
- **Validation** of biomarker roles and assessed entity types against a standard terminology.
- **Duplicate detection** across rows.
- **ID consistency checks** if panel biomarkers are not present.

---

## Folder Structure
dataset/: Folder to store your dataset. The oncomx.tsv file should be placed here.

main.py: Main script to run QC checks on the dataset.

qc_checks.py: Contains the QC functions used in the main script.

config.json: Stores terminology and other configurations.

qc_report.log: Log file that stores any issues found during QC checks.

README.md: Documentation file (this one).
