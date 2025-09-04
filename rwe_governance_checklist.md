# RWE Governance Checklist (v1)

Use this at **project intake** and at each **stage-gate**.

## 1) Purpose & Value
- [ ] Clear decision/use case defined (regulatory, payer, clinical, safety, HEOR)
- [ ] Target estimand(s) defined (target population, endpoint, time horizon)
- [ ] Business impact articulated (time/cost/risk, expected ROI)

## 2) Data Rights & Ethics
- [ ] Data use rights verified (license, permitted purposes, sublicensing)
- [ ] Privacy model documented (de-identified / pseudonymized / synthetic)
- [ ] Jurisdictional constraints (GDPR, HIPAA, cross-border transfers) mapped
- [ ] DUA/BAA in place and archived

## 3) Provenance & Quality
- [ ] Source provenance captured (EHR/claims/registry/wearable/API)
- [ ] Refresh frequency & latency documented
- [ ] Completeness / missingness profiled
- [ ] Plausibility & internal consistency checked
- [ ] Outlier policy & audit trail defined

## 4) Standards & Interoperability
- [ ] Conforms to OMOP/FHIR/HL7 (where applicable)
- [ ] Controlled vocabularies (SNOMED, RxNorm, LOINC) coverage assessed
- [ ] Coding maps (ICD, CPT, ATC) evaluated and versioned

## 5) Methods & Bias Control
- [ ] Confounding plan (PSM/IPTW, negative controls) documented
- [ ] Sensitivity analyses pre-specified
- [ ] Missing data strategy (MI, IPW, complete-case) defined
- [ ] Transportability considerations captured

## 6) Compliance & GxP
- [ ] Validation approach documented (requirements, test evidence)
- [ ] SOP references linked (data handling, model governance)
- [ ] Audit trail and versioning enabled

## 7) Communication & Enablement
- [ ] Stakeholders identified; training needs assessed
- [ ] Standard outputs specified (tables, figures, narratives)
- [ ] Reproducibility plan (code, containers, environments)
