"""
Agent Persona Generator v6 — OASIS-Optimized Deep Characterization.

Key improvements:
- DEEP PERSONA: Generates ~1000-2000 word psychological profiles for agents.
- INDIVIDUAL vs GROUP: Distinguishes between person-type entities and abstract institutions.
- ROBUST PARSING: Includes _try_fix_json to handle truncated LLM outputs or minor formatting errors.
- KG ENRICHMENT: Uses Neo4j context to ground personas in world history and relationships.
- PARALLEL: Concurrent generation for large swarms.
"""

from typing import List, Dict, Any, cast, Optional
import random
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import Config
from app.services import llm_client
from app.models.schemas import (
    AgentPersona, KnowledgeGraph, Entity, Platform, Stance, EntityType,
    CognitiveProfile, LifeExperience, LivingMemory, MemoryType,
)

logger = logging.getLogger("novelswarm.persona")

AVATARS: Any = list("🧙⚔📜🌙🔮🗡👁🦅🐉🏰🌿💀⚡🎭📖🕯🗺🛡🪶🌊🔥❄💎🪄👑🧿🎪🌑☀🗝")

# Narrative angles for critics' forum agents
CRITIC_ANGLES = [
    "plot structure", "character psychology", "pacing and tension", "thematic depth",
    "world consistency", "dialogue and voice", "reader experience", "genre conventions",
    "emotional resonance", "foreshadowing and payoff", "political subtext", "power dynamics",
    "moral complexity", "cultural authenticity", "narrative unreliability", "symbolism",
]

# Individual type entities (need to generate specific personas)
INDIVIDUAL_ENTITY_TYPES = ["character", "person", "publicfigure", "expert", "faculty", "official", "journalist", "activist"]

# Group/institutional type entities (need to generate group representative personas)
GROUP_ENTITY_TYPES = ["university", "governmentagency", "organization", "ngo", "mediaoutlet", "company", "institution", "group", "community", "faction", "culture"]

# Crowd archetypes used when generating world-native agents beyond named KG entities.
# These are intentionally generic so the LLM fills them with world-specific details.
CROWD_ARCHETYPES = [
    "common soldier", "traveling merchant", "temple priest/priestess", "village elder",
    "blacksmith", "court scribe", "herbalist/hedge-mage", "city guard",
    "dockworker/sailor", "wandering bard", "rural farmer", "mine worker",
    "innkeeper", "street thief/pickpocket", "noble's servant", "militia recruit",
    "healer/field medic", "spy/informant", "scholar/librarian", "arena fighter/gladiator",
    "hunter/tracker", "cartographer/explorer", "smuggler", "revolutionary agitator",
    "refugee", "orphan turned street-rat", "disgraced knight", "exiled noble",
]

# Maps crowd archetypes to specialized agent roles the adapter can route correctly.
ARCHETYPE_TO_ROLE: dict[str, str] = {
    "common soldier":          "strategist",
    "militia recruit":         "strategist",
    "arena fighter/gladiator": "strategist",
    "disgraced knight":        "strategist",
    "spy/informant":           "strategist",
    "smuggler":                "strategist",
    "revolutionary agitator":  "strategist",
    "hunter/tracker":          "strategist",
    "scholar/librarian":       "historian",
    "cartographer/explorer":   "historian",
    "temple priest/priestess": "historian",
    "village elder":           "historian",
    "wandering bard":          "historian",
    "court scribe":            "historian",
    "herbalist/hedge-mage":    "character_arc_planner",
    "healer/field medic":      "character_arc_planner",
    "exiled noble":            "character_arc_planner",
    "refugee":                 "character_arc_planner",
    "orphan turned street-rat":"character_arc_planner",
}

# ─────────────────────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

_JSON_SCHEMA = """{
    "name": "Their actual name (use THIS world's naming conventions)",
    "age": 35,
    "race": "a race that EXISTS in this world",
    "gender": "male/female/nonbinary/other",
    "personality_summary": "2-3 vivid sentences — WHO this person IS, not a trait list",
    "personality_traits": ["trait1", "trait2", "trait3", "trait4"],
    "speech_pattern": "How they actually talk — dialect, rhythm, vocabulary level",
    "catchphrase": "Something they'd actually say repeatedly",
    "quirks": ["specific habit 1", "specific habit 2"],
    "expertise": ["domain1", "domain2"],
    "backstory": "3-4 sentences explaining WHY they are who they are",
    "deep_persona": "A 1000-2000 word high-detail character profile. Include sections: Basic Info, Personal Background, Personality Traits, Social Media Behavior, Positions & Views, Unique Features, and Personal Memories. Show internal contradictions and deep grounding in the world context.",
    "mbti": "INTJ",
    "country": "Nation/Region name from world context",
    "profession": "Specific role name",
    "interested_topics": ["topic1", "topic2"],
    "cognitive": {
        "intelligence": 100,
        "education_level": "basic|educated|scholar|illiterate|genius_autodidact",
        "worldly_exposure": "sheltered|local|traveled|cosmopolitan|otherworldly",
        "reasoning_style": "intuitive|analytical|emotional|dogmatic|creative|strategic",
        "attention_span": "scattered|normal|focused|obsessive",
        "communication_style": "crude|plain|eloquent|flowery|cryptic|academic|street",
        "literacy": true,
        "speaks_in": "description of accent/dialect",
        "cognitive_biases": ["specific bias 1", "specific bias 2"],
        "blind_spots": ["topic they cannot see clearly"]
    },
    "emotional_ties": {
        "loves": ["name of person they love"],
        "hates": ["name of person they hate or rival"],
        "loyal_to": ["faction or person they serve blindly"]
    },
    "life": {
        "formative_event": "The specific event that shaped them",
        "greatest_achievement": "What they're proud of",
        "deepest_wound": "What still hurts",
        "social_class_origin": "destitute|common|merchant|noble|royal|outcast",
        "current_social_position": "Where they are now",
        "has_killed": false,
        "has_been_betrayed": false,
        "has_loved_and_lost": false,
        "years_of_experience": 10,
        "traveled_places": ["place1"],
        "languages_spoken": ["Common"],
        "mentors": ["name"],
        "enemies_made": ["name"]
    },
    "behavioral_params": {
        "influence": 0.5,
        "reaction_speed": 0.5,
        "susceptibility": 0.3,
        "creativity": 0.5,
        "contentiousness": 0.3
    }
}"""

PERSONA_GENERATION_PROMPT = """Generate a DEEPLY characterized agent persona for a novel-writing swarm simulation.

This agent is grounded in: {entity_context}

WORLD CONTEXT:
{graph_context}

RULES:
1. This must feel like a REAL PERSON from THIS SPECIFIC WORLD — not a generic archetype.
2. If the entity is a GROUP or INSTITUTION (e.g., a Faction or University), generate a persona for a REPROSENTATIVE or a specific high-ranking member who speaks for that group.
3. IQ ranges from 70-160. Cognitive biases must be SPECIFIC.
4. Speech patterns must be DISTINCT. 
5. The deep_persona field should consume ~1500 words and be a "master file" for this character's psyche.
6. Determine specific interpersonal drama based on the provided world context.

Return ONLY valid JSON:
{schema}"""

INWORLD_ARCHETYPE_PROMPT = """Generate a world-native character for a swarm simulation set in this fictional world.

ARCHETYPE TO FILL: {archetype}

ANCHOR ENTITY (inspiration): {entity_context}

WORLD CONTEXT:
{graph_context}

CRITICAL RULES:
1. This character IS A NATIVE of this specific world.
2. Their race, naming, and role MUST be world-appropriate.
3. deep_persona should be a massive, detailed psychological profile.
4. Avoid modern concepts unless explicitly defined in the world context.

Return ONLY valid JSON:
{schema}"""


# ─────────────────────────────────────────────────────────────────────────────
# JSON FIXING UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _fix_truncated_json(content: str) -> str:
    """Fix truncated JSON (output truncated by max_tokens limit)"""
    open_braces = content.count('{') - content.count('}')
    open_brackets = content.count('[') - content.count(']')
    stripped = content.strip()
    if stripped and stripped[-1] not in '",}]':
        if not stripped.endswith('"'):
            content += '"'
    content += ']' * max(0, open_brackets)
    content += '}' * max(0, open_braces)
    return content


def _try_fix_json(content: str, fallback_name: str, fallback_type: str) -> dict:
    """Try to fix corrupted JSON or extract fields via regex."""
    # 1. Try to fix truncated case
    fixed_content = _fix_truncated_json(content)
    try:
        return json.loads(fixed_content)
    except:
        pass

    # 2. Try to extract JSON portion
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass

    # 3. Last-ditch regex extraction
    bio_match = re.search(r'"personality_summary"\s*:\s*"([^"]*)"', content)
    persona_match = re.search(r'"deep_persona"\s*:\s*"((?:[^"\\]|\\.)*)', content)
    
    return {
        "name": fallback_name,
        "personality_summary": bio_match.group(1) if bio_match else f"{fallback_type}: {fallback_name}",
        "deep_persona": persona_match.group(1) if persona_match else "",
        "backstory": "Character from the world of NovelSwarm.",
        "_fixed": True
    }


# ─────────────────────────────────────────────────────────────────────────────
# KG ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyze_knowledge_graph(kg: KnowledgeGraph) -> dict:
    """Analyze the KG to determine agent composition."""
    characters = [e for e in kg.entities if e.type == EntityType.CHARACTER]
    factions   = [e for e in kg.entities if e.type == EntityType.FACTION]
    total = len(kg.entities)
    rels  = len(kg.relationships)

    complexity = "simple"
    if total > 30 or rels > 40: complexity = "complex"
    elif total > 15 or rels > 20: complexity = "moderate"

    recommended = {
        "simple":   max(6,  min(max(4, len(characters)), 24)),
        "moderate": max(10, min(max(4, len(characters)) + 6, 32)),
        "complex":  max(14, min(max(4, len(characters)) + 8, 50)),
    }[complexity]

    return {
        "complexity": complexity,
        "characters": characters,
        "factions": factions,
        "all_entities": kg.entities,
        "recommended_count": recommended,
        "theme_angles": cast(Any, list(CRITIC_ANGLES))[:10],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CORE GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _build_world_context(all_entities: list) -> str:
    lines = []
    for e in cast(Any, all_entities)[:40]:
        desc = str(e.description or "")
        lines.append(f"- {e.name} ({e.type.value}): {cast(Any, desc)[:120]}")
    return "\n".join(lines)


def _get_graph_context(graph_builder, project_id: str, entity_name: str) -> tuple[str, dict]:
    if not graph_builder or not project_id or not entity_name:
        return "", {}
    try:
        ctx = graph_builder.query_agent_full_context(project_id, entity_name)
        text = "\n".join(ctx.get("all_rels", [])[:15])
        return text, ctx
    except Exception:
        return "", {}


def _parse_agent_from_llm(text: str, entity, platform: Platform, role: str, idx: int,
                          graph_ctx_struct: dict | None = None) -> AgentPersona:
    name = entity.name if entity else f"Agent-{idx+1}"
    
    try:
        data = _try_fix_json(text, name, role)
    except Exception as e:
        logger.warning(f"JSON parse totally failed for {name}: {e}")
        return _fallback_agent(entity, platform, role, idx)

    cog  = data.get("cognitive", {})
    life = data.get("life", {})
    par  = data.get("behavioral_params", {})
    formative = life.get("formative_event", "")
    wound = life.get("deepest_wound", "")

    emotional_ties = data.get("emotional_ties", {})
    known_allies   = list(emotional_ties.get("loves", []))
    known_enemies  = list(emotional_ties.get("hates", []))
    loyal_to       = emotional_ties.get("loyal_to", [])
    known_locations: list[str] = []
    known_artifacts: list[str] = []

    if graph_ctx_struct:
        known_allies.extend(list(graph_ctx_struct.get("allies", [])))
        known_enemies.extend(list(graph_ctx_struct.get("enemies", [])))
        known_locations = cast(Any, list(graph_ctx_struct.get("locations", [])))[:5]
        known_artifacts = cast(Any, list(graph_ctx_struct.get("artifacts", [])))[:3]
        factions = [f.split(" (")[0] for f in cast(Any, graph_ctx_struct.get("factions", []))]
        if factions and not loyal_to:
            loyal_to = cast(Any, factions)[:1]

    faction_membership = loyal_to[0] if loyal_to else None

    n_allies, n_enemies = len(set(known_allies)), len(set(known_enemies))
    if n_enemies > n_allies + 1: stance = random.choice([Stance.NEGATIVE, Stance.STRONGLY_NEGATIVE])
    elif n_allies > n_enemies + 1: stance = random.choice([Stance.POSITIVE, Stance.STRONGLY_POSITIVE])
    else: stance = random.choice(list(Stance))

    memories: list[LivingMemory] = []
    if wound:
        memories.append(LivingMemory(
            type=MemoryType.SCAR, source_round=0, trigger=wound, intensity=0.7,
            description=f"Deep wound: {wound}",
            behavioral_effect="Respond with raw vulnerability or sudden anger when this is touched.",
        ))
    if formative:
        memories.append(LivingMemory(
            type=MemoryType.TRAUMA, source_round=0, trigger=formative, intensity=0.6,
            description=f"Shaped by: {formative}",
            behavioral_effect="Colors judgment about power and loyalty.",
        ))
    if life.get("has_loved_and_lost"):
        memories.append(LivingMemory(
            type=MemoryType.SCAR, source_round=0, trigger="loss", intensity=0.55,
            description="Loved and lost — grief colors connections",
            behavioral_effect="Withdraws from emotional intimacy.",
        ))

    return AgentPersona(
        name=str(data.get("name", name)),
        avatar=random.choice(AVATARS),
        age=int(data.get("age", random.randint(18, 70))),
        race=str(data.get("race", "human")),
        gender=str(data.get("gender", "unknown")),
        role=role,
        platform=platform,
        personality_traits=cast(Any, data.get("personality_traits", []))[:6],
        personality_summary=str(data.get("personality_summary") or data.get("bio") or ""),
        backstory=str(data.get("backstory", "")),
        deep_persona=str(data.get("deep_persona", "")),
        expertise=cast(Any, data.get("expertise", []))[:4],
        speech_pattern=str(data.get("speech_pattern", "")),
        catchphrase=str(data.get("catchphrase", "")),
        quirks=cast(Any, data.get("quirks", []))[:3],
        mbti=data.get("mbti"),
        country=data.get("country"),
        profession=data.get("profession"),
        interested_topics=cast(Any, data.get("interested_topics", []))[:10],
        cognitive=CognitiveProfile(
            intelligence=int(cog.get("intelligence", 100)),
            education_level=cog.get("education_level", "average"),
            worldly_exposure=cog.get("worldly_exposure", "local"),
            reasoning_style=cog.get("reasoning_style", "balanced"),
            attention_span=cog.get("attention_span", "normal"),
            communication_style=cog.get("communication_style", "plain"),
            literacy=cog.get("literacy", True),
            speaks_in=cog.get("speaks_in", ""),
            cognitive_biases=cog.get("cognitive_biases", []),
            blind_spots=cog.get("blind_spots", []),
        ),
        life=LifeExperience(
            formative_event=formative or "",
            greatest_achievement=life.get("greatest_achievement", ""),
            deepest_wound=wound or "",
            social_class_origin=life.get("social_class_origin", "common"),
            current_social_position=life.get("current_social_position", ""),
            has_killed=life.get("has_killed", False),
            has_been_betrayed=life.get("has_been_betrayed", False),
            has_loved_and_lost=life.get("has_loved_and_lost", False),
            years_of_experience=int(life.get("years_of_experience", 5)),
            traveled_places=life.get("traveled_places", []),
            languages_spoken=life.get("languages_spoken", []),
            mentors=life.get("mentors", []),
            enemies_made=life.get("enemies_made", []),
        ),
        grounded_entity=entity.name if entity else None,
        known_allies=cast(Any, list(dict.fromkeys(known_allies)))[:5],
        known_enemies=cast(Any, list(dict.fromkeys(known_enemies)))[:5],
        known_locations=known_locations,
        known_artifacts=known_artifacts,
        faction_membership=faction_membership,
        living_memories=memories,
        influence_level=float(par.get("influence", 0.5)),
        reaction_speed=float(par.get("reaction_speed", 0.5)),
        susceptibility=float(par.get("susceptibility", 0.3)),
        creativity=float(par.get("creativity", 0.5)),
        contentiousness=float(par.get("contentiousness", 0.3)),
        stance=stance,
    )


def _fallback_agent(entity, platform: Platform, role: str, idx: int) -> AgentPersona:
    return AgentPersona(
        name=entity.name if entity else f"Agent-{idx+1}",
        avatar=random.choice(AVATARS),
        role=role,
        platform=platform,
        personality_traits=["pragmatic", "curious"],
        backstory=entity.description if entity else "A person of this world.",
        grounded_entity=entity.name if entity else None,
        cognitive=CognitiveProfile(intelligence=random.randint(85, 130)),
        life=LifeExperience(),
        stance=random.choice(list(Stance)),
    )


def _generate_one(
    idx: int, entity, platform: Platform, role: str,
    world_ctx: str, graph_builder, project_id: str,
    archetype: str = "", inworld_mode: bool = False,
) -> AgentPersona:
    entity_name = entity.name if entity else ""
    entity_ctx = f"{entity.name} ({entity.type.value}): {entity.description}" if entity else "Original world-native character."
    graph_ctx_text, graph_ctx_struct = _get_graph_context(graph_builder, project_id, entity_name)
    
    full_graph = f"{graph_ctx_text}\n\nFULL WORLD:\n{world_ctx}" if graph_ctx_text else world_ctx

    if inworld_mode and archetype:
        prompt_data = {
            "entity_context": entity_ctx,
            "graph_context": full_graph,
            "archetype": archetype,
            "schema": _JSON_SCHEMA
        }
        prompt = INWORLD_ARCHETYPE_PROMPT.format(**prompt_data)
    else:
        prompt_data = {
            "entity_context": entity_ctx + (f"\nNarrative role: {role}" if role else ""),
            "graph_context": full_graph,
            "schema": _JSON_SCHEMA
        }
        prompt = PERSONA_GENERATION_PROMPT.format(**prompt_data)

    try:
        # Use raw chat to get the string, so our robust fixer can handle truncations
        data_text = llm_client.chat(
            [{"role": "user", "content": prompt}],
            system="You create vivid, distinct fictional characters native to the world. Valid JSON only.",
            max_tokens=4096,
            json_mode=True
        )
        agent = _parse_agent_from_llm(data_text, entity, platform, role or archetype or "character", idx, graph_ctx_struct)
        agent.graph_context_summary = graph_ctx_text
        return agent
    except Exception as e:
        logger.warning(f"Generation failed for slot {idx}: {e}")
        return _fallback_agent(entity, platform, role or archetype or "character", idx)


def _seed_inter_agent_memories(agents: list[AgentPersona]) -> None:
    name_to_agent = {a.name: a for a in agents}
    for agent in agents:
        for ally_name in agent.known_allies[:3]:
            target = name_to_agent.get(ally_name)
            if target and target is not agent:
                agent.living_memories.append(LivingMemory(
                    type=MemoryType.BOND, source_round=0, trigger=f"Alliance with {target.name}", target=target.name,
                    intensity=0.6, description=f"Instinctive bond with {target.name}",
                    behavioral_effect=f"You trust and support {target.name}."
                ))
        for enemy_name in agent.known_enemies[:3]:
            target = name_to_agent.get(enemy_name)
            if target and target is not agent:
                agent.living_memories.append(LivingMemory(
                    type=MemoryType.GRUDGE, source_round=0, trigger=f"Enmity with {target.name}", target=target.name,
                    intensity=0.7, description=f"Deep animosity toward {target.name}",
                    behavioral_effect=f"You challenge and undermine {target.name}."
                ))


def generate_personas(kg: KnowledgeGraph, count: int | None = None, critics_ratio: float = 0.5,
                      graph_builder=None, project_id: str | None = None) -> list[AgentPersona]:
    analysis = analyze_knowledge_graph(kg)
    world_ctx = _build_world_context(analysis["all_entities"])
    if not count: count = analysis["recommended_count"]
    
    critics_count = int(count * critics_ratio)
    inworld_count = count - critics_count
    
    tasks = []
    for i in range(critics_count):
        tasks.append(dict(idx=i, entity=analysis["all_entities"][i % len(analysis["all_entities"])] if analysis["all_entities"] else None,
                          platform=Platform.CRITICS_FORUM, role=analysis["theme_angles"][i % len(analysis["theme_angles"])],
                          archetype="", inworld_mode=False))
    
    named_pool = analysis["characters"] + analysis["factions"]
    for i in range(inworld_count):
        slot = critics_count + i
        if named_pool and i < len(named_pool): entity, archetype = named_pool[i], ""
        else:
            entity = named_pool[i % len(named_pool)] if named_pool else None
            archetype = CROWD_ARCHETYPES[i % len(CROWD_ARCHETYPES)]
        tasks.append(dict(idx=slot, entity=entity, platform=Platform.INWORLD_FORUM,
                          role=ARCHETYPE_TO_ROLE.get(archetype, "character"), archetype=archetype, inworld_mode=critics_ratio == 0.0))

    agents = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=max(1, Config.MAX_CONCURRENT_AGENTS)) as pool:
        future_map = {pool.submit(_generate_one, t["idx"], t["entity"], t["platform"], t["role"], world_ctx, graph_builder, project_id or "", t["archetype"], t["inworld_mode"]): i for i, t in enumerate(tasks)}
        for future in as_completed(future_map):
            agents[future_map[future]] = future.result()
            
    final = [a for a in agents if a]
    _seed_inter_agent_memories(final)
    return final
