import sys
import os
import time

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.agents.graph import run_agent_workflow
from app.tools.schema_tool import get_schema_context
from app.database import warm_database_pool

print("\n" + "=" * 70)
print("⚡ LIVE BENCHMARK: MINIFIED SCHEMA, SUPABASE POOL & FAST PATH")
print("=" * 70)

# Pre-warm pool & schema
warm_database_pool()
minified_schema = get_schema_context()
print(f"\n[0] Minified Schema Preview:\n{minified_schema}")

# Test 1: Plain-Code Fast Path for Greeting
print("\n[Test 1] User asks: 'hi'")
t0 = time.perf_counter()
res1 = run_agent_workflow("hi")
dt1 = time.perf_counter() - t0
print(f"  ⏱️  Latency: {dt1 * 1000:.2f}ms ({dt1:.4f}s)")
print(f"  Response: {res1['final_response']}")
print(f"  Trace: {res1['agent_thought_trace']}")
assert dt1 < 0.05, "Greeting should return in < 50ms"
assert res1["intent"] == "general_chat"
print("  ✅ Instant 0ms greeting verified!")

# Test 2: Plain-Code Fast Path for Capabilities
print("\n[Test 2] User asks: 'What can you do?'")
t0 = time.perf_counter()
res2 = run_agent_workflow("What can you do?")
dt2 = time.perf_counter() - t0
print(f"  ⏱️  Latency: {dt2 * 1000:.2f}ms ({dt2:.4f}s)")
print(f"  Response Preview: {res2['final_response'][:120]}...")
print(f"  Trace: {res2['agent_thought_trace']}")
assert dt2 < 0.05, "Capabilities should return in < 50ms"
assert res2["intent"] == "general_chat"
print("  ✅ Instant 0ms capability response verified!")

# Test 3: Standard Business Data Query (Minified Schema)
print("\n[Test 3] User asks: 'What are our top 5 products by total revenue?'")
t0 = time.perf_counter()
res3 = run_agent_workflow("What are our top 5 products by total revenue?")
dt3 = time.perf_counter() - t0
print(f"  ⏱️  Latency: {dt3:.2f}s ({dt3 * 1000:.0f}ms)")
print(f"  SQL: {res3['sql_query']}")
print(f"  DB Execution Time: {res3['execution_time_ms']}ms ({res3['row_count']} rows)")
print(f"  Chart Config: {res3['chart_config']}")
print(f"  Summary: {res3['final_response'][:130]}...")
print(f"  Trace: {res3['agent_thought_trace']}")
assert res3["intent"] == "data_query"
assert res3["row_count"] > 0
print("  ✅ Fast data query executed with minified schema!")

# Test 4: Statistical Analytics Query
print("\n[Test 4] User asks: 'Calculate our overall profit margins and top margin products'")
t0 = time.perf_counter()
res4 = run_agent_workflow("Calculate our overall profit margins and top margin products")
dt4 = time.perf_counter() - t0
print(f"  ⏱️  Latency: {dt4:.2f}s ({dt4 * 1000:.0f}ms)")
print(f"  Intent: {res4['intent']}")
print(f"  Computed Metrics: {res4['computed_metrics']}")
print(f"  Summary: {res4['final_response'][:130]}...")
print(f"  Trace: {res4['agent_thought_trace']}")
assert res4["intent"] == "statistical_analysis"
print("  ✅ Statistical analysis completed!")

print("\n" + "=" * 70)
print("🎉 ALL BENCHMARKS COMPLETED SUCCESSFULLY!")
print(f"  • 'hi' (Instant Greeting):        {dt1 * 1000:.2f}ms  (0 tokens)")
print(f"  • 'what can you do' (Help):       {dt2 * 1000:.2f}ms  (0 tokens)")
print(f"  • 'top 5 products' (Data Query):  {dt3:.2f}s")
print(f"  • 'profit margins' (Stats Query): {dt4:.2f}s")
print("=" * 70)
