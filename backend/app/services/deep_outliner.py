"""
Deep Outliner — Multi-pass chapter-by-chapter outline generation.

Instead of one massive LLM call, this:
0. Generates SAGA/VOLUME structure (macro-story organization)
1. Generates the story SPINE (acts, major turning points)
2. Breaks each act into chapters with a dedicated call per act
3. Deepens EACH chapter individually with a per-chapter call
4. Validates character arcs track consistently across chapters
5. Arc Loop: After each arc, checks if continuation/escalation is needed

Result: 30-800 deeply detailed chapters, organized into sagas and acts.
"""

import json
from app.services import llm_client
from app.models.schemas import AgentPersona


class DeepOutliner:
    """Multi-pass outline generator that produces genuinely writable chapter plans."""

    def __init__(
        self,
        seed: str,
        expanded_seed: str,
        world_data: dict,
        debate_highlights: str,
        characters: list[dict],
        arcs: list[dict],
        simulation_events: str = "",
        chapter_count: int = 35,
        actual_ending: str = "",
        genres: str = "",
        pacing="balanced",
        mood="neutral",
        graph_builder=None,
        project_id="",
    ):
        self.seed = seed
        self.expanded_seed = expanded_seed
        self.world_data = world_data
        self.debate_highlights = debate_highlights
        self.simulation_events = simulation_events
        self.characters = characters
        self.arcs = arcs
        self.chapter_count = chapter_count
        self.actual_ending = actual_ending
        self.genres = genres
        self.pacing = pacing
        self.mood = mood
        self.graph_builder = graph_builder
        self.project_id = project_id
        self.spine = {}
        self.sagas = []  # NEW: Saga/Volume structure
        self.chapters = []
        self.pov_prose = ""  # Generated first-person prose
        self.pov_agent_name = ""
        self.log = []
        self.arc_loop_enabled = True  # Enable infinite arc generation

    # ═══ PASS 0: Saga/Volume Structure (NEW) ═══

    def generate_sagas(self, emit_fn=None) -> list[dict]:
        """Generate Saga/Volume structure before Acts.

        For 100+ chapter novels, organizes content into manageable volumes.
        Each saga = ~100 chapters or thematic grouping.
        """
        saga_count = max(2, min(10, self.chapter_count // 100))

        logger = self._get_logger()
        logger.info(f"  -> Generating {saga_count} Sagas/Volumes...")
        if emit_fn:
            emit_fn("saga_stage", {"stage": "Generating sagas", "count": saga_count})

        saga_prompt = f"""Design the SAGA/VOLUME structure for this {self.chapter_count}-chapter novel.

A SAGA is a major story arc spanning ~{self.chapter_count // saga_count if saga_count > 0 else 25} chapters.
Each saga should have:
- A central thematic question
- A climactic event that changes everything
- A resolution that sets up the next saga

REQUIRED:
- Generate exactly {saga_count} sagas
- They MUST connect to each other
- Each saga needs a title, theme, and key events

SEED: {self.seed}
CONCEPT: {self.expanded_seed[:600]}
{f"SIMULATION EVENTS:\n{self.simulation_events[:800]}\n" if self.simulation_events else ""}

Return JSON:
{{
  "sagas": [
    {{
      "saga_number": 1,
      "title": "Saga title",
      "theme": "central thematic question",
      "chapters_range": [1, {self.chapter_count // saga_count if saga_count > 0 else 25}],
      "starts_with": "how does this saga begin",
      "ends_with": "what climactic event ends this saga",
      "central_conflict": "what is the main conflict in this saga",
      "key_events": ["event1", "event2"],
      "characters_central": ["main characters in this saga"],
      "stakes": "what is at stake",
      "resolution": "how does this saga resolve (but not fully end the story)"
    }},
    ...
  ]
}}"""

        try:
            result = llm_client.chat_json(
                [{"role": "user", "content": saga_prompt}],
                system="You are a master story architect. Design a saga structure that creates epic, interconnected storytelling.",
                max_tokens=6000,
            )

            if isinstance(result, dict) and "sagas" in result:
                self.sagas = result["sagas"]
            elif isinstance(result, list):
                self.sagas = result
            else:
                self.sagas = []

            self.log.append({"pass": "sagas", "count": len(self.sagas)})
            logger.info(f"  Generated {len(self.sagas)} sagas")

            if emit_fn:
                emit_fn("saga_complete", {"sagas": self.sagas})

            return self.sagas

        except Exception as e:
            logger.warning(f"  Saga generation failed: {e}")
            return []

    def _get_logger(self):
        """Get or create logger."""
        try:
            from app.utils.logger import get_logger

            return get_logger("mirofish.outliner")
        except Exception:
            import logging

            return logging.getLogger("mirofish.outliner")

    def _world_summary(self, max_len=3000) -> str:
        lines = []
        for layer, items in self.world_data.items():
            if not items:
                continue
            lines.append(f"[{layer}]")
            for item in (items if isinstance(items, list) else [items])[:4]:
                if isinstance(item, dict):
                    n = (
                        item.get("name")
                        or item.get("era_name")
                        or item.get("theme")
                        or "?"
                    )
                    lines.append(f"  {n}")
        return "\n".join(lines)[:max_len]

    def _chars_summary(self) -> str:
        lines = []
        for c in self.characters[:12]:
            name = c.get("name", "?")
            role = c.get("role_in_story", c.get("role", "?"))
            arc = c.get("character_arc_summary", c.get("arc", ""))[:100]
            lines.append(f"  {name} ({role}): {arc}")
        return "\n".join(lines)

    # ═══ PASS 1: Story Spine ═══

    def generate_spine(self, emit_fn=None) -> dict:
        """Generate the macro-structure: acts, major turning points, climax (with multi-draft iterations)."""
        user_prompt = f"""Design the story SPINE for this novel.

CONSTRAINTS (you MUST follow these exactly):
- CHAPTER COUNT: {self.chapter_count} (total_chapters field MUST equal {self.chapter_count})
- GENRES: {self.genres or "not specified"}
- REQUIRED ENDING: {self.actual_ending or "author's choice"}
- PACING: {self.pacing}
- MOOD: {self.mood}

SEED: {self.seed}
CONCEPT: {self.expanded_seed[:800]}

{f"SIMULATION EVENTS (incorporate these specific actions into the plot):\n{self.simulation_events[:1500]}\n" if self.simulation_events else ""}
{f"CRITICS FORUM DEBATE HIGHLIGHTS:\n{self.debate_highlights[:1000]}\n" if self.debate_highlights else ""}

MASTERPIECE EXAMPLE OF A GREAT ACT SUMMARY:
{{
  "act_number": 1,
  "act_name": "The Rotting Crown",
  "theme": "The cost of blind loyalty vs. the necessity of rebellion",
  "chapters_range": [1, 5],
  "starts_with": "Kaelen discovers the Queen's secret pact with the Void-bringers.",
  "ends_with": "The Burning of High-Guard; Kaelen is framed for treason.",
  "key_events": ["The Midnight Council", "Assassination of Duke Vane"],
  "emotional_arc": "From naive devotion to shattering disillusionment",
  "characters_introduced": ["Queen Iyana (The Betrayer)", "Slythe (Void-touched informant)"],
  "subplots_active": ["The missing royal heir"]
}}

Return ONLY valid JSON in this exact structure:
{{
  "_thinking": "Your step-by-step reasoning about how to hit the constraints, escalate tension, and align with the ending.",
  "spine": {{
    "title": "Novel title",
    "total_chapters": {self.chapter_count},
    "act_structure": [
      {{
        "act_number": 1,
        "act_name": "Act name here",
        "theme": "core thematic idea",
        "chapters_range": [1, {self.chapter_count // 3}],
        "starts_with": "opening situation",
        "ends_with": "first major turning point",
        "key_events": ["event1", "event2"],
        "emotional_arc": "from X to Y",
        "characters_introduced": ["name1"],
        "subplots_active": ["subplot name"]
      }},
      {{
        "act_number": 2,
        "act_name": "Act name here",
        "theme": "core thematic idea",
        "chapters_range": [{self.chapter_count // 3 + 1}, {self.chapter_count * 2 // 3}],
        "starts_with": "escalation begins",
        "ends_with": "darkest moment / all is lost",
        "key_events": ["event1", "event2"],
        "emotional_arc": "from X to Y",
        "characters_introduced": ["name1"],
        "subplots_active": ["subplot name"]
      }},
      {{
        "act_number": 3,
        "act_name": "Act name here",
        "theme": "core thematic idea",
        "chapters_range": [{self.chapter_count * 2 // 3 + 1}, {self.chapter_count}],
        "starts_with": "darkest moment aftermath",
        "ends_with": "resolution matching the REQUIRED ENDING",
        "climax_and_ending": "Describe the climax and how the story resolves — must match: {self.actual_ending or "author choice"}",
        "key_events": ["event1", "event2"],
        "emotional_arc": "from X to Y",
        "characters_introduced": [],
        "subplots_active": ["subplot name"]
      }}
    ],
    "major_turning_points": [
      {{"chapter": {self.chapter_count // 3}, "event": "...", "consequence": "...", "characters_affected": ["..."]}},
      {{"chapter": {self.chapter_count * 2 // 3}, "event": "...", "consequence": "...", "characters_affected": ["..."]}}
    ],
    "climax": {{"chapter": {self.chapter_count - 3}, "description": "...", "stakes": "..."}},
    "resolution": {{"chapters": [{self.chapter_count - 2}, {self.chapter_count}], "what_resolves": "...", "what_remains_open": "..."}}
  }}
}}"""
        system = "You are a master story architect. Return ONLY the JSON — no explanation outside the JSON."

        from app.utils.logger import get_logger

        logger = get_logger("mirofish.outliner")
        logger.info("  -> Generating Rough Draft of Story Spine...")
        if emit_fn:
            emit_fn("draft_stage", {"layer": "Spine", "stage": "Rough Draft"})

        draft = llm_client.chat_json(
            [{"role": "user", "content": user_prompt}],
            system=system,
            max_tokens=6000,
        )
        if isinstance(draft, dict) and "spine" in draft:
            draft = draft["spine"]

        draft_stages = ["First Draft", "Second Draft", "Final Draft"]
        for stage in draft_stages:
            logger.info(f"  -> Generating {stage} of Story Spine...")
            if emit_fn:
                emit_fn("draft_stage", {"layer": "Spine", "stage": stage})

            draft_text = json.dumps(draft, indent=2)
            critique_prompt = f"{user_prompt}\n\nCURRENT DRAFT:\n{draft_text}\n\nCritique this draft for pacing, narrative tension, character arcs, and alignment with the required ending. Then output the improved {stage.upper()} JSON."

            draft = llm_client.chat_json(
                [{"role": "user", "content": critique_prompt}],
                system=system,
                max_tokens=6000,
            )
            if isinstance(draft, dict) and "spine" in draft:
                draft = draft["spine"]

        self.spine = draft
        self.log.append(
            {"pass": "spine", "acts": len(self.spine.get("act_structure", []))}
        )
        return self.spine

    # ═══ PASS 2: Per-Act Chapter Breakdown ═══

    def generate_act_chapters(self) -> list[dict]:
        """For each act, generate its chapters in detail."""
        self.chapters = []

        for act in self.spine.get("act_structure", []):
            act_num = act.get("act_number", 0)
            ch_start, ch_end = act.get("chapters_range", [1, 10])

            # What happened in previous acts (for continuity)
            prev_chapters_summary = ""
            if self.chapters:
                prev_chapters_summary = "PREVIOUS CHAPTERS:\n" + "\n".join(
                    f"  Ch{c['chapter']}: {c.get('title', '?')} — {c.get('summary', '')[:80]}"
                    for c in self.chapters[-8:]
                )

            act_chapters = llm_client.chat_json(
                [
                    {
                        "role": "user",
                        "content": f"""Generate detailed chapters for ACT {act_num}: {act.get("act_name", "")}.

REQUIRED PACING: {self.pacing}
REQUIRED MOOD: {self.mood}

STORY SPINE:
{json.dumps(act, indent=2, default=str)}

WORLD:
{self._world_summary(1500)}

CHARACTERS:
{self._chars_summary()}

{prev_chapters_summary}

AGENT DEBATE INSIGHTS:
{self.debate_highlights[:1000]}

Generate chapters {ch_start} to {ch_end}. For EACH chapter, return:
{{
  "chapter": number,
  "title": "evocative chapter title",
  "pov_character": "whose perspective",
  "setting": "specific location from the world",
  "summary": "3-4 sentence summary of what happens",
  "opening_scene": "how the chapter opens",
  "key_events": ["specific event 1", "specific event 2"],
  "character_development": "how does someone CHANGE in this chapter",
  "conflicts_advanced": ["which tensions escalate or resolve"],
  "thematic_beat": "what deeper meaning is explored",
  "foreshadowing": "what seeds are planted or what pays off",
  "emotional_tone": "what should the reader FEEL",
  "end_hook": "why keep reading — the last line energy",
  "world_elements_used": ["specific world-building elements referenced"]
}}

Return JSON array of chapters.""",
                    }
                ],
                system="Generate specific, writable chapter plans. Every event must use named characters and locations.",
                max_tokens=6000,
            )

            if isinstance(act_chapters, list):
                self.chapters.extend(act_chapters)

            self.log.append(
                {
                    "pass": "act_chapters",
                    "act": act_num,
                    "chapters": len(act_chapters)
                    if isinstance(act_chapters, list)
                    else 0,
                }
            )

        return self.chapters

    # ═══ PASS 3: Per-Chapter Deepening ═══

    def deepen_chapters(self, chapters_to_deepen: list[int] = None):
        """Deepen specific chapters with a dedicated call each.
        If None, deepens all climax/turning-point chapters."""
        if chapters_to_deepen is None:
            # Auto-select important chapters
            turning_points = {
                tp.get("chapter") for tp in self.spine.get("major_turning_points", [])
            }
            climax_ch = self.spine.get("climax", {}).get("chapter", 0)
            chapters_to_deepen = sorted(
                turning_points | {climax_ch, 1, len(self.chapters)}
            )

        for ch_num in chapters_to_deepen:
            ch = next((c for c in self.chapters if c.get("chapter") == ch_num), None)
            if not ch:
                continue

            # Get surrounding chapters for continuity
            prev_ch = next(
                (c for c in self.chapters if c.get("chapter") == ch_num - 1), {}
            )
            next_ch = next(
                (c for c in self.chapters if c.get("chapter") == ch_num + 1), {}
            )

            rag_context = ""
            if self.graph_builder and self.project_id:
                try:
                    ch_dump = json.dumps(ch).lower()
                    mentioned_chars = [
                        c
                        for c in self.characters
                        if c.get("name", "").lower() in ch_dump
                    ]
                    for mc in mentioned_chars[:4]:
                        web = self.graph_builder.query_character_web(
                            self.project_id, mc.get("name")
                        )
                        if web:
                            rag_context += f"Connections for {mc.get('name')}:\n{web}\n"
                except Exception as e:
                    pass

            deepened = llm_client.chat_json(
                [
                    {
                        "role": "user",
                        "content": f"""Deepen this chapter into a scene-by-scene breakdown.

REQUIRED PACING: {self.pacing}
REQUIRED MOOD: {self.mood}

CHAPTER {ch_num}: {ch.get("title", "")}
Current plan: {json.dumps(ch, indent=2, default=str)[:1000]}

Previous chapter ends with: {prev_ch.get("end_hook", "N/A")}
Next chapter opens with: {next_ch.get("opening_scene", "N/A")}

WORLD CONTEXT:
{self._world_summary(800)}

GRAPH-RAG RELATIONAL CONTEXT (MUST BE RESPECTED):
{rag_context}

Return JSON:
{{
  "chapter": {ch_num},
  "scenes": [
    {{
      "scene_number": 1,
      "location": "specific place",
      "characters_present": ["name1", "name2"],
      "what_happens": "detailed 2-3 sentence scene description",
      "dialogue_key_line": "one important line that could actually be in the book",
      "emotional_beat": "what the reader feels",
      "subtext": "what's really going on beneath the surface"
    }}
  ],
  "chapter_word_count_estimate": 3500,
  "pacing_note": "fast/slow/building/release"
}}""",
                    }
                ],
                system="Generate detailed scene breakdowns. Be specific enough that someone could write this chapter.",
            )

            if isinstance(deepened, dict):
                # Merge deepened data into the chapter
                for c in self.chapters:
                    if c.get("chapter") == ch_num:
                        c["scenes"] = deepened.get("scenes", [])
                        c["word_count_estimate"] = deepened.get(
                            "chapter_word_count_estimate", 3000
                        )
                        c["pacing_note"] = deepened.get("pacing_note", "")
                        break

            self.log.append(
                {
                    "pass": "deepen",
                    "chapter": ch_num,
                    "scenes": len(deepened.get("scenes", []))
                    if isinstance(deepened, dict)
                    else 0,
                }
            )

    # ═══ PASS 4: Character Arc Validation ═══

    def validate_character_arcs(self) -> list[dict]:
        """Check that character arcs track consistently across chapters."""
        arc_issues = []
        for char in self.characters[:8]:
            char_name = char.get("name", "?")
            char_chapters = [
                c for c in self.chapters if char_name.lower() in json.dumps(c).lower()
            ]

            if len(char_chapters) < 2:
                continue

            try:
                result = llm_client.chat_json(
                    [
                        {
                            "role": "user",
                            "content": f"""Validate the arc for {char_name} across these chapters:

CHARACTER: {json.dumps(char, default=str)[:500]}

APPEARANCES:
{json.dumps([{"ch": c["chapter"], "title": c.get("title"), "dev": c.get("character_development"), "events": c.get("key_events")} for c in char_chapters], default=str)[:2000]}

Check:
1. Does the character GROW consistently?
2. Are there gaps where they disappear too long?
3. Does their final state match their arc description?
4. Are there contradictions in their behavior?

Return JSON: {{"character": "{char_name}", "arc_valid": true/false, "issues": ["issue1"], "suggestions": ["fix1"]}}""",
                        }
                    ],
                    system="Validate character arcs. Be specific about problems.",
                )
                if not result.get("arc_valid", True):
                    arc_issues.append(result)
            except Exception:
                pass

        self.log.append({"pass": "arc_validation", "issues": len(arc_issues)})
        return arc_issues

    # ═══ ARC LOOP SYSTEM: Escalation Check After Each Arc ═══

    def check_arc_continuation(
        self, completed_arc: dict, next_arc_num: int, total_acts: int
    ) -> dict:
        """After each arc, check if story should continue/escalate.

        This enables infinite story generation with proper escalation.
        """
        logger = self._get_logger()

        completed_chapters = completed_arc.get("chapters_range", [0, 0])
        current_ch_count = (
            completed_chapters[1]
            if len(completed_chapters) > 1
            else completed_chapters[0]
        )

        # Build context of what's happened
        arc_context = f"""COMPLETED ARC {completed_arc.get("act_number", 0)}: {completed_arc.get("act_name", "")}
Theme: {completed_arc.get("theme", "")}
Ended with: {completed_arc.get("ends_with", completed_arc.get("ends_with", ""))}
Key events: {", ".join(completed_arc.get("key_events", []))}

STORY PROGRESS: {current_ch_count}/{self.chapter_count} chapters completed
REMAINING: {self.chapter_count - current_ch_count} chapters
NEXT ARC: #{next_arc_num} of {total_acts}
"""

        continuation_prompt = f"""{arc_context}

Evaluate if the story should ESCALATE, CONTINUE, or begin WRAP-UP:

1. ESCALATION: Increase stakes, introduce new threats, deepen mysteries
2. CONTINUE: Keep the same tension level, develop subplots
3. WRAP-UP: Begin closing threads, lead to resolution

Consider:
- Are stakes at maximum? Should they go higher?
- Are there unresolved mysteries or prophecies?
- Do characters have unmet goals?
- Is the climax building appropriately?
- Are there foreshadowed events not yet paid off?
- Is it too soon to end?

Return JSON:
{{
  "decision": "escalate|continue|wrap_up",
  "confidence": 0.0-1.0,
  "reason": "why this decision",
  "if_escalate": {{
    "new_threats": ["what could escalate"],
    "new_mysteries": ["unresolved threads to deepen"],
    "stakes_increase": "how to raise the stakes"
  }},
  "if_continue": {{
    "subplots_to_develop": ["which subplots need attention"],
    "character_moments": ["character development opportunities"]
  }},
  "if_wrap_up": {{
    "threads_to_close": ["unresolved plot threads"],
    "climax_elements": ["what the climax needs"],
    "resolution_checklist": ["what needs to be resolved"]
  }}
}}"""

        try:
            result = llm_client.chat_json(
                [{"role": "user", "content": continuation_prompt}],
                system="You are a story architect. Be bold - stories need escalation to stay interesting.",
                max_tokens=2000,
            )
            logger.info(
                f"  Arc {next_arc_num - 1} continuation check: {result.get('decision')}"
            )
            return result
        except Exception as e:
            logger.warning(f"  Continuation check failed: {e}")
            return {"decision": "continue", "reason": "check_failed"}

    # ═══ FULL OUTLINE PIPELINE ═══

    def generate_full(
        self, progress_callback=None, skip_spine: bool = False, skip_sagas: bool = False
    ) -> dict:
        """Run all passes to produce a complete deep outline.

        If arc_loop_enabled=True, performs escalation checks after each arc.
        """
        # Generate Sagas first (for 100+ chapter novels)
        if not skip_sagas and self.chapter_count >= 100:
            if progress_callback:
                progress_callback("Generating saga structure...", 0, 7)
            self.generate_sagas(progress_callback)

        if not skip_spine:
            if progress_callback:
                progress_callback(
                    "Generating story spine...", 1 if self.chapter_count < 100 else 2, 7
                )
            self.generate_spine()

        if progress_callback:
            progress_callback(
                "Breaking into chapters...", 2 if self.chapter_count < 100 else 3, 7
            )
        self.generate_act_chapters()

        # Arc Loop: Check escalation after each act
        if self.arc_loop_enabled:
            acts = self.spine.get("act_structure", [])
            for i, act in enumerate(acts):
                if i > 0:  # After first arc, check continuation
                    continuation = self.check_arc_continuation(act, i + 1, len(acts))

                    if continuation.get("decision") == "escalate":
                        logger = self._get_logger()
                        logger.info(f"  ESCALATION TRIGGERED after Act {i}")
                        if progress_callback:
                            progress_callback(
                                f"Escalating story after Act {i}...", 3, 7
                            )

                        # Log escalation for later use
                        self.log.append(
                            {
                                "pass": "arc_escalation",
                                "act": i,
                                "decision": continuation,
                            }
                        )

        if progress_callback:
            progress_callback("Deepening key chapters...", 4, 7)
        self.deepen_chapters()

        if progress_callback:
            progress_callback("Validating character arcs...", 5, 7)
        arc_issues = self.validate_character_arcs()

        if progress_callback:
            progress_callback("Compiling final outline...", 6, 7)

        return {
            "spine": self.spine,
            "sagas": self.sagas,  # NEW: Include sagas
            "chapters": self.chapters,
            "arc_issues": arc_issues,
            "total_chapters": len(self.chapters),
            "deepened_chapters": len([c for c in self.chapters if c.get("scenes")]),
            "pov_prose": self.pov_prose,
            "pov_agent_name": self.pov_agent_name,
            "generation_log": self.log,
        }

    def to_markdown(self) -> str:
        """Convert the outline to a readable markdown document."""
        md = f"# {self.spine.get('title', 'Novel Outline')}\n\n"
        md += f"## Seed\n{self.seed}\n\n"

        # Sagas (if generated)
        if self.sagas:
            md += f"## Sagas/Volumes\n"
            for saga in self.sagas:
                md += f"\n### Saga {saga.get('saga_number', 0)}: {saga.get('title', '')}\n"
                md += f"Chapters {saga.get('chapters_range', [])}\n"
                md += f"Theme: {saga.get('theme', '')}\n"
                md += f"Central Conflict: {saga.get('central_conflict', '')}\n"
                md += f"Ends with: {saga.get('ends_with', '')}\n"

        md += f"## Story Spine\n"
        for act in self.spine.get("act_structure", []):
            md += f"\n### Act {act.get('act_number')}: {act.get('act_name', '')}\n"
            md += f"Chapters {act.get('chapters_range', [])}\n"
            md += f"Theme: {act.get('theme', '')}\n"
            md += f"Emotional arc: {act.get('emotional_arc', '')}\n"

        md += f"\n## Chapters\n"
        for ch in self.chapters:
            md += f"\n### Chapter {ch.get('chapter', '?')}: {ch.get('title', '')}\n"
            md += f"**POV:** {ch.get('pov_character', '?')} | **Setting:** {ch.get('setting', '?')}\n\n"
            md += f"{ch.get('summary', '')}\n\n"
            if ch.get("key_events"):
                md += f"**Events:** {', '.join(ch['key_events'][:5])}\n\n"
            if ch.get("character_development"):
                md += f"**Character development:** {ch['character_development']}\n\n"
            if ch.get("foreshadowing"):
                md += f"**Foreshadowing:** {ch['foreshadowing']}\n\n"
            if ch.get("end_hook"):
                md += f"**End hook:** {ch['end_hook']}\n\n"
            if ch.get("scenes"):
                md += f"**Scenes:**\n"
                for scene in ch["scenes"]:
                    md += f"  {scene.get('scene_number', '?')}. [{scene.get('location', '?')}] {scene.get('what_happens', '')}\n"
                    if scene.get("dialogue_key_line"):
                        md += f'     *"{scene["dialogue_key_line"]}"*\n'
                md += "\n"

        if self.pov_prose:
            md += f"\n---\n\n## First Chapter Draft — POV: {self.pov_agent_name}\n\n"
            md += self.pov_prose + "\n"

        return md

    # ═══ POV PROSE GENERATION ═══

    def generate_pov_chapter(
        self, agents: list["AgentPersona"] = None, progress_callback=None
    ) -> str:
        """Write the first chapter as actual prose using the most reactive agent's voice.

        Selects the agent with the most intense living memories (the character
        who was most emotionally affected during the debate) and writes
        Chapter 1 from their first-person perspective.
        """
        if progress_callback:
            progress_callback("Generating POV prose draft...", 5, 6)

        # --- SELECT the POV character ---
        pov_agent = None
        if agents:

            def _reactivity(a):
                score = 0.0
                for m in a.living_memories:
                    score += m.intensity
                score += a.posts_count * 0.1 + a.replies_count * 0.05
                return score

            pov_agent = max(agents, key=_reactivity)
            self.pov_agent_name = pov_agent.name

        # Get Chapter 1 details
        ch1 = next((c for c in self.chapters if c.get("chapter") == 1), {})
        if not ch1 and self.chapters:
            ch1 = self.chapters[0]

        # Build the persona context for the LLM
        persona_ctx = ""
        if pov_agent:
            cog = pov_agent.cognitive
            life = pov_agent.life
            persona_ctx = (
                f"You ARE {pov_agent.name}. Write from inside their skull.\n"
                f"Age: {pov_agent.age} | Race: {pov_agent.race} | Gender: {pov_agent.gender}\n"
                f"Personality: {pov_agent.personality_summary}\n"
                f"IQ: {cog.intelligence} | Education: {cog.education_level}\n"
                f"Communication style: {cog.communication_style}\n"
                f"Speech pattern: {pov_agent.speech_pattern or 'natural'}\n"
                f"Cognitive biases: {', '.join(cog.cognitive_biases or [])}\n"
                f"Blind spots: {', '.join(cog.blind_spots or [])}\n"
                f"Deepest wound: {life.deepest_wound or 'unknown'}\n"
                f"Formative event: {life.formative_event or 'unknown'}\n"
                f"Social origin: {life.social_class_origin or 'unknown'}\n"
                f"Catchphrase: {pov_agent.catchphrase or 'none'}\n"
                f"Quirks: {', '.join(pov_agent.quirks or [])}\n"
            )
        else:
            self.pov_agent_name = ch1.get("pov_character", "Narrator")
            persona_ctx = f"Write from the perspective of {self.pov_agent_name}.\n"

        system_prompt = (
            f"You are a world-class fantasy novelist. Write Chapter 1 of this novel "
            f"in vivid, immersive first-person prose.\n\n"
            f"{persona_ctx}\n"
            f"CRITICAL RULES:\n"
            f"1. The prose MUST sound like this specific character — their vocabulary, "
            f"their biases, their speech rhythm.\n"
            f"2. Their cognitive biases should subtly distort how they perceive events.\n"
            f"3. Their deepest wound should color their internal monologue.\n"
            f"4. Use sensory details — what they see, smell, hear, feel.\n"
            f"5. Write 1500-2500 words of publication-quality prose.\n"
            f"6. End on a hook that makes the reader desperate for Chapter 2.\n"
        )

        user_prompt = (
            f"CHAPTER 1 PLAN:\n"
            f"Title: {ch1.get('title', 'Untitled')}\n"
            f"Setting: {ch1.get('setting', 'Unknown')}\n"
            f"Summary: {ch1.get('summary', 'No summary')}\n"
            f"Opening scene: {ch1.get('opening_scene', 'No opening defined')}\n"
            f"Key events: {json.dumps(ch1.get('key_events', []), default=str)}\n"
            f"Emotional tone: {ch1.get('emotional_tone', 'unknown')}\n"
            f"End hook: {ch1.get('end_hook', 'unknown')}\n\n"
            f"WORLD:\n{self._world_summary(1500)}\n\n"
            f"CHARACTERS:\n{self._chars_summary()}\n\n"
            f"Now write the full Chapter 1 prose. No outline, no notes — just the novel itself."
        )

        self.pov_prose = llm_client.chat(
            [{"role": "user", "content": user_prompt}],
            system=system_prompt,
            max_tokens=4096,
            temperature=0.85,
        )

        self.log.append(
            {
                "pass": "pov_prose",
                "agent": self.pov_agent_name,
                "words": len(self.pov_prose.split()),
            }
        )
        return self.pov_prose
