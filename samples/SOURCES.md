# Sample documents

The demo family ("The Parkers") uses these documents. Each one goes through the same pipeline as a
user's upload. Names, insurer names not in the documents, dates, premiums and 555-01xx phone numbers
in `demo_family.json` are made up and shown in the app as "Demo · entered by user".

| File | What it is | Source |
|---|---|---|
| `cms_sample_sbc_2025.pdf` | Sample completed Summary of Benefits and Coverage, 2025 (CMS template) | [cms.gov](https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/english-sample-completed-sbc-accessible-format-012825.pdf) — public document |
| `pinellas_county_ppo_sbc_2025.pdf` | Pinellas County (FL) employee PPO, Summary of Benefits and Coverage 2025 | [pinellas.gov](https://pinellas.gov/wp-content/uploads/2024/12/ppo-sbc-2025.pdf) — public document |
| `2025_Delta_Dental_Plan_Chart_Standard.pdf` | Delta Dental PPO (Standard) plan chart, 2025 | [hr.caltech.edu](https://hr.caltech.edu/documents/6240/2025_Delta_Dental_Plan_Chart_Standard.pdf) — public document |
| `matrix-direct-ppo-basic-py2025.pdf` | Delta Dental PPO Basic, Summary of Dental Benefits and Coverage Disclosure Matrix, 2025 | [deltadentalins.com](https://www1.deltadentalins.com/content/dam/ddins/en/pdf/hcx/2025/matrix-direct-ppo-basic-py2025.pdf) — public document |
| `homeowners-3-special-form.pdf` | ISO Homeowners 3 – Special Form (HO 00 03 04 91) | [securityfirstflorida.com](https://agents.securityfirstflorida.com/files/forms/policy-forms-and-endorsements/homeowners/ho3/homeowners-3-special-form.pdf) — public document |
| `aaa_alabama_personal_auto_policy_sample.pdf` | Alabama Personal Auto Policy, specimen marked "SAMPLE" (Automobile Club Inter-Insurance Exchange / AAA, form 138 05 2011) | [autoclubmo.aaa.com](https://services.autoclubmo.aaa.com/InsuranceAux/Forms/AL/STD/138_052011_JM.pdf) — public document |

All files were checked: each has a text layer (no scans). Only text is stored; the app masks policy
numbers, VINs and license numbers before saving, and ignores very large characters (the "SAMPLE"
watermark).

`tests/fixtures/fictional_auto_policy.pdf` is a fictional policy used only in tests (VIN and
policy-number masking); it is not part of the demo.
