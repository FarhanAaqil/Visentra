# Assurance Report Template

## VISENTRA Assurance Report
**Chain ID:** `{chain_id}`  
**Generated:** `{timestamp}`  
**Overall Score:** `{score}/100`

---

## Score Breakdown

| Component | Weight | Score | Notes |
|---|---|---|---|
| Dataset integrity | 20% | {dataset_score} | SHA-256 verified, near-duplicate check |
| Model integrity | 30% | {model_score} | Hash + arch fingerprint match |
| Backdoor screening | 25% | {backdoor_score} | Trigger-consistency test suite |
| Inference binding | 25% | {inference_score} | Input + model + config hashes bound |

---

## Findings

{findings_table}

---

## Evidence

{evidence_section}

---

## Stated Limitations

> **Important:** This report reflects the state of the pipeline at the time of the scan. It does **not** guarantee:
> - Absence of all possible backdoor triggers (only the tested trigger library was checked)
> - Protection against adversarial inputs not present in the test set
> - Guarantees beyond what SHA-256 content-addressing provides
> - Security against a privileged attacker who controls the storage layer

The backdoor screening is a **black-box, trigger-consistency test** — it is a prototype-level screening tool, not a formal proof of model safety.

---

*VISENTRA — SIH26228 — From Data to Decision, Proving AI Integrity*
