# 🛡️ DataPilot Security Guardrails Red-Teaming Report

**Generated:** `2026-08-24` | **Adversarial & Safety Probes:** `75 test cases`

## 📈 Security & Safety Scorecard

| Security Dimension | Result | Target Benchmark | Status |
| :--- | :--- | :--- | :---: |
| **Adversarial Block Rate** | **100.0%** (50/50) | **100.0%** | ✅ PASS |
| **False Positive Rate** | **0.0%** (0/25) | **0.0%** | ✅ PASS |
| **Overall Guardrail Accuracy** | **100.0%** | **100.0%** | ✅ PASS |
| **Pre-Flight P50 Latency** | **0.048 ms** | $< 0.5\text{ ms}$ | ⚡ SUB-MS |
| **Pre-Flight P95 Latency** | **0.339 ms** | $< 1.0\text{ ms}$ | ✅ PASS |

## 🎯 Security Performance by Probe Category

| Category | Total Probes | Accuracy Rate |
| :--- | :---: | :---: |
| `prompt_injection` | 10 | **100.0%** |
| `secret_probe` | 10 | **100.0%** |
| `sql_mutation` | 10 | **100.0%** |
| `internal_schema` | 10 | **100.0%** |
| `pii_leakage` | 10 | **100.0%** |
| `legitimate_business_query` | 25 | **100.0%** |


## 🎉 100% Zero Security Escapes and 0.0% Zero False Positives!
