# 📊 DataPilot Executive Synthesis & LLM Judge Report

**Generated:** `2026-08-25` | **Judge Model:** `openai/gpt-oss-120b` | **Benchmark Size:** `25 test cases`

## 📈 Executive Summary Scorecard

| Evaluation Dimension | Result | Target Benchmark | Status |
| :--- | :--- | :--- | :---: |
| **Data Faithfulness (No Hallucinations)** | **99.6%** | $\ge 90.0\%$ | ✅ PASS |
| **Answer Relevancy** | **88.0%** | $\ge 85.0\%$ | ✅ PASS |
| **ChartConfig Schema Accuracy** | **100.0%** | $\ge 90.0\%$ | ✅ PASS |
| **INR Currency Formatting (₹)** | **60.0%** | $\ge 80.0\%$ | ✅ PASS |
| **Overall Synthesis Quality Index** | **95.9%** | $\ge 88.0\%$ | ✅ PASS |
| **Median (P50) Synthesis Time** | **2877.5 ms** | $< 1500\text{ ms}$ | ⚡ FAST |
| **P95 Synthesis Time** | **7037.9 ms** | $< 3000\text{ ms}$ | ⚡ FAST |

## ❌ Mismatches or Hallucinations Detected

### `[syn_07]` Draft a VIP re-engagement campaign offering 20% discount (`action_summary`)

- **Final Summary:** *"- **Campaign Title:** *VIP Customer Win‑Back Campaign* – targeting **1** VIP (Siddharth Rao) who has..."*
- **Diff Reason:** `Hallucination: ['7‑day expiry'] (The response is relevant and well-formatted, with monetary values in INR and key numbers bolded. However, it introduces a 7‑day expiry which is not present in the data, making the answer not fully faithful.)`
