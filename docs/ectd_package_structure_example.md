# eCTD Submission Package: Complete Folder Structure Example

**Example Drug:** XYZ-101 (Investigational New Drug - IND Submission)  
**Submission Type:** IND Application (Phase 1 to Phase 2)  
**Regulatory Authority:** FDA  
**Submission Date:** June 15, 2026

---

## Complete Folder Structure

```
eCTD_XYZ101_IND_20260615/
│
├── common.xml                                    # eCTD metadata (required)
├── manifest.xml                                  # File manifest (required)
├── README.txt                                    # Submission instructions
│
├── m1/                                           # MODULE 1: ADMINISTRATIVE INFORMATION
│   ├── m1_index.xml                             # Module 1 index file
│   ├── 00001_cover_letter.pdf                   # Cover letter to FDA
│   ├── 00002_form_ind_1571.pdf                  # FDA Form 1571 (IND Application)
│   ├── 00003_form_1571_attachments.pdf          # Form 1571 supporting docs
│   ├── 00004_ind_safety_report.pdf              # IND Safety Report (if applicable)
│   ├── 00005_curriculum_vitae_pi.pdf            # Principal Investigator CV
│   ├── 00006_previous_ind_history.pdf           # Prior IND submissions reference
│   ├── 00007_financial_disclosure_form.pdf      # Financial disclosure forms (FDA Form 3454/3455)
│   ├── 00008_environmental_assessment.pdf       # Environmental assessment (if required)
│   └── 00009_debarment_certification.pdf        # Debarment certification
│
├── m2/                                           # MODULE 2: SUMMARIES
│   ├── m2_index.xml                             # Module 2 index file
│   │
│   ├── m2_2_1_nonclin_overview.pdf              # Nonclinical Overview
│   │   # Summarizes all nonclinical (animal) studies
│   │   # Includes: pharmacology, toxicology, ADME findings
│   │
│   ├── m2_2_2_nonclin_summaries.pdf             # Nonclinical Study Summaries
│   │   # Executive summaries of individual nonclinical studies
│   │
│   ├── m2_2_3_clin_overview.pdf                 # Clinical Overview
│   │   # Summarizes clinical experience to date
│   │   # Includes: Phase 1 safety, PK data, preliminary efficacy
│   │
│   ├── m2_2_4_clin_summary.pdf                  # Clinical Summary
│   │   # Detailed clinical summary of Phase 1 trial(s)
│   │
│   ├── m2_3_1_quality_overall_summary.pdf       # Quality Overall Summary
│   │   # Summary of manufacturing, specifications, stability
│   │
│   ├── m2_3_2_quality_nonclin_summary.pdf       # Quality Nonclinical Summary
│   │   # Nonclinical quality aspects
│   │
│   ├── m2_3_3_quality_clin_summary.pdf          # Quality Clinical Summary
│   │   # Clinical quality aspects
│   │
│   └── m2_7_1_clinical_efficacy_summary.pdf     # Clinical Efficacy Summary (if applicable)
│
├── m3/                                           # MODULE 3: QUALITY (CMC - Chemistry, Manufacturing, Controls)
│   ├── m3_index.xml                             # Module 3 index file
│   │
│   ├── m3_2_1_drug_substance/                   # Drug Substance Information
│   │   ├── 00101_ds_nomenclature.pdf            # Nomenclature and structure
│   │   ├── 00102_ds_characterization.pdf        # Characterization
│   │   ├── 00103_ds_synthesis.pdf               # Synthesis route and process
│   │   ├── 00104_ds_specifications.pdf          # Specifications and standards
│   │   ├── 00105_ds_analytical_methods.pdf      # Analytical methods
│   │   ├── 00106_ds_stability_data.pdf          # Stability data
│   │   ├── 00107_ds_container_closure.pdf       # Container/closure system
│   │   └── 00108_ds_justification.pdf           # Justification of specifications
│   │
│   ├── m3_2_2_drug_product/                     # Drug Product Information
│   │   ├── 00201_dp_composition.pdf             # Composition and formulation
│   │   ├── 00202_dp_pharmaceutical_development.pdf # Pharmaceutical development
│   │   ├── 00203_dp_specifications.pdf          # Specifications and standards
│   │   ├── 00204_dp_analytical_methods.pdf      # Analytical methods
│   │   ├── 00205_dp_stability_data.pdf          # Stability data
│   │   ├── 00206_dp_container_closure.pdf       # Container/closure system
│   │   ├── 00207_dp_microbial_limits.pdf        # Microbial limits testing
│   │   └── 00208_dp_justification.pdf           # Justification of specifications
│   │
│   ├── m3_2_3_drug_product_manufacturing/       # Drug Product Manufacturing
│   │   ├── 00301_dp_manufacturing_process.pdf   # Manufacturing process description
│   │   ├── 00302_dp_process_validation.pdf      # Process validation studies
│   │   ├── 00303_dp_process_controls.pdf        # In-process controls
│   │   ├── 00304_dp_batch_analysis.pdf          # Batch analysis data
│   │   └── 00305_dp_manufacturing_facilities.pdf # Manufacturing facility information
│   │
│   ├── m3_2_4_drug_substance_manufacturing/     # Drug Substance Manufacturing
│   │   ├── 00401_ds_manufacturing_process.pdf   # Manufacturing process description
│   │   ├── 00402_ds_process_validation.pdf      # Process validation studies
│   │   ├── 00403_ds_process_controls.pdf        # In-process controls
│   │   ├── 00404_ds_batch_analysis.pdf          # Batch analysis data
│   │   └── 00405_ds_manufacturing_facilities.pdf # Manufacturing facility information
│   │
│   ├── m3_2_5_environmental_risk_assessment.pdf # Environmental Risk Assessment
│   │
│   └── m3_2_6_regional_information.pdf          # Regional Information (if applicable)
│
├── m4/                                           # MODULE 4: NONCLINICAL STUDY REPORTS
│   ├── m4_index.xml                             # Module 4 index file
│   │
│   ├── m4_2_1_pharmacology/                     # Pharmacology Studies
│   │   ├── 00001_pharm_primary_pharmacology.pdf # Primary pharmacology study
│   │   │   # Mechanism of action, receptor binding, in vitro studies
│   │   │
│   │   ├── 00002_pharm_secondary_pharmacology.pdf # Secondary pharmacology study
│   │   │   # Off-target effects, related mechanisms
│   │   │
│   │   └── 00003_pharm_safety_pharmacology.pdf  # Safety pharmacology study
│   │       # Cardiovascular, respiratory, CNS effects
│   │
│   ├── m4_2_2_pharmacokinetics/                 # Pharmacokinetics (PK) Studies
│   │   ├── 00101_pk_rat_iv_study.pdf            # Rat IV PK study (GLP)
│   │   │   # Absorption, distribution, metabolism, excretion
│   │   │
│   │   ├── 00102_pk_rat_oral_study.pdf          # Rat oral PK study (GLP)
│   │   │
│   │   ├── 00103_pk_dog_iv_study.pdf            # Dog IV PK study (GLP)
│   │   │
│   │   ├── 00104_pk_dog_oral_study.pdf          # Dog oral PK study (GLP)
│   │   │
│   │   └── 00105_pk_summary_report.pdf          # PK Summary Report
│   │
│   ├── m4_2_3_adme/                             # ADME (Absorption, Distribution, Metabolism, Excretion)
│   │   ├── 00201_adme_rat_study.pdf             # Rat ADME study (GLP)
│   │   │   # Radiolabeled compound, tissue distribution, excretion
│   │   │
│   │   ├── 00202_adme_dog_study.pdf             # Dog ADME study (GLP)
│   │   │
│   │   ├── 00203_adme_in_vitro_metabolism.pdf   # In vitro metabolism study
│   │   │   # Hepatic metabolism, CYP450 interactions
│   │   │
│   │   └── 00204_adme_summary_report.pdf        # ADME Summary Report
│   │
│   ├── m4_2_4_toxicology/                       # Toxicology Studies
│   │   ├── m4_2_4_1_acute_toxicity/             # Acute Toxicity
│   │   │   ├── 00301_acute_tox_rat_oral.pdf    # Acute oral toxicity (rat)
│   │   │   ├── 00302_acute_tox_rat_iv.pdf      # Acute IV toxicity (rat)
│   │   │   └── 00303_acute_tox_summary.pdf     # Acute toxicity summary
│   │   │
│   │   ├── m4_2_4_2_repeat_dose_toxicity/      # Repeat Dose Toxicity
│   │   │   ├── 00401_repeat_dose_rat_28day.pdf # 28-day rat study (GLP)
│   │   │   │   # Dose range finding, target organ identification
│   │   │   │
│   │   │   ├── 00402_repeat_dose_rat_90day.pdf # 90-day rat study (GLP)
│   │   │   │   # Main toxicology study, NOAEL determination
│   │   │   │
│   │   │   ├── 00403_repeat_dose_dog_28day.pdf # 28-day dog study (GLP)
│   │   │   │
│   │   │   ├── 00404_repeat_dose_dog_90day.pdf # 90-day dog study (GLP)
│   │   │   │
│   │   │   └── 00405_repeat_dose_summary.pdf   # Repeat dose toxicity summary
│   │   │
│   │   ├── m4_2_4_3_genetic_toxicity/          # Genetic Toxicity (Genotoxicity)
│   │   │   ├── 00501_geno_bacterial_mutation.pdf # Bacterial reverse mutation (Ames)
│   │   │   ├── 00502_geno_mammalian_mutation.pdf # Mammalian cell mutation assay
│   │   │   ├── 00503_geno_micronucleus.pdf     # Micronucleus assay
│   │   │   └── 00504_geno_summary.pdf          # Genotoxicity summary
│   │   │
│   │   ├── m4_2_4_4_reproductive_toxicity/     # Reproductive Toxicity
│   │   │   ├── 00601_repro_fertility_study.pdf # Fertility and early embryonic development
│   │   │   ├── 00602_repro_dev_toxicity.pdf    # Developmental toxicity study
│   │   │   ├── 00603_repro_lactation_study.pdf # Effects on lactation
│   │   │   └── 00604_repro_summary.pdf         # Reproductive toxicity summary
│   │   │
│   │   ├── m4_2_4_5_juvenile_toxicity/         # Juvenile Toxicity (if applicable)
│   │   │   ├── 00701_juv_tox_rat_study.pdf     # Juvenile rat toxicity study
│   │   │   └── 00702_juv_tox_summary.pdf       # Juvenile toxicity summary
│   │   │
│   │   ├── m4_2_4_6_local_tolerance/           # Local Tolerance
│   │   │   └── 00801_local_tolerance_study.pdf # Local tolerance study (if applicable)
│   │   │
│   │   ├── m4_2_4_7_other_toxicity/            # Other Toxicity Studies
│   │   │   ├── 00901_immunotoxicity_study.pdf  # Immunotoxicity study
│   │   │   ├── 00902_phototoxicity_study.pdf   # Phototoxicity study
│   │   │   └── 00903_other_tox_summary.pdf     # Other toxicity summary
│   │   │
│   │   └── m4_2_4_overall_summary.pdf           # Overall Toxicology Summary
│   │
│   └── m4_2_5_exogenous_toxicology/             # Exogenous Toxicology (if applicable)
│       └── 00951_exo_tox_study.pdf              # Exogenous toxicology study
│
├── m5/                                           # MODULE 5: CLINICAL STUDY REPORTS
│   ├── m5_index.xml                             # Module 5 index file (typically empty for IND)
│   │
│   ├── m5_3_1_clinical_study_reports/           # Clinical Study Reports
│   │   ├── 00001_csr_xyz101_101_phase1.pdf      # Phase 1 Clinical Study Report
│   │   │   # Detailed CSR from first-in-human trial
│   │   │
│   │   └── 00002_csr_summary.pdf                # Clinical Study Summary
│   │
│   └── m5_3_2_literature_references.pdf         # Literature References (if applicable)
│
└── regional/                                     # REGIONAL-SPECIFIC INFORMATION (FDA M1)
    ├── regional_index.xml                       # Regional index file
    ├── 00001_fda_form_1571_original.pdf         # Original FDA Form 1571 (signed)
    ├── 00002_fda_form_1572.pdf                  # FDA Form 1572 (IND Protocol)
    ├── 00003_protocol_xyz101_101.pdf            # Detailed protocol for Phase 1 trial
    ├── 00004_protocol_amendments.pdf            # Protocol amendments (if any)
    ├── 00005_ib_xyz101_v3.pdf                   # Investigator's Brochure (IB)
    ├── 00006_safety_update.pdf                  # Safety update report
    ├── 00007_chemistry_manufacturing.pdf        # Chemistry/Manufacturing information
    ├── 00008_pharmacology_toxicology.pdf        # Pharmacology and Toxicology summary
    ├── 00009_previous_human_experience.pdf      # Previous human experience (if any)
    ├── 00010_foreign_regulatory_status.pdf      # Foreign regulatory status
    ├── 00011_debarment_certification.pdf        # Debarment certification
    ├── 00012_financial_disclosure.pdf           # Financial disclosure
    └── 00013_environmental_assessment.pdf       # Environmental assessment (if required)
```

---

## File Naming Convention Explained

### FDA eCTD Naming Rules:

**Format:** `{SEQUENCE}_{TYPE}_{DESCRIPTION}.{EXTENSION}`

**Examples:**
- `00001_cover_letter.pdf` → Sequence 1, cover letter
- `00002_form_ind_1571.pdf` → Sequence 2, FDA Form 1571
- `00101_pk_rat_iv_study.pdf` → Sequence 101, PK rat IV study
- `00401_repeat_dose_rat_28day.pdf` → Sequence 401, 28-day rat repeat dose study

**Rules:**
1. Sequence numbers: 5 digits, zero-padded (00001, 00002, etc.)
2. Type codes: Descriptive abbreviation (cover, form, pk, tox, etc.)
3. Description: Brief file description
4. Extension: .pdf, .xml, .txt, .csv (no spaces in filenames)
5. No special characters except underscores
6. Unique sequence number per file (no duplicates)

---

## Module Breakdown & Content

### **Module 1: Administrative Information**
- Cover letter and application forms
- FDA Form 1571 (IND Application)
- Financial disclosures
- Environmental assessment
- Debarment certification
- **Typical size:** 5-10 files

### **Module 2: Summaries**
- Nonclinical overview & summaries
- Clinical overview & summaries
- Quality overall summary
- **Typical size:** 5-8 files

### **Module 3: Quality (CMC)**
- Drug substance information (synthesis, specs, stability)
- Drug product information (formulation, specs, stability)
- Manufacturing process & validation
- Analytical methods
- **Typical size:** 15-25 files

### **Module 4: Nonclinical Study Reports**
- Pharmacology studies (primary, secondary, safety pharmacology)
- PK/ADME studies (rat, dog, in vitro)
- Toxicology studies (acute, repeat-dose, genotoxicity, reproductive)
- **Typical size:** 20-40 files

### **Module 5: Clinical Study Reports**
- Clinical Study Reports (CSRs)
- Clinical summaries
- Literature references
- **Note:** For IND submissions, Module 5 is typically minimal or empty
- **Typical size:** 1-5 files

### **Regional (FDA M1)**
- FDA-specific forms and protocols
- Investigator's Brochure
- Protocol details
- Safety updates
- **Typical size:** 10-15 files

---

## XML Backbone Files Explained

### **common.xml** (Required)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<eCTD xmlns="http://www.fda.gov/eCTD">
  <submissionType>IND</submissionType>
  <submissionNumber>2026-001</submissionNumber>
  <submissionDate>2026-06-15</submissionDate>
  <sponsor>Example Pharma Inc.</sponsor>
  <drug>
    <name>XYZ-101</name>
    <indication>Advanced NSCLC</indication>
  </drug>
</eCTD>
```

### **m1_index.xml** (Module 1 Index)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<module name="M1" type="Administrative">
  <document sequence="00001" type="cover_letter">
    <file>00001_cover_letter.pdf</file>
    <title>Cover Letter</title>
  </document>
  <document sequence="00002" type="form_ind_1571">
    <file>00002_form_ind_1571.pdf</file>
    <title>FDA Form 1571</title>
  </document>
</module>
```

### **manifest.xml** (File Manifest)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <file path="m1/00001_cover_letter.pdf" checksum="abc123"/>
  <file path="m1/00002_form_ind_1571.pdf" checksum="def456"/>
  <file path="m3/m3_2_1_drug_substance/00101_ds_nomenclature.pdf" checksum="ghi789"/>
  <!-- All files listed -->
</manifest>
```

---

## Key Points for Your eCTD Agent

### **Validation Rules:**
1. ✓ All files referenced in XML must exist in folder structure
2. ✓ No orphaned files (all files must be referenced in XML)
3. ✓ Sequence numbers must be unique
4. ✓ File names must follow FDA naming convention
5. ✓ All XML files must be well-formed
6. ✓ Total package size typically 1-5 GB
7. ✓ No corrupted PDFs or missing pages

### **Common Errors to Catch:**
- ✗ Duplicate sequence numbers
- ✗ Files not referenced in XML
- ✗ Incorrect folder hierarchy
- ✗ Missing required modules
- ✗ Malformed XML files
- ✗ File names with spaces or special characters
- ✗ Missing common.xml or manifest.xml

### **Completeness Checklist for IND:**
- [ ] Module 1: Administrative (≥5 files)
- [ ] Module 2: Summaries (≥5 files)
- [ ] Module 3: CMC (≥15 files)
- [ ] Module 4: Nonclinical (≥20 files)
- [ ] Module 5: Clinical (1-5 files)
- [ ] Regional: FDA M1 (≥10 files)
- [ ] common.xml present
- [ ] manifest.xml present
- [ ] All XML files valid
- [ ] No duplicate sequence numbers
- [ ] All cross-references resolvable

---

## Example: Minimal IND Submission

For a **minimal IND submission**, you'd need at least:

```
eCTD_XYZ101_IND_MINIMAL/
├── common.xml
├── manifest.xml
├── m1/
│   ├── m1_index.xml
│   ├── 00001_cover_letter.pdf
│   ├── 00002_form_ind_1571.pdf
│   ├── 00003_form_1572.pdf
│   └── 00004_ib.pdf
├── m2/
│   ├── m2_index.xml
│   ├── m2_2_1_nonclin_overview.pdf
│   ├── m2_2_3_clin_overview.pdf
│   └── m2_3_1_quality_summary.pdf
├── m3/
│   ├── m3_index.xml
│   ├── m3_2_1_drug_substance/
│   │   └── 00101_ds_specifications.pdf
│   └── m3_2_2_drug_product/
│       └── 00201_dp_specifications.pdf
├── m4/
│   ├── m4_index.xml
│   ├── m4_2_2_pharmacokinetics/
│   │   └── 00101_pk_rat_study.pdf
│   └── m4_2_4_toxicology/
│       ├── m4_2_4_2_repeat_dose_toxicity/
│       │   └── 00401_repeat_dose_rat_90day.pdf
│       └── m4_2_4_3_genetic_toxicity/
│           └── 00501_geno_bacterial_mutation.pdf
└── regional/
    ├── regional_index.xml
    ├── 00001_protocol.pdf
    └── 00002_safety_update.pdf
```

This minimal structure contains ~20 files but covers all required modules.

---

## Notes for Implementation

1. **Folder names** should match exactly (m1, m2, m3, m4, m5, regional)
2. **File names** must be unique within the entire package
3. **Sequence numbers** should increment logically (not required to be sequential, but helps organization)
4. **XML files** must be UTF-8 encoded
5. **PDFs** should be searchable (not scanned images)
6. **Total size** should not exceed 10 GB (FDA limit)
7. **Compression** is optional but recommended (ZIP format acceptable)

