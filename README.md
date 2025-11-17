# LIMS-ELISA Lab Architecture

This repository organizes ELISA laboratory assets into layered components to keep validation, data integrity, and automation workstreams separated. Each top-level folder includes a README and implementation artifacts as the project grows.

## docs/qms — Quality Management Standards
- Captures SOPs, work instructions, and policies aligned with **ICH Q7**, **ISO 15189/17025**, **CLIA**, and **21 CFR Part 210/211** for regulated laboratories.
- Traceability matrix and validation plans should reference **GAMP 5** categories and risk assessments.
- Document templates can start from open-source QMS examples such as the [GxP-Ready QMS templates](https://github.com/DataReply/GxP-Ready-QMS-Templates).

## lims — Core LIMS/ELN Selection
- Houses evaluations and configurations for open-source LIMS/ELN platforms. Candidate stacks include:
  - [LabKey Server](https://www.labkey.org/) for assay data management and audit trails.
  - [SENAITE LIMS](https://www.senaite.com/) (Bika) for sample tracking and stability protocols.
  - [eLabFTW](https://www.elabftw.net/) as an ELN with electronic signatures and scheduling.
- Include URS/FRS documents mapping required features (sample lifecycle, plate maps, audit trails, role-based access) to chosen platform modules.
- Align configuration and user provisioning with **21 CFR Part 11** (unique credentials, e-signature meaning/intent, time-stamped audit trails, validated change control).

## sop-runner — SOP Execution & 21 CFR Part 11 Controls
- Workflow engine or notebook runner for executing validated SOPs with enforced steps, approvals, and electronic signatures.
- Capture metadata (operator, instrument, reagent lot) and immutable audit events per **21 CFR Part 11 Subpart B** (Sec. 11.10, 11.30, 11.50).
- Consider open-source orchestrators such as [n8n](https://n8n.io/) or [Apache Airflow](https://airflow.apache.org/) with controlled deployments and signed release baselines.
- Include validation packs: IQ/OQ/PQ scripts, controlled test evidence, and CSV/e-signature challenge tests.

## connectors — Instrument & Reader Integrations
- Drivers and parsers for plate readers and liquid handlers; normalize outputs to structured assay results.
- Example adapters:
  - [pylabrobot](https://github.com/pylabrobot/pylabrobot) for liquid handlers.
  - [py-opcua](https://github.com/FreeOpcUa/python-opcua) or [pythonnet](https://github.com/pythonnet/pythonnet) for OPC/COM-based instruments.
  - CSV/XML/JSON translators for plate reader exports (e.g., SpectraMax, BioTek, Tecan).
- Include checksum verification, instrument qualification status checks, and data provenance tags to maintain ALCOA+ attributes.

## analytics — 4PL/5PL Curve Fits & Reporting
- Pipelines for 4-parameter and 5-parameter logistic fits, limit of detection/quantitation, and plate/assay quality flags.
- Recommended libraries: [scipy](https://scipy.org/) (`curve_fit`), [statsmodels](https://www.statsmodels.org/), and [bokeh](https://bokeh.org/) or [plotly](https://plotly.com/python/) for interactive QC plots.
- Capture model parameters, residuals, and confidence intervals; store versioned analysis scripts with hash-based immutability for validation traceability.

## qc — Westgard Rules & Ongoing Monitoring
- Implement Westgard multi-rule QC (1_2s, 1_3s, 2_2s, R_4s, 4_1s, 10x) for control samples across runs.
- Track bias, precision, and drift; trigger CAPA workflows when rule violations accumulate.
- Reference open-source tools such as [westgard-python](https://github.com/yoavram/westgard) or [qccharts](https://github.com/Tarang74/qccharts) for charting and rule evaluation.

## orchestrator — End-to-End Coordination
- Coordinates SOP runner, LIMS updates, instrument connectors, and analytics pipelines with event-driven scheduling.
- Suggested open-source backbones: [Temporal](https://temporal.io/) (with Python/TypeScript SDKs) or [Prefect](https://www.prefect.io/) for resilient workflows and retries.
- Enforce segregation of duties: operators vs approvers vs administrators, with centralized logging (e.g., [OpenTelemetry](https://opentelemetry.io/)) and secure secrets management (e.g., [HashiCorp Vault](https://www.vaultproject.io/)).
- Orchestrator should expose APIs/webhooks for external systems and produce validation-ready execution records.

## Validation & Compliance Notes
- Establish a configuration management baseline with versioned releases, signed tags, and change control aligned to **ISO 13485** design controls where applicable.
- Ensure disaster recovery (backups, restore tests) and business continuity plans are documented in `docs/qms`.
- Every module should maintain a traceability matrix linking URS → FRS → test cases → executed evidence for audit readiness.
