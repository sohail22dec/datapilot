import os
from pathlib import Path
from app.agent.graph import agent_graph

def export_graph():
    output_path = Path("langgraph_architecture.png")
    
    try:
        # LangGraph built-in method to export graph as PNG using mermaid.ink API
        png_data = agent_graph.get_graph().draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(png_data)
        print(f"Successfully generated image using LangGraph at: {output_path.resolve()}")
    except Exception as e:
        print(f"Mermaid PNG generation failed ({e}), fallback saving Mermaid file...")
        mermaid_path = Path("langgraph_architecture.mmd")
        with open(mermaid_path, "w") as f:
            f.write(agent_graph.get_graph().draw_mermaid())
        print(f"Saved mermaid graph to: {mermaid_path.resolve()}")

if __name__ == "__main__":
    export_graph()
