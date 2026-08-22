import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.agents import agent_graph, run_agent_workflow
from app.llm_service import process_chat_query

print("=" * 60)
print("🧪 DATAPILOT MODULE 2: LANGGRAPH STATE MACHINE VERIFICATION")
print("=" * 60)

# 1. Inspect Compiled Graph Structure
print("\n[1] Verifying StateGraph Assembly & Nodes...")
nodes = list(agent_graph.nodes.keys())
print(f"  Registered Nodes in Graph: {nodes}")
required_nodes = ["router_node", "sql_node", "heal_node", "stats_node", "email_node", "synthesis_node"]
for req in required_nodes:
    assert req in nodes, f"Missing node: {req}"
print("  ✅ All 6 specialized nodes registered in StateGraph successfully")

# 2. Test General Conversational Routing Flow
print("\n[2] Testing General Chat Flow...")
chat_question = "Hello DataPilot, who are you and how can you help me?"
chat_state = run_agent_workflow(chat_question)

assert chat_state["intent"] == "general_chat"
assert chat_state["final_response"] is not None and len(chat_state["final_response"]) > 0
assert chat_state["sql_query"] is None, "General chat should not generate SQL"
assert len(chat_state["agent_thought_trace"]) >= 2
print(f"  Intent: {chat_state['intent']}")
print(f"  Thought Trace: {chat_state['agent_thought_trace']}")
print(f"  Response Preview: {chat_state['final_response'][:100]}...")
print("  ✅ General chat routed directly to synthesis without SQL execution")

# 3. Test Service Layer API Bridge
print("\n[3] Testing process_chat_query() API Bridge...")
api_response = process_chat_query("Hi there!")
assert api_response.response is not None
assert api_response.model is not None
print("  ✅ process_chat_query() successfully returned valid ChatResponse")

print("\n" + "=" * 60)
print("🎉 ALL MODULE 2 LANGGRAPH COMPONENTS VERIFIED SUCCESSFULLY!")
print("=" * 60)
