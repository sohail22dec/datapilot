# 🧭 DataPilot Router Node Evaluation Report

**Generated:** `2026-08-24` | **Benchmark Size:** `40 test cases`

## 📈 Executive Summary Scorecard

| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :---: |
| **Overall Intent Accuracy** | **95.0%** (37/40) | $\ge 90.0\%$ | ✅ PASS |
| **State Contract Integrity** | **97.5%** | $\ge 95.0\%$ | ✅ PASS |
| **P50 Latency (Median)** | **2804.0 ms** | $< 1000\text{ ms}$ | ⚡ FAST |
| **P95 Latency** | **10957.1 ms** | $< 2000\text{ ms}$ | ⚠️ WARN |

## 🎯 Precision, Recall & F1 by Intent Category

| Intent | Support | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| `data_query` | 10 | 90.9% | 100.0% | **95.2%** |
| `statistical_analysis` | 8 | 100.0% | 87.5% | **93.3%** |
| `email_action` | 6 | 100.0% | 83.3% | **90.9%** |
| `general_chat` | 8 | 88.9% | 100.0% | **94.1%** |
| `policy_violation` | 8 | 100.0% | 100.0% | **100.0%** |


## ❌ Failure Analysis & Edge Cases

| ID | Category | Question | Expected | Predicted | Contract Issue |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sa_08` | `statistical_analysis` | *Calculate average order frequency and repeat purch...* | `statistical_analysis` | `data_query` | Intent Mismatch |
| `ea_04` | `email_action` | *Prepare an abandoned cart recovery email sequence ...* | `email_action` | `email_action` | Missing SQL for data/stats/email intent |
| `ea_06` | `email_action` | *Compose a seasonal promotional announcement email ...* | `email_action` | `general_chat` | Intent Mismatch |

