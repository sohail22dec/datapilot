# 🩹 DataPilot Self-Healing Resilience Evaluation Report

**Generated:** `2026-08-24` | **Fault Injections:** `20 test cases`

## 📈 Executive Summary Scorecard

| Metric | Result | Benchmark Target | Status |
| :--- | :--- | :--- | :---: |
| **Overall Recovery Rate** | **100.0%** (20/20) | $\ge 80.0\%$ | ✅ PASS |
| **1-Shot Recovery Rate** | **100.0%** (20/20) | $\ge 65.0\%$ | ✅ PASS |
| **2-Shot Recovery Rate** | **0.0%** (0/20) | $\le 30.0\%$ | — |
| **Post-Heal Execution Match** | **80.0%** (16/20) | $\ge 75.0\%$ | ✅ PASS |
| **Median (P50) Healing Time** | **1306.8 ms** | $< 2000\text{ ms}$ | ⚡ FAST |
| **P95 Healing Time** | **6063.5 ms** | $< 3500\text{ ms}$ | ⚠️ WARN |

## 🎯 Resilience by Fault Category

| Fault Category | Samples | Recovered | 1-Shot | Recovery Rate |
| :--- | :---: | :---: | :---: | :---: |
| `column_hallucination` | 6 | 6 | 6 | **100.0%** |
| `table_hallucination` | 4 | 4 | 4 | **100.0%** |
| `missing_group_by` | 3 | 3 | 3 | **100.0%** |
| `type_mismatch` | 3 | 3 | 3 | **100.0%** |
| `syntax_join_predicate` | 2 | 2 | 2 | **100.0%** |
| `syntax_trailing_comma` | 1 | 1 | 1 | **100.0%** |
| `syntax_clause_order` | 1 | 1 | 1 | **100.0%** |


## 🎉 100% Self-Healing Recovery across all 20 Fault Injections!
