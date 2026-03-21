"""ReACT-pattern ReportAgent for post-simulation synthesis.
Equivalent to MiroFish's report_agent.py — iteratively uses tools to query
the knowledge graph, interview agents, and synthesize findings."""

import json
import time
from app.services import llm_client
from app.models.schemas import SimulationSession, Platform, SimPost


# ═══════════════════════════════════════════════
# TOOLS available to the ReportAgent
# ═══════════════════════════════════════════════

TOOL_DEFINITIONS = """You have access to these tools. To use one, respond with:
TOOL: tool_name
INPUT: your input

Available tools:

1. search_graph(query) — Search the knowledge graph for entities matching a query
2. get_entity(name) — Get full details + relationships for a specific entity
3. get_posts_by_agent(agent_name) — Get all posts by a specific agent
4. get_posts_by_action(action) — Get posts filtered by action type (post, disagree, synthesize, etc.)
5. get_platform_summary(platform) — Summarize activity on critics_forum or inworld_forum
6. interview_agent(agent_name, question) — Ask a simulated agent a question about their reasoning
7. get_opinion_shifts() — Get opinion drift data across all agents
8. get_relationship_map() — Get inter-agent relationship sentiments
9. write_section(title, content) — Write a section of the report
10. finalize_report() — Compile all sections into the final report

After using a tool, you'll see the result. Then decide your next action.
When you have enough information, use write_section for each part, then finalize_report."""


REACT_SYSTEM = """You are the ReportAgent — a master literary analyst synthesizing a multi-agent 
swarm simulation about a novel. You follow the ReACT pattern: Reason about what info you need,
Act by calling a tool, Observe the result, then Reason again.

Your goal: produce a comprehensive {mode} report that captures the best ideas from the swarm.

For LORE ENHANCEMENT mode, your report should include:
- Executive Summary: Key discoveries from the swarm
- World Mechanics: Magic systems, natural laws, technology
- Geography & Politics: Places, factions, power structures
- Characters: Deepened arcs, motivations, relationships
- History & Timeline: Key events, cause and effect
- Themes & Symbolism: What the story is really about
- Unresolved Questions: Contradictions or gaps to explore

For OUTLINE GENERATION mode, your report should include:
- Story Structure: Overall arc, act breaks
- Chapter-by-Chapter Outline: Title, events, character beats, thematic threads
- Character Arcs: Per-character progression across chapters
- Pacing Analysis: Tension curves, quiet moments, climaxes
- Foreshadowing Map: Seeds planted and their payoffs

Use the tools to gather evidence from the simulation data before writing each section.
Be specific — cite which agents contributed which ideas."""


class ReportAgent:
    """ReACT agent that iteratively queries simulation data and produces a report."""

    def __init__(self, session: SimulationSession, graph_builder=None):
        self.session = session
        self.graph_builder = graph_builder
        self.sections: list[dict] = []
        self.tool_log: list[dict] = []

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """Execute a tool and return the result as a string."""
        try:
            if tool_name == "search_graph":
                if self.graph_builder:
                    results = self.graph_builder.search_entities(self.session.project_id, tool_input)
                    return json.dumps(results[:10], indent=2, default=str)
                return "Graph not available."

            elif tool_name == "get_entity":
                if self.graph_builder:
                    result = self.graph_builder.query_entity(self.session.project_id, tool_input)
                    return json.dumps(result, indent=2, default=str) if result else "Entity not found."
                return "Graph not available."

            elif tool_name == "get_posts_by_agent":
                posts = [p for p in self.session.posts if tool_input.lower() in p.author_name.lower()]
                summaries = [{"action": p.action.value, "round": p.round, "text": p.text[:200], "platform": p.platform.value} for p in posts[:15]]
                return json.dumps(summaries, indent=2)

            elif tool_name == "get_posts_by_action":
                posts = [p for p in self.session.posts if p.action.value == tool_input.strip()]
                summaries = [{"author": p.author_name, "round": p.round, "text": p.text[:200]} for p in posts[:15]]
                return json.dumps(summaries, indent=2)

            elif tool_name == "get_platform_summary":
                platform = Platform.CRITICS_FORUM if "critic" in tool_input.lower() else Platform.INWORLD_FORUM
                posts = [p for p in self.session.posts if p.platform == platform]
                action_counts = {}
                for p in posts:
                    action_counts[p.action.value] = action_counts.get(p.action.value, 0) + 1
                agents = set(p.author_name for p in posts)
                return json.dumps({
                    "platform": platform.value,
                    "total_posts": len(posts),
                    "unique_agents": len(agents),
                    "action_distribution": action_counts,
                    "sample_posts": [{"author": p.author_name, "action": p.action.value, "text": p.text[:150]} for p in posts[-5:]],
                }, indent=2)

            elif tool_name == "interview_agent":
                parts = tool_input.split("|", 1)
                agent_name = parts[0].strip()
                question = parts[1].strip() if len(parts) > 1 else "What was your reasoning?"

                agent = next((a for a in self.session.agents if agent_name.lower() in a.name.lower()), None)
                if not agent:
                    return f"Agent '{agent_name}' not found."

                agent_posts = [p for p in self.session.posts if p.author_id == agent.id]
                context = "\n".join(f"[R{p.round}|{p.action.value}]: {p.text[:200]}" for p in agent_posts[-5:])

                response = llm_client.chat(
                    [{"role": "user", "content": f"Question: {question}\n\nYour posts during the simulation:\n{context}"}],
                    system=f'You are "{agent.name}" ({agent.role}). Traits: {", ".join(agent.personality_traits)}. '
                           f'Background: {agent.backstory}\nAnswer the question based on your simulation experience. Stay in character.',
                )
                return response

            elif tool_name == "get_opinion_shifts":
                shifts = []
                for agent in self.session.agents:
                    shifts.append({
                        "name": agent.name,
                        "platform": agent.platform.value,
                        "current_stance": agent.stance.value,
                        "total_shifts": len(agent.opinion_history),
                        "history": agent.opinion_history[-5:],
                    })
                return json.dumps(shifts, indent=2)

            elif tool_name == "get_relationship_map":
                return "Relationship data available in agent memory databases."

            elif tool_name == "write_section":
                parts = tool_input.split("|", 1)
                title = parts[0].strip()
                content = parts[1].strip() if len(parts) > 1 else ""
                self.sections.append({"title": title, "content": content})
                return f"Section '{title}' written ({len(content)} chars)."

            elif tool_name == "finalize_report":
                return "REPORT_FINALIZED"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Tool error: {str(e)}"

    def generate_report(self, max_iterations: int = 15) -> str:
        """Run the ReACT loop to generate a comprehensive report."""
        mode_label = "LORE ENHANCEMENT" if self.session.config.mode == "lore" else "OUTLINE GENERATION"

        # Build initial context
        stats = {
            "total_posts": len(self.session.posts),
            "total_agents": len(self.session.agents),
            "rounds": self.session.config.rounds,
            "critics_posts": len([p for p in self.session.posts if p.platform == Platform.CRITICS_FORUM]),
            "inworld_posts": len([p for p in self.session.posts if p.platform == Platform.INWORLD_FORUM]),
        }

        conversation = [
            {"role": "user", "content": (
                f"Generate a {mode_label} report from this simulation.\n\n"
                f"SIMULATION STATS: {json.dumps(stats)}\n\n"
                f"ORIGINAL LORE:\n{self.session.config.prediction_requirement[:2000]}\n\n"
                f"{TOOL_DEFINITIONS}\n\n"
                f"Begin your ReACT loop. First, reason about what information you need, then use tools."
            )},
        ]

        system = REACT_SYSTEM.format(mode=mode_label)

        for iteration in range(max_iterations):
            response = llm_client.chat(conversation, system=system, max_tokens=1500)
            conversation.append({"role": "assistant", "content": response})

            # Parse tool calls
            if "TOOL:" in response:
                lines = response.split("\n")
                tool_name = None
                tool_input = ""
                for line in lines:
                    if line.strip().startswith("TOOL:"):
                        tool_name = line.split("TOOL:")[1].strip().lower().replace(" ", "_")
                    elif line.strip().startswith("INPUT:"):
                        tool_input = line.split("INPUT:", 1)[1].strip()

                if tool_name:
                    result = self._execute_tool(tool_name, tool_input)
                    self.tool_log.append({
                        "iteration": iteration,
                        "tool": tool_name,
                        "input": tool_input,
                        "result_length": len(result),
                    })

                    if result == "REPORT_FINALIZED":
                        break

                    conversation.append({"role": "user", "content": f"TOOL RESULT:\n{result}\n\nContinue your analysis. Use more tools or write sections."})
            else:
                # No tool call — check if it's writing content directly
                if "finalize" in response.lower() or iteration >= max_iterations - 1:
                    break
                conversation.append({"role": "user", "content": "Continue. Use tools to gather more data, then write_section for each part of the report."})

        # Compile final report
        if self.sections:
            report = f"# NovelSwarm {mode_label} Report\n\n"
            report += f"*Generated from {stats['total_posts']} posts by {stats['total_agents']} agents over {stats['rounds']} rounds*\n\n"
            for section in self.sections:
                report += f"## {section['title']}\n\n{section['content']}\n\n"
            return report
        else:
            # Fallback: use the last response as the report
            return response

    def chat(self, message: str, history: list[dict] = None) -> str:
        """Post-report interactive chat with the ReportAgent."""
        history = history or []

        context = f"You generated a report from a simulation with {len(self.session.posts)} posts by {len(self.session.agents)} agents.\n"
        if self.sections:
            context += "Report sections: " + ", ".join(s["title"] for s in self.sections) + "\n"

        messages = [*history, {"role": "user", "content": message}]
        return llm_client.chat(
            messages,
            system=f"You are the ReportAgent for a novel writing simulation. {context}\nAnswer questions about the simulation results. You can reference specific agents and their contributions.",
        )

    def interview_agent(self, agent_id: str, question: str) -> str:
        """Interview a specific simulated agent."""
        agent = next((a for a in self.session.agents if a.id == agent_id), None)
        if not agent:
            return "Agent not found."
        return self._execute_tool("interview_agent", f"{agent.name}|{question}")
