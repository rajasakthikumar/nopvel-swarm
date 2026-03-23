"""
Master Pipeline v3: Seed → Expand → World (+ vector store + validate) → Debate → Deep Outline

Vector DB integration:
- Every generated entity gets embedded in ChromaDB
- Layer generation pulls semantically relevant context from ALL previous layers
- Agent prompts include vector-retrieved world knowledge
- Outline generation uses vector search for per-chapter context
- Coherence validation uses vector similarity to find near-duplicates
"""

import json, os, time, threading, queue, copy, logging
from typing import List, Dict, Any, Optional, Union, cast
from app.services import llm_client

logger = logging.getLogger("novelswarm.pipeline")
from app.services.world_ontology import (
    WorldLayer,
    LAYER_META,
    GENERATION_PHASES,
    build_generation_prompt,
)
from app.services.coherence_validator import CoherenceValidator
from app.services.deep_outliner import DeepOutliner
from app.services.vector_memory import VectorMemory
from app.services.persona_generator import generate_personas
from app.models.schemas import (
    Entity,
    EntityType,
    KnowledgeGraph,
    SimulationSession,
    SimulationConfig,
    SimulationState,
)


class StoryPipeline:
    def __init__(
        self,
        seed,
        graph_builder=None,
        project_id="default",
        upload_dir="uploads",
        agent_count=12,
        debate_rounds=15,
        chapter_count=35,
        actual_ending="",
        genres="",
        pacing="balanced",
        mood="neutral",
        god_mode=False,
    ):
        self.seed = seed
        self.graph_builder = graph_builder
        self.project_id = project_id
        self.upload_dir = upload_dir
        self.agent_count = agent_count
        self.debate_rounds = debate_rounds
        self.chapter_count = chapter_count
        self.actual_ending = actual_ending
        self.genres = genres
        self.pacing = pacing
        self.mood = mood

        self.expanded_seed = ""
        self.world_data = {}
        self.knowledge_graph = KnowledgeGraph()
        self.agents = []
        self.debate_posts = []
        self.outline_data = {}
        self.outline_markdown = ""
        self.pov_prose = ""
        self.coherence_report = {}
        self.active_outliner = None

        self.event_queue = queue.Queue()  # Legacy fallback
        self._subscribers = []  # List of per-client queues for broadcast
        self._sub_lock = threading.Lock()
        self._event_log = []  # Replay buffer for late SSE subscribers
        self.state = "idle"
        self.error = None
        self.active_engine = (
            None  # Reference to the running SimulationEngine for live injections
        )
        self.is_paused = False
        self.is_god_mode = god_mode
        self.injection_queue = []

        self.proj_dir = os.path.join(upload_dir, "projects", project_id)
        os.makedirs(self.proj_dir, exist_ok=True)

        # Initialize vector memory
        from app.config import Config

        self.vector_mem = VectorMemory(project_id, Config.CHROMA_PERSIST_DIR)

        # Timeline tracking
        self.snapshots = {}  # round -> snapshot file path
        self.parent_project_id = None  # If this is a fork

    def subscribe(self):
        """Create a new per-client queue, register it, and replay buffered events."""
        q = queue.Queue()
        with self._sub_lock:
            self._subscribers.append(q)
            # Replay all past events so late-connecting clients don't miss anything
            for event in list(self._event_log):
                try:
                    q.put_nowait(event)
                except Exception:
                    pass
        return q

    def unsubscribe(self, q):
        """Remove a client queue from the broadcast list."""
        with self._sub_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def emit(self, etype, data):
        event = {"type": etype, "data": data, "timestamp": time.time()}
        # Log everything to terminal
        if etype not in ("keepalive", "outline_progress"):
            _d = str(data)[:140]
            logger.info(f"[{etype}] {_d}")
        with self._sub_lock:
            # Append to replay buffer (cap at 500 events)
            self._event_log.append(event)
            if len(self._event_log) > 500:
                self._event_log.pop(0)
            # Broadcast to all active subscribers
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except Exception:
                    pass
        # Also put in legacy queue for non-SSE consumers
        try:
            self.event_queue.put_nowait(event)
        except Exception:
            pass

    def inject_event(self, text: str) -> bool:
        """Pass a manual god-mode event into the active simulation engine or generation queue."""
        self.injection_queue.append(text)
        self.emit("system_notification", f"God-Mode Event Queued: {text}")
        if self.active_engine is not None:
            self.active_engine.inject(text)
            self.emit(
                "system_notification", f"God-Mode Event Injected into Engine: {text}"
            )
            return True
        elif self.active_outliner is not None:
            if hasattr(self.active_outliner, "inject"):
                cast(Any, self.active_outliner).inject(text)
            return True
        return True

    def pause(self):
        self.is_paused = True
        self.emit("pipeline_paused", {"status": "paused"})
        if self.active_engine and not getattr(self.active_engine, "_pause", False):
            self.active_engine.pause()

    def resume(self):
        self.is_paused = False
        self.emit("pipeline_resumed", {"status": "resumed"})
        if self.active_engine is not None and getattr(
            self.active_engine, "resume", None
        ):
            self.active_engine.resume()

    def _check_pause(self):
        while self.is_paused:
            time.sleep(0.5)

    def _save(self, filename, content):
        path = os.path.join(self.proj_dir, filename)
        with open(path, "w") as f:
            if isinstance(content, (dict, list)):
                json.dump(content, f, indent=2, default=str)
            else:
                f.write(str(content))

    # ═══ PHASE 1: Snowflake Expansion (5 options → choose best) ═══

    def expand_seed(self):
        self.state = "expanding_seed"
        logger.info("═══ PHASE 1: Snowflake Expansion ═══")
        self.emit(
            "phase_start",
            {"phase": "expand_seed", "description": "Generating 5 story options"},
        )

        # Step 1: Generate 5 different story concepts
        logger.info("  -> Generating 5 story concept options...")
        self.emit("snowflake_stage", {"stage": "Generating options", "step": 1})

        options_prompt = f"""You are a master story developer. Generate exactly 5 DIFFERENT expanded story concepts from this seed.

SEED: {self.seed}
{f"REQUIRED ENDING: {self.actual_ending}" if self.actual_ending else "ENDING: Author's choice (be creative)"}

For EACH option, provide:
1. A compelling 1-sentence hook
2. A 150-word expanded concept (protagonist with wound/want/need, world hook, central conflict, tone/genre, thematic core, antagonist motivation, opening image, closing image)
3. Why this version has strong narrative potential
4. A suggested title

Return ONLY valid JSON:
{{
  "options": [
    {{
      "option_number": 1,
      "title": "Suggested title",
      "one_sentence_hook": "compelling hook",
      "expanded_concept": "150-word expansion...",
      "why_strong": "narrative strengths...",
      "tone": "tone/genre tags",
      "mood": "emotional quality"
    }},
    ... (exactly 5 options)
  ]
}}"""

        try:
            options_result = llm_client.chat_json(
                [{"role": "user", "content": options_prompt}],
                system="You are a master story developer. Generate exactly 5 diverse story options. Return ONLY valid JSON.",
                max_tokens=8000,
            )

            if isinstance(options_result, dict) and "options" in options_result:
                options = options_result["options"]
            else:
                options = options_result if isinstance(options_result, list) else []

            self._save("snowflake_options.json", options_result)
            logger.info(f"  Generated {len(options)} story options")

            # Step 2: User selects best (or auto-select based on ending match)
            self.emit("snowflake_options", {"options": options, "count": len(options)})

            # Step 3: Expand the best option into full concept
            self.emit("snowflake_stage", {"stage": "Expanding best concept", "step": 2})

            # Build summary of all 5 options so LLM can evaluate and pick the best
            options_summary = "\n\n".join(
                f"OPTION {o.get('option_number', i+1)}: {o.get('title', 'Untitled')}\n"
                f"Hook: {o.get('one_sentence_hook', '')}\n"
                f"Concept: {o.get('expanded_concept', '')[:300]}\n"
                f"Why strong: {o.get('why_strong', '')}\n"
                f"Tone: {o.get('tone', '')} | Mood: {o.get('mood', '')}"
                for i, o in enumerate(options)
            )

            best_option_prompt = f"""Review these {len(options)} story concepts and expand the BEST one into a 600-900 word detailed document.

ALL OPTIONS:
{options_summary}

{f"REQUIRED ENDING: {self.actual_ending}" if self.actual_ending else ""}
{f"PACING: {self.pacing}" if self.pacing else ""}
{f"MOOD: {self.mood}" if self.mood else ""}
{f"GENRES: {self.genres}" if self.genres else ""}

Choose the option with the strongest narrative potential (best protagonist wound, most compelling conflict, richest thematic core). Then expand it into a detailed document including:
- Protagonist: wound, want vs need, flaw, arc
- World hook: unique setting element
- Central conflict: what drives the plot
- Antagonist: believes they're right
- Thematic core: what the story is ABOUT
- 4-5 key relationships
- Opening image
- Closing image
- Tone/genre
- Why I want to read this novel

Make it compelling and specific."""

            self.expanded_seed = llm_client.chat(
                [{"role": "user", "content": best_option_prompt}],
                system="You are a master story developer. Select the best concept from the options provided and expand it into a detailed document.",
                max_tokens=2000,
            )

        except Exception as e:
            logger.warning(
                f"  Snowflake options failed, falling back to basic expansion: {e}"
            )
            self.expanded_seed = llm_client.chat(
                [
                    {
                        "role": "user",
                        "content": f"""Expand this story seed into a 600-900 word concept document.

SEED: {self.seed}
{f"REQUIRED ENDING: {self.actual_ending}" if self.actual_ending else ""}

Include: protagonist (wound, want vs need), world hook, central conflict, tone/genre,
thematic core, 4-5 key relationships, antagonist (believes they're right),
opening image, closing image.

Make me WANT to read this novel.""",
                    }
                ],
                system="You are a master story developer. Write a compelling expansion.",
                max_tokens=1500,
            )

        # Store expanded seed in vector DB for retrieval during later phases
        self.vector_mem.store_world_entity(
            "Expanded Seed",
            "concept",
            self.expanded_seed,
            "seed",
            {"full_text": self.expanded_seed},
        )

        self._save(
            "expanded_seed.md",
            f"# Seed\n{self.seed}\n\n# Expanded\n{self.expanded_seed}",
        )
        logger.info(f"Seed expanded: {len(self.expanded_seed)} chars")
        self.emit(
            "phase_complete",
            {"phase": "expand_seed", "length": len(self.expanded_seed)},
        )

    # ═══ PHASE 2: World Generation + Vector Storage + Validation ═══

    def generate_world(self):
        self.state = "generating_world"
        logger.info("═══ PHASE 2: Generating world ═══")
        self.emit(
            "phase_start",
            {"phase": "generate_world", "description": "Building world layer by layer"},
        )
        validator = CoherenceValidator(self.graph_builder, self.project_id)
        seed_ctx = f"{self.seed}\n\n{self.expanded_seed}"
        all_entities = []
        etype_map = {
            "cosmology": "concept",
            "natural_laws": "concept",
            "geography": "place",
            "magic_system": "magic_system",
            "power_system": "magic_system",
            "divine_system": "character",
            "races": "creature",
            "creatures": "creature",
            "flora": "creature",
            "spirits_ghosts": "creature",
            "cultures": "culture",
            "religions": "culture",
            "societies": "culture",
            "languages": "culture",
            "factions": "faction",
            "nations": "faction",
            "economies": "concept",
            "technologies": "concept",
            "wonders": "place",
            "artifacts": "artifact",
            "history": "event",
            "prophecies": "event",
            "characters": "character",
            "conflicts": "event",
            "themes": "concept",
            "story_arcs": "event",
        }

        for phase_idx, phase in enumerate(GENERATION_PHASES):
            for layer in phase:
                logger.info(f"  → Building layer: {layer.value}")
                self.emit(
                    "layer_start",
                    {
                        "layer": layer.value,
                        "phase": phase_idx,
                        "total": len(GENERATION_PHASES),
                    },
                )

                # ── VECTOR-ENHANCED CONTEXT ──
                # Pull semantically relevant entities from ALL previous layers
                vector_context = self.vector_mem.build_context_for_layer_generation(
                    layer.value, seed_ctx, n_results=15
                )

                system, user = build_generation_prompt(layer, seed_ctx, self.world_data)

                # Inject vector context into the prompt
                if vector_context:
                    user = f"{vector_context}\n\n{user}"

                try:
                    # 1. Draft Generation (Rough)
                    self.emit(
                        "draft_stage", {"layer": layer.value, "stage": "Rough Draft"}
                    )
                    draft = llm_client.chat_json(
                        [{"role": "user", "content": user}], system=system
                    )
                    if isinstance(draft, dict) and "items" in draft:
                        draft = draft["items"]
                    elif not isinstance(draft, list):
                        draft = [draft]

                    # 2. Multi-Draft Iteration
                    draft_stages = ["First Draft", "Second Draft", "Final Draft"]

                    for stage in draft_stages:
                        self._check_pause()

                        # Consume any pending injections from the queue
                        pending_injections = ""
                        if self.injection_queue:
                            pending_injections = (
                                "\n\nAUTHOR GOD-MODE INJECTIONS YOU MUST FOLLOW FOR THIS DRAFT:\n"
                                + "\n- ".join(self.injection_queue)
                            )
                            self.injection_queue = []

                        self.emit("draft_stage", {"layer": layer.value, "stage": stage})
                        draft_text = cast(Any, json.dumps(draft, indent=2))[:3000]

                        if self.agents:
                            from app.models.schemas import (
                                SimulationConfig,
                                SimulationSession,
                                AgentPersona,
                                CognitiveProfile,
                                LifeExperience,
                            )
                            from app.services.simulation_engine import SimulationEngine

                            editorial_agents = [
                                AgentPersona(
                                    id="ed_lore",
                                    name="The Lorekeeper",
                                    role="Consistency Editor",
                                    avatar="📚",
                                    personality_summary="A strict entity demanding continuity, world-building depth, and no plot holes.",
                                    backstory="An artificial curator of worlds.",
                                    speech_pattern="Analytical and critical.",
                                    deep_persona="You exist to critique the lore, ensuring physics, politics, and relationships make sense.",
                                    cognitive=CognitiveProfile(
                                        intelligence=180,
                                        education_level="Omniscient",
                                        reasoning_style="Strictly logical",
                                    ),
                                    life=LifeExperience(),
                                ),
                                AgentPersona(
                                    id="ed_pace",
                                    name="The Pacing Architect",
                                    role="Narrative Editor",
                                    avatar="⚡",
                                    personality_summary="Focused heavily on tension, stakes, and narrative momentum.",
                                    backstory="An artificial architect of pacing.",
                                    speech_pattern="Urgent and structural.",
                                    deep_persona="You evaluate if the narrative is moving fast enough, if the stakes are escalating, and if tension remains high.",
                                    cognitive=CognitiveProfile(
                                        intelligence=180,
                                        education_level="Omniscient",
                                        reasoning_style="Structural focus",
                                    ),
                                    life=LifeExperience(),
                                ),
                            ]

                            review_agents = self.agents + editorial_agents

                            cfg = SimulationConfig(
                                project_id=self.project_id,
                                agent_count=len(review_agents),
                                rounds=1,
                                mode=f"review_{layer.value}",
                                prediction_requirement=f"CURRENT {stage.upper()} TARGET ({layer.value}):\n{draft_text}",
                            )
                            session = SimulationSession(
                                project_id=self.project_id,
                                config=cfg,
                                agents=review_agents,
                                knowledge_graph=self.knowledge_graph,
                            )
                            engine = SimulationEngine(
                                session, self.upload_dir, self.graph_builder
                            )
                            engine.vector_mem = self.vector_mem

                            def _intercept(etype, data):
                                if etype == "agent_post":
                                    self.emit("agent_post", data)
                                    self.debate_posts.append(data.get("post"))

                            engine.emit = _intercept
                            self.active_engine = engine
                            engine.run()
                            self.active_engine = None

                            swarm_context = "\n".join(
                                f"[{p.author_name}]: {p.text}" for p in session.posts
                            )
                            if swarm_context or pending_injections:
                                user_synth = f"{user}\n\nAGENTS REVIEWED THE PREVIOUS DRAFT:\n{swarm_context}\n{pending_injections}\nPlease output the improved {stage.upper()} JSON for this layer combining your ideas, agent feedback, and author injections. CRITICAL REQUIREMENT: Remember to generate MULTIPLE entries in the `items` array. DO NOT just generate one."
                                draft = llm_client.chat_json(
                                    [{"role": "user", "content": user_synth}],
                                    system=system,
                                )
                                if isinstance(draft, dict) and "items" in draft:
                                    draft = draft["items"]
                                elif not isinstance(draft, list):
                                    draft = [draft]
                        else:
                            # Self-critique fallback if no agents
                            user_synth = f"{user}\n\nCURRENT DRAFT:\n{draft_text}\n{pending_injections}\nCritique this draft for narrative tension, interconnectedness, and depth. Then output the improved {stage.upper()} JSON. CRITICAL REQUIREMENT: Remember to generate MULTIPLE entries in the `items` array. DO NOT just generate one."
                            draft = llm_client.chat_json(
                                [{"role": "user", "content": user_synth}], system=system
                            )
                            if isinstance(draft, dict) and "items" in draft:
                                draft = draft["items"]
                            elif not isinstance(draft, list):
                                draft = [draft]

                    # Coherence validation + auto-repair
                    result = draft
                    issues = validator.validate_layer(
                        layer.value, result, self.world_data
                    )
                    if issues:
                        self.emit(
                            "coherence_issues",
                            {"layer": layer.value, "count": len(issues)},
                        )
                        result = validator.auto_repair(
                            layer.value, result, issues, seed_ctx, self.world_data
                        )

                    self.world_data[layer.value] = result

                    # ── STORE IN VECTOR DB ──
                    self.vector_mem.store_world_layer(layer.value, result)

                    # Convert to entities + persist to Neo4j
                    etype = EntityType(etype_map.get(layer.value, "concept"))
                    for item in result:
                        name = (
                            item.get("name")
                            or item.get("era_name")
                            or item.get("arc_name")
                            or item.get("theme")
                            or f"{layer.value}_unnamed"
                        )
                        desc_parts = [
                            f"{k}: {v}" for k, v in item.items() if k != "name" and v
                        ]
                        all_entities.append(
                            Entity(
                                name=name,
                                type=etype,
                                description=" | ".join(desc_parts[:4])[:500],
                                properties={"world_layer": layer.value},
                            )
                        )

                    self._persist_layer(layer.value, result, etype)

                    if self.is_god_mode:
                        logger.info(
                            f"  GOD-MODE: Auto-pausing after {layer.value} layer"
                        )
                        self.pause()
                        self.emit(
                            "pipeline_paused",
                            {"reason": f"Review {layer.value}", "auto": True},
                        )
                        self._check_pause()

                    logger.info(
                        f"  ✓ Layer [{layer.value}]: {len(result)} entries — {[i.get('name', '?') for i in result[:4]]}"
                    )
                    self.emit(
                        "layer_complete",
                        {
                            "layer": layer.value,
                            "count": len(result),
                            "names": [i.get("name", "?") for i in result][:8],
                            "vector_store_total": self.vector_mem.get_stats()[
                                "world_entities"
                            ],
                        },
                    )

                except Exception as e:
                    logger.error(f"  ✗ Layer [{layer.value}] failed: {e}")
                    self.emit("layer_error", {"layer": layer.value, "error": str(e)})
                    self.world_data[layer.value] = []

        self.knowledge_graph = KnowledgeGraph(entities=all_entities)
        self.coherence_report = validator.get_report()
        self._save("world_data.json", self.world_data)
        self._save("knowledge_graph.json", self.knowledge_graph.model_dump())
        self._save("coherence_report.json", self.coherence_report)

        self.emit(
            "phase_complete",
            {
                "phase": "world",
                "entities": len(all_entities),
                "layers": len(self.world_data),
                "vector_entities": self.vector_mem.get_stats()["world_entities"],
                "issues_found": self.coherence_report["total_issues"],
                "issues_fixed": self.coherence_report["total_corrections"],
            },
        )

    # ═══ PHASE 2.5: Expansion Check Loop ═══

    def check_expansion_needed(self) -> dict:
        """After world generation, check if we need more content for the target chapter count."""
        self.state = "checking_expansion"
        logger.info("═══ PHASE 2.5: Expansion Check ═══")
        self.emit(
            "phase_start",
            {
                "phase": "expansion_check",
                "description": "Checking if world needs expansion",
            },
        )

        world_summary = self._world_summary(2000)
        entity_count = sum(
            len(items) for items in self.world_data.values() if isinstance(items, list)
        )

        expansion_prompt = f"""Evaluate if this world needs more content for {self.chapter_count} chapters.

CURRENT WORLD:
{world_summary}

CURRENT ENTITY COUNT: {entity_count}

Target: {self.chapter_count} chapters with rich content

Consider:
1. Are there enough factions for sustained conflict?
2. Are there enough character motivations and backstories?
3. Are there mysteries, prophecies, or unresolved threads?
4. Are stakes high enough for {self.chapter_count} chapters?
5. Is the magic system/combat system deep enough?
6. Are there enough secondary characters?
7. Are there subplot hooks?

Return JSON:
{{
  "needs_expansion": true/false,
  "confidence": 0.0-1.0,
  "reason": "why expansion is/isn't needed",
  "recommendations": [
    {{"layer": "layer_name", "add_count": number, "focus": "what to add"}}
  ],
  "priority": "high/medium/low"
}}"""

        try:
            result = llm_client.chat_json(
                [{"role": "user", "content": expansion_prompt}],
                system="You are a world-building consultant. Be honest about what the story needs.",
                max_tokens=2000,
            )
            self._save("expansion_check.json", result)
            logger.info(
                f"  Expansion check: needs={result.get('needs_expansion')}, confidence={result.get('confidence')}"
            )
            self.emit("expansion_check_complete", result)
            return result
        except Exception as e:
            logger.warning(f"  Expansion check failed: {e}")
            return {"needs_expansion": False, "reason": str(e)}

    def expand_world_layers(self, recommendations: list) -> dict:
        """Expand specific world layers based on recommendations."""
        self.state = "expanding_world"
        logger.info("═══ PHASE 2.6: Targeted World Expansion ═══")
        self.emit(
            "phase_start",
            {
                "phase": "expansion",
                "description": "Expanding world based on recommendations",
            },
        )

        expansion_results = []
        validator = CoherenceValidator(self.graph_builder, self.project_id)

        for rec in recommendations:
            layer = rec.get("layer")
            add_count = rec.get("add_count", 5)
            focus = rec.get("focus", "")

            if not layer:
                continue

            logger.info(f"  Expanding {layer}: add {add_count} entries, focus: {focus}")

            # Find the layer enum
            from app.services.world_ontology import WorldLayer, build_generation_prompt

            try:
                layer_enum = WorldLayer(layer)
            except ValueError:
                logger.warning(f"  Unknown layer: {layer}")
                continue

            self.emit(
                "layer_start", {"layer": layer, "reason": "expansion", "focus": focus}
            )

            # Build context
            seed_ctx = f"{self.seed}\n\n{self.expanded_seed}"
            vector_context = self.vector_mem.build_context_for_layer_generation(
                layer, seed_ctx, n_results=10
            )
            system, user = build_generation_prompt(
                layer_enum, seed_ctx, self.world_data
            )

            user = f"GENERATE {add_count} MORE entries for this layer.\nFOCUS: {focus}\n\n{user}"
            if vector_context:
                user = f"{vector_context}\n\n{user}"

            try:
                draft = llm_client.chat_json(
                    [{"role": "user", "content": user}],
                    system=system
                    + "\n\nCRITICAL: Generate EXACTLY the number of entries requested.",
                )

                if isinstance(draft, dict) and "items" in draft:
                    new_items = draft["items"]
                elif isinstance(draft, list):
                    new_items = draft
                else:
                    new_items = []

                # Merge with existing
                existing_names = {
                    item.get("name")
                    for item in self.world_data.get(layer, [])
                    if isinstance(item, dict)
                }
                for item in new_items:
                    if item.get("name") not in existing_names:
                        self.world_data.setdefault(layer, []).append(item)
                        existing_names.add(item.get("name"))

                # Store in vector DB
                self.vector_mem.store_world_layer(layer, new_items)

                expansion_results.append(
                    {"layer": layer, "added": len(new_items), "focus": focus}
                )

                self.emit(
                    "layer_complete",
                    {"layer": layer, "count": len(new_items), "reason": "expansion"},
                )

            except Exception as e:
                logger.error(f"  Expansion failed for {layer}: {e}")
                self.emit("layer_error", {"layer": layer, "error": str(e)})

        self._save("world_data_expanded.json", self.world_data)
        self.emit(
            "phase_complete", {"phase": "expansion", "results": expansion_results}
        )

        return {"expansion_results": expansion_results}

    def _persist_layer(self, layer_name, items, etype):
        if not self.graph_builder or not self.graph_builder.driver:
            return
        pid = self.project_id
        try:
            with self.graph_builder.driver.session() as s:
                for item in items:
                    name = (
                        item.get("name")
                        or item.get("era_name")
                        or item.get("arc_name")
                        or item.get("theme")
                        or "unnamed"
                    )
                    desc = " | ".join(
                        f"{k}: {v}" for k, v in item.items() if k != "name" and v
                    )[:400]
                    s.run(
                        "MERGE (n:Entity {name:$name, project_id:$pid}) SET n.type=$t, n.description=$d, n.world_layer=$l",
                        name=name,
                        pid=pid,
                        t=etype.value,
                        d=desc,
                        l=layer_name,
                    )
                    text = json.dumps(item).lower()
                    existing = s.run(
                        "MATCH (e:Entity {project_id:$pid}) WHERE e.name <> $name RETURN e.name as n",
                        pid=pid,
                        name=name,
                    )
                    for rec in existing:
                        if rec["n"].lower() in text:
                            s.run(
                                "MATCH (a:Entity {name:$a,project_id:$pid}) MATCH (b:Entity {name:$b,project_id:$pid}) MERGE (a)-[:REFERENCES {layer:$l}]->(b)",
                                a=name,
                                b=rec["n"],
                                pid=pid,
                                l=layer_name,
                            )
        except Exception as e:
            print(f"[Pipeline] Neo4j error: {e}")

    # ═══ PHASE 3: Agent Debate (with vector-enhanced context) ═══

    def run_debate(self):
        self.state = "debating"
        logger.info("═══ PHASE 3: Agent Debate ═══")
        self.emit(
            "phase_start",
            {"phase": "debate", "description": "Agents debating the world"},
        )

        # Spawn new agents to join early critics, filling out roster with in-world agents
        new_count = max(0, self.agent_count - len(self.agents))
        if new_count > 0:
            logger.info(f"  Spawning {new_count} additional agents...")
            new_agents = generate_personas(
                self.knowledge_graph,
                count=new_count,
                critics_ratio=0.1,
                graph_builder=self.graph_builder,
                project_id=self.project_id,
            )
            self.agents.extend(new_agents)
            self.emit(
                "agents_spawned",
                {
                    "count": len(new_agents), 
                    "names": [a.name for a in new_agents],
                    "agents": [a.model_dump() for a in self.agents]
                },
            )

        logger.info(
            f"  Total agents in debate: {len(self.agents)} | Rounds: {self.debate_rounds}"
        )

        world_summary = self._world_summary()
        config = SimulationConfig(
            project_id=self.project_id,
            agent_count=len(self.agents),
            rounds=self.debate_rounds,
            mode="outline",
            prediction_requirement=f"SEED:\n{self.seed}\n\nCONCEPT:\n{self.expanded_seed}\n\nWORLD:\n{world_summary}",
        )
        session = SimulationSession(
            project_id=self.project_id,
            config=config,
            agents=self.agents,
            knowledge_graph=self.knowledge_graph,
        )

        from app.services.simulation_engine import SimulationEngine

        engine = SimulationEngine(session, self.upload_dir, self.graph_builder)

        # Pass vector memory to the engine so agents can use semantic retrieval
        engine.vector_mem = self.vector_mem

        # Forward ALL engine events to the pipeline's SSE subscribers so the
        # frontend sees debate posts, round progress, memory formations, etc.
        _pipe = self

        def _forward(etype, data):
            _pipe.emit(etype, data)

        engine.emit = _forward

        self.active_engine = engine
        engine.run()
        self.active_engine = None
        logger.info(f"  Debate complete: {len(session.posts)} posts")

        # Store all debate posts in vector DB
        for post in session.posts:
            if not post.is_injection:
                self.vector_mem.store_post(
                    post.id,
                    post.author_name,
                    post.action.value,
                    post.text,
                    post.round,
                    post.platform.value,
                )

        self._last_debate_session_id = session.id
        self.debate_posts = [p.model_dump() for p in session.posts]
        self._save("debate_posts.json", self.debate_posts)

        self.emit(
            "phase_complete",
            {
                "phase": "debate",
                "posts": len(self.debate_posts),
                "vector_posts": self.vector_mem.get_stats()["simulation_posts"],
                "promotions": [p.model_dump() for p in session.character_promotions],
            },
        )

    def _world_summary(self, max_len=5000):
        lines = []
        for layer, items in self.world_data.items():
            if not items:
                continue
            lines.append(f"\n[{layer.upper()}]")
            for item in (items if isinstance(items, list) else [items])[:5]:
                if isinstance(item, dict):
                    n = (
                        item.get("name")
                        or item.get("era_name")
                        or item.get("theme")
                        or "?"
                    )
                else:
                    n = str(item)

                if isinstance(item, dict):
                    details = [
                        f"{k}: {str(v)[:80]}"
                        for k, v in item.items()
                        if k != "name" and v
                    ][:3]
                    lines.append(f"  {n}: {' | '.join(details)}")
                else:
                    lines.append(f"  {n}")
        return "\n".join(lines)[:max_len]

    # ═══ PHASE 4: Deep Outline (with vector-enhanced per-chapter context) ═══

    def generate_outline(self):
        self.state = "outlining"
        logger.info("═══ PHASE 4: Generating outline ═══")
        self.emit(
            "phase_start",
            {"phase": "outline", "description": "Generating deep chapter outline"},
        )

        key_actions = {
            "synthesize",
            "outline",
            "theme",
            "foreshadow",
            "characterize",
            "conflict",
            "resolve",
        }
        highlights = [
            p
            for p in self.debate_posts
            if p.get("action") in key_actions and not p.get("is_injection")
        ]
        if not highlights:
            highlights = cast(Any, self.debate_posts)[-20:]
        debate_text = "\n\n".join(
            f"[{p.get('author_name')}|{p.get('action')}]: {cast(Any, p.get('text', ''))[:250]}"
            for p in cast(Any, highlights)[:20]
        )

        # Extract in-world physical simulation events (including new InWorld actions)
        inworld_actions = {
            # Basic actions
            "move",
            "fight",
            "flee",
            "use_item",
            "give_item",
            "take_item",
            "discover",
            "destroy",
            "create",
            "sabotage",
            "heal",
            "cast_spell",
            "steal",
            "hide",
            "wait",
            # NEW: Character actions
            "speak",
            "act",
            "gather_intel",
            "kiss",
            "hug",
            "appreciate",
            "praise",
            "cry",
            "attack",
            "kill",
            "betray",
            "react",
            # NEW: Strategist actions
            "initiate_conflict",
            "form_alliance",
            "deploy_resources",
            "scheme",
            "wage_war",
            "assassinate",
            "negotiate",
            # NEW: Historian actions
            "record_lore",
            "uncover_secret",
            "prophesy",
            "chronicle",
            "mourn_loss",
            "celebrate_triumph",
            # NEW: Critic InWorld actions
            "audit_narrative",
            "thematic_intervention",
            "structural_shift",
            "praise_development",
            "criticize_action",
            # NEW: Arc Planner InWorld actions
            "trigger_transformation",
            "create_dilemma",
            "emotional_catalyst",
            "force_breakthrough",
            "orchestrate_tragedy",
        }
        sim_events = [
            p
            for p in self.debate_posts
            if p.get("action") in inworld_actions and not p.get("is_injection")
        ]
        sim_events_text = "\n".join(
            f"- {p.get('author_name')} ({p.get('action')}): {p.get('text', '')[:200]}"
            for p in sim_events
        )

        characters = self.world_data.get("characters", [])
        arcs = self.world_data.get("story_arcs", [])

        # Merge agents into the character list for the outliner
        # This ensures agents created/promoted during the simulation appear in the story
        all_chars = list(characters)
        agent_names = {c.get("name") for c in all_chars}

        # Add agents as characters if not already present
        for agent in self.agents:
            if agent.name not in agent_names:
                all_chars.append(
                    {
                        "name": agent.name,
                        "role": agent.role,
                        "personality": agent.personality_summary,
                        "backstory": agent.backstory,
                        "is_agent": True,
                    }
                )

        self.active_outliner = DeepOutliner(
            seed=self.seed,
            expanded_seed=self.expanded_seed,
            world_data=self.world_data,
            debate_highlights=debate_text,
            characters=all_chars,
            arcs=arcs,
            simulation_events=sim_events_text,
            chapter_count=self.chapter_count,
            actual_ending=self.actual_ending,
            genres=self.genres,
            pacing=self.pacing,
            mood=self.mood,
            graph_builder=self.graph_builder,
            project_id=self.project_id,
        )
        self.active_outliner.vector_mem = self.vector_mem

        logger.info("  Generating Story Spine for review...")
        self.emit(
            "phase_start",
            {"phase": "spine", "description": "Generating Story Spine for your review"},
        )
        spine = self.active_outliner.generate_spine(emit_fn=self.emit)
        self.outline_data["spine"] = spine
        self._save("spine.json", spine)

        self.state = "waiting_for_review"
        logger.info("  Pipeline PAUSED for spine review.")
        self.emit("phase_waiting", {"phase": "spine_review", "spine": spine})

    # ═══ FULL PIPELINE ═══

    def run(self):
        try:
            self.state = "running"
            logger.info(
                f"═══ PIPELINE START | project={self.project_id} | agents={self.agent_count} | rounds={self.debate_rounds} ═══"
            )
            self.emit(
                "pipeline_start", {"seed": self.seed, "project_id": self.project_id}
            )
            self.expand_seed()

            # --- MIROFISH EARLY SPAWN ---
            logger.info("  Spawning early critic panel...")
            self.emit(
                "phase_start",
                {
                    "phase": "spawn_agents",
                    "description": "Gathering early critic panel",
                },
            )
            self.agents = generate_personas(
                self.knowledge_graph,
                count=min(6, self.agent_count),
                critics_ratio=1.0,
                graph_builder=self.graph_builder,
                project_id=self.project_id,
            )
            logger.info(f"  Early critics spawned: {[a.name for a in self.agents]}")
            self.emit(
                "agents_spawned",
                {
                    "count": len(self.agents), 
                    "names": [a.name for a in self.agents],
                    "agents": [a.model_dump() for a in self.agents]
                },
            )

            self.generate_world()

            # --- EXPANSION CHECK LOOP ---
            expansion_result = self.check_expansion_needed()
            if expansion_result.get("needs_expansion"):
                recommendations = expansion_result.get("recommendations", [])
                if recommendations:
                    logger.info(f"  Expanding world based on recommendations...")
                    self.expand_world_layers(recommendations)

            self.run_debate()

            # --- RELATIONSHIP SYNC ---
            if self.graph_builder and hasattr(self, "_last_debate_session_id"):
                sim_db = os.path.join(
                    self.upload_dir,
                    "simulations",
                    self._last_debate_session_id,
                    "agent_memory.db",
                )
                self.graph_builder.sync_agent_relationships(self.project_id, sim_db)

            self.generate_outline()
            # If generating_outline pauses, run() finishes here.
            # resume_after_review() will pick up and call generate_pov_prose().

            # If it didn't pause (e.g. error or skip), we might handle it here,
            # but usually it pauses.
        except Exception as e:
            self.state = "error"
            self.error = str(e)
            logger.exception(f"Pipeline error: {e}")
            self.emit("pipeline_error", {"error": str(e)})
            raise

    def generate_pov_prose(self):
        """Phase 5: Generate first-person prose from the most reactive agent."""
        self.state = "generating_prose"
        logger.info("═══ PHASE 5: Writing POV prose ═══")
        self.emit(
            "phase_start",
            {
                "phase": "pov_prose",
                "description": "Writing Chapter 1 from the most reactive agent's POV",
            },
        )

        outliner = DeepOutliner(
            seed=self.seed,
            expanded_seed=self.expanded_seed,
            world_data=self.world_data,
            debate_highlights="",
            characters=self.world_data.get("characters", []),
            arcs=self.world_data.get("story_arcs", []),
        )
        # Copy over the already-generated chapters so POV chapter has context
        outliner.chapters = self.outline_data.get("chapters", [])
        outliner.spine = self.outline_data.get("spine", {})

        def progress(msg, cur, total):
            self.emit(
                "outline_progress", {"message": msg, "current": cur, "total": total}
            )

        prose = outliner.generate_pov_chapter(
            agents=self.agents, progress_callback=progress
        )
        self.pov_prose = prose

        self._save(
            "pov_chapter_1.md",
            f"# Chapter 1 — POV: {outliner.pov_agent_name}\n\n{prose}",
        )
        # Also update the outline markdown to include prose
        self.outline_markdown += f"\n\n---\n\n## First Chapter Draft — POV: {outliner.pov_agent_name}\n\n{prose}"
        self._save("outline.md", self.outline_markdown)

        logger.info(
            f"  POV prose complete: {len(prose.split())} words by {outliner.pov_agent_name}"
        )
        self.emit(
            "phase_complete",
            {
                "phase": "pov_prose",
                "pov_agent": outliner.pov_agent_name,
                "word_count": len(prose.split()),
            },
        )

    def create_snapshot(self, label: str = "") -> dict:
        """Save the full pipeline state so it can be forked later."""
        snap = {
            "label": label or f"snapshot_{int(time.time())}",
            "seed": self.seed,
            "expanded_seed": self.expanded_seed,
            "world_data": self.world_data,
            "debate_posts": self.debate_posts,
            "outline_data": self.outline_data,
            "outline_markdown": self.outline_markdown,
            "pov_prose": self.pov_prose,
            "agents": [a.model_dump() for a in self.agents],
            "knowledge_graph": self.knowledge_graph.model_dump(),
            "state": self.state,
            "project_id": self.project_id,
            "timestamp": time.time(),
        }
        path = os.path.join(self.proj_dir, f"snapshot_{snap['label']}.json")
        with open(path, "w") as f:
            json.dump(snap, f, indent=2, default=str)
        self.snapshots[snap["label"]] = path
        self.emit("snapshot_created", {"label": snap["label"], "path": path})
        return snap

    @classmethod
    def fork_from_snapshot(
        cls,
        snapshot_path: str,
        new_project_id: str,
        graph_builder=None,
        upload_dir="uploads",
    ) -> "StoryPipeline":
        """Create a new pipeline from a snapshot, enabling a branching alternate timeline."""
        with open(snapshot_path) as f:
            snap = json.load(f)

        pipe = cls(
            seed=snap["seed"],
            graph_builder=graph_builder,
            project_id=new_project_id,
            upload_dir=upload_dir,
        )
        pipe.expanded_seed = snap.get("expanded_seed", "")
        pipe.world_data = snap.get("world_data", {})
        pipe.debate_posts = snap.get("debate_posts", [])
        pipe.outline_data = snap.get("outline_data", {})
        pipe.outline_markdown = snap.get("outline_markdown", "")
        pipe.pov_prose = snap.get("pov_prose", "")

        # Reconstruct agents from JSON
        from app.models.schemas import AgentPersona

        pipe.agents = [AgentPersona(**a) for a in snap.get("agents", [])]

        # Reconstruct knowledge graph
        pipe.knowledge_graph = KnowledgeGraph(**snap.get("knowledge_graph", {}))

        pipe.parent_project_id = snap.get("project_id", "")
        pipe.state = "forked"

        # Persist the forked state
        pipe._save("world_data.json", pipe.world_data)
        pipe._save(
            "expanded_seed.md",
            f"# Seed\n{pipe.seed}\n\n# (Forked from {pipe.parent_project_id})\n\n{pipe.expanded_seed}",
        )
        pipe.emit(
            "pipeline_forked",
            {
                "from_project": pipe.parent_project_id,
                "new_project": new_project_id,
            },
        )
        return pipe

    def resume_after_review(self, approved_spine: list):
        """Resume the pipeline after the user approves/edits the story spine."""
        if self.state != "waiting_for_review" or not self.active_outliner:
            return False

        self.state = "outlining"
        logger.info("═══ Resuming Pipeline: Generating Full Outline ═══")
        self.emit(
            "phase_start",
            {"phase": "outline", "description": "Generating detailed chapter outline"},
        )

        assert self.active_outliner is not None
        self.active_outliner.spine = approved_spine
        self.outline_data["spine"] = approved_spine

        def progress(msg, current, total):
            self.emit(
                "outline_progress", {"message": msg, "current": current, "total": total}
            )

        # Continue with full generation — skip_spine=True so the approved spine isn't overwritten
        self.outline_data = self.active_outliner.generate_full(
            progress_callback=progress, skip_spine=True
        )
        self.outline_markdown = self.active_outliner.to_markdown()

        # Store outline chapters in vector DB
        for ch in self.outline_data.get("chapters", []):
            assert isinstance(ch, dict)
            ch_text = json.dumps(ch, default=str)[:1500]
            self.vector_mem.store_outline_chunk(
                f"ch_{ch.get('chapter', 0)}", ch.get("chapter", 0), ch_text, "chapter"
            )

        self._save("outline.json", self.outline_data)
        self._save("outline.md", self.outline_markdown)

        logger.info(
            f"  Outline complete: {self.outline_data.get('total_chapters', 0)} chapters"
        )
        self.emit(
            "phase_complete",
            {
                "phase": "outline",
                "chapters": self.outline_data.get("total_chapters", 0),
                "deepened": self.outline_data.get("deepened_chapters", 0),
                "arc_issues": len(self.outline_data.get("arc_issues", [])),
                "vector_stats": self.vector_mem.get_stats(),
            },
        )

        # Final phases
        self.generate_pov_prose()
        self.state = "completed"
        self._finalize_pipeline()
        return True

    def _finalize_pipeline(self):
        logger.info("═══ PIPELINE COMPLETE ═══")
        stats = self.vector_mem.get_stats()
        self.emit(
            "pipeline_complete",
            {
                "world_layers": len(self.world_data),
                "entities": len(self.knowledge_graph.entities),
                "debate_posts": len(self.debate_posts),
                "chapters": self.outline_data.get("total_chapters", 0),
                "vector_stats": stats,
                "coherence_issues_found": self.coherence_report.get("total_issues", 0),
                "coherence_issues_fixed": self.coherence_report.get(
                    "total_corrections", 0
                ),
            },
        )
        self._save(
            "pipeline_result.json",
            {
                "seed": self.seed,
                "state": "completed",
                "world_layers": list(self.world_data.keys()),
                "entity_count": len(self.knowledge_graph.entities),
                "debate_posts": len(self.debate_posts),
                "chapters": self.outline_data.get("total_chapters", 0),
                "vector_stats": stats,
            },
        )

    def run_async(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t
