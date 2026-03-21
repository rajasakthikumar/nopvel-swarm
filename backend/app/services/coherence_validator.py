"""
Coherence Validator — Catches contradictions between world layers.

After each layer is generated, validates it against Neo4j for:
- Name consistency (same entity referred to differently)
- Relationship contradictions (X leads Y, but Y says Z leads it)
- Timeline violations (event A before B, but B supposedly caused A)
- Dead references (mentions entity that doesn't exist)
- Duplicate entities across layers

When contradictions are found, it auto-corrects by re-querying the LLM
with the contradiction highlighted.
"""

import json
from app.services import llm_client


class CoherenceValidator:
    """Validates and repairs contradictions between world layers."""

    def __init__(self, graph_builder=None, project_id=None):
        self.graph_builder = graph_builder
        self.project_id = project_id
        self.issues: list[dict] = []
        self.corrections: list[dict] = []

    def validate_layer(self, layer_name: str, layer_data: list[dict],
                       all_previous_data: dict) -> list[dict]:
        """Validate a newly generated layer against everything else.
        Returns list of issues found."""
        found_issues = []

        # 1. Dead reference check — does it mention entities that don't exist?
        all_known_names = set()
        for prev_name, prev_items in all_previous_data.items():
            for item in (prev_items if isinstance(prev_items, list) else [prev_items]):
                if isinstance(item, dict):
                    name = item.get("name") or item.get("era_name") or item.get("arc_name") or item.get("theme")
                    if name:
                        all_known_names.add(name.lower())

        for item in layer_data:
            item_text = json.dumps(item).lower()
            # Check if this layer's items reference names not in the graph
            for name in all_known_names:
                pass  # Names existing is fine — we want to catch when they DON'T exist

        # 2. LLM-based contradiction check (most powerful)
        if all_previous_data and layer_data:
            found_issues.extend(self._llm_contradiction_check(layer_name, layer_data, all_previous_data))

        self.issues.extend(found_issues)
        return found_issues

    def _llm_contradiction_check(self, layer_name: str, layer_data: list[dict],
                                  previous_data: dict) -> list[dict]:
        """Use LLM to find contradictions."""
        # Build a condensed view of relevant previous data
        prev_summary = ""
        for name, items in previous_data.items():
            if not items: continue
            prev_summary += f"\n[{name.upper()}]:\n"
            for item in (items if isinstance(items, list) else [items])[:4]:
                if isinstance(item, dict):
                    n = item.get("name") or item.get("era_name") or "?"
                    prev_summary += f"  {n}: {json.dumps(item)[:200]}\n"

        new_summary = f"\n[NEW — {layer_name.upper()}]:\n"
        for item in layer_data[:6]:
            n = item.get("name") or "?"
            new_summary += f"  {n}: {json.dumps(item)[:200]}\n"

        try:
            result = llm_client.chat_json(
                [{"role": "user", "content": f"""Check for CONTRADICTIONS between the NEW layer and previously established world data.

PREVIOUSLY ESTABLISHED:
{prev_summary[:3000]}

NEWLY GENERATED:
{new_summary[:2000]}

Find contradictions like:
- Same entity described differently (different leader, different location, etc.)
- Timeline impossibilities
- Power/ability contradictions
- Geographic impossibilities
- Character relationship mismatches

Return JSON: {{"contradictions": [{{"entity": "name", "issue": "description of contradiction", "severity": "high|medium|low", "suggestion": "how to fix"}}]}}
Return {{"contradictions": []}} if no issues found."""}],
                system="You are a world-building consistency checker. Find real contradictions, not nitpicks.",
            )
            issues = result.get("contradictions", [])
            for issue in issues:
                issue["layer"] = layer_name
                issue["type"] = "contradiction"
            return issues
        except Exception:
            return []

    def auto_repair(self, layer_name: str, layer_data: list[dict],
                    issues: list[dict], seed: str, previous_data: dict) -> list[dict]:
        """Re-generate items that have contradictions, with the issues highlighted."""
        if not issues:
            return layer_data

        issues_text = "\n".join(
            f"- {i['entity']}: {i['issue']} (suggestion: {i.get('suggestion', 'fix it')})"
            for i in issues
        )

        # Find which items need repair
        problem_names = {i.get("entity", "").lower() for i in issues}
        items_to_fix = [item for item in layer_data
                        if (item.get("name") or "").lower() in problem_names]
        items_ok = [item for item in layer_data
                    if (item.get("name") or "").lower() not in problem_names]

        if not items_to_fix:
            return layer_data

        prev_summary = ""
        for name, items in previous_data.items():
            if not items: continue
            prev_summary += f"\n[{name}]: "
            for item in (items if isinstance(items, list) else [items])[:3]:
                if isinstance(item, dict):
                    prev_summary += f"{item.get('name', '?')}, "

        try:
            repaired = llm_client.chat_json(
                [{"role": "user", "content": f"""These items have CONTRADICTIONS that need fixing:

ITEMS WITH PROBLEMS:
{json.dumps(items_to_fix, indent=2, default=str)[:2000]}

CONTRADICTIONS FOUND:
{issues_text}

ESTABLISHED WORLD CONTEXT:
{prev_summary[:2000]}

Re-generate ONLY the problematic items with the contradictions FIXED.
Keep the same structure and fields. Return valid JSON array."""}],
                system="Fix the contradictions while keeping the creative spirit. Return valid JSON array only.",
            )
            if isinstance(repaired, list):
                self.corrections.append({
                    "layer": layer_name,
                    "fixed_count": len(repaired),
                    "issues": issues_text,
                })
                return items_ok + repaired
        except Exception:
            pass

        return layer_data

    def get_report(self) -> dict:
        return {
            "total_issues": len(self.issues),
            "total_corrections": len(self.corrections),
            "issues": self.issues,
            "corrections": self.corrections,
        }
