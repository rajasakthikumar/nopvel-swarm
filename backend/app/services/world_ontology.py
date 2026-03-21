"""
World Ontology v2 — Seed-driven world generation.

Every layer prompt explicitly references the seed and all previously generated layers.
Connection rules enforce that later layers MUST reference earlier ones.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Union, cast


class WorldLayer(str, Enum):
    # Foundation
    COSMOLOGY = "cosmology"
    NATURAL_LAWS = "natural_laws"
    GEOGRAPHY = "geography"
    # Power systems
    MAGIC_SYSTEM = "magic_system"
    POWER_SYSTEM = "power_system"
    DIVINE_SYSTEM = "divine_system"
    # Living world
    RACES = "races"
    CREATURES = "creatures"
    FLORA = "flora"
    SPIRITS_GHOSTS = "spirits_ghosts"
    # Civilization
    CULTURES = "cultures"
    RELIGIONS = "religions"
    SOCIETIES = "societies"
    LANGUAGES = "languages"
    # Organizations
    FACTIONS = "factions"
    NATIONS = "nations"
    ECONOMIES = "economies"
    # Craft & legacy
    TECHNOLOGIES = "technologies"
    WONDERS = "wonders"
    ARTIFACTS = "artifacts"
    # Narrative
    HISTORY = "history"
    PROPHECIES = "prophecies"
    CHARACTERS = "characters"
    CONFLICTS = "conflicts"
    # Meta
    THEMES = "themes"
    STORY_ARCS = "story_arcs"


LAYER_META = {
    WorldLayer.COSMOLOGY: {
        "fields": ["name", "creation_myth", "planes_of_existence", "fundamental_forces", "origin_of_life", "what_happens_after_death"],
        "count": "2-4",
        "must_reference_seed": True,
        "prompt": "Generate the cosmological foundation. Creation myths, planes of existence, fundamental forces. The seed story MUST feel like a natural consequence of this cosmology.",
    },
    WorldLayer.NATURAL_LAWS: {
        "fields": ["name", "description", "how_it_differs_from_reality", "narrative_consequences", "who_exploits_it"],
        "count": "3-5",
        "must_reference_seed": True,
        "prompt": "Define the natural/supernatural laws. What's physically different from our world? How does death work? Souls? Time? These laws MUST enable the seed story's premise.",
    },
    WorldLayer.GEOGRAPHY: {
        "fields": ["name", "type", "climate", "terrain", "resources", "dangers", "notable_features", "who_lives_here", "narrative_role"],
        "count": "5-8",
        "prompt": "Create the geography. Every location must serve the story — as a setting for conflict, a source of power, or a character's homeland. Reference the seed.",
    },
    WorldLayer.MAGIC_SYSTEM: {
        "fields": ["name", "source_of_power", "cost_or_price", "hard_limitations", "types_or_schools", "how_learned", "rarity", "social_perception", "forbidden_arts", "connection_to_cosmology"],
        "count": "2-4",
        "prompt": "Design the magic system(s). Must connect to the cosmology. Must have COSTS and LIMITATIONS that create story tension. The seed's protagonist must have a specific relationship to this magic.",
    },
    WorldLayer.POWER_SYSTEM: {
        "fields": ["name", "ranks_or_stages", "training_method", "breakthrough_conditions", "bottlenecks", "physical_mental_changes", "legendary_peak_power", "how_society_views_each_rank"],
        "count": "1-3",
        "prompt": "Design training/cultivation/advancement systems. How do people get stronger? What are the ranks? What does it cost to advance? How does this intersect with the magic system?",
    },
    WorldLayer.DIVINE_SYSTEM: {
        "fields": ["name", "domain", "personality", "relationship_to_mortals", "blessings_granted", "curses_inflicted", "allied_gods", "enemy_gods", "mortal_lovers_or_champions", "current_status", "worshipper_count"],
        "count": "6-12",
        "prompt": "Create the gods/divine beings. They must have PERSONALITY and AGENDA — not just domains. Their conflicts mirror or cause mortal conflicts. Include divine alliances, bitter divine enemies, and mortal favorites/lovers. At least one must be relevant to the seed story.",
    },
    WorldLayer.RACES: {
        "fields": ["name", "physical_traits", "lifespan", "innate_abilities", "cultural_tendencies", "homeland", "relations_with_other_races", "role_in_the_story_world"],
        "count": "4-7",
        "prompt": "Create the intelligent races/species. Each must have a distinct relationship to magic, to the land, and to power. Inter-racial tensions should create conflict.",
    },
    WorldLayer.CREATURES: {
        "fields": ["name", "type", "habitat", "danger_level_1to10", "abilities", "weaknesses", "uses_to_civilizations", "intelligence_level", "any_cultural_significance"],
        "count": "5-8",
        "prompt": "Create creatures — from common wildlife to legendary horrors. Include beasts people ride, hunt, fear, worship, and ones that guard ancient places.",
    },
    WorldLayer.FLORA: {
        "fields": ["name", "type", "magical_properties", "habitat", "rarity", "uses_in_alchemy_or_medicine", "dangers", "cultural_significance"],
        "count": "4-6",
        "prompt": "Create the plant life — especially those with magical, medicinal, or narrative importance. Poisons, healing herbs, trees that are sacred to religions, flowers tied to prophecies.",
    },
    WorldLayer.SPIRITS_GHOSTS: {
        "fields": ["name", "type", "origin_of_the_spirit", "behavior_pattern", "power_level", "weakness_or_binding_method", "haunted_location", "what_they_want", "danger_to_the_living"],
        "count": "4-6",
        "prompt": "Create the undead, ghosts, ancestral spirits, and supernatural entities. How do the dead persist? What unfinished business traps them? How do the living interact with them? Connect to cosmology and death mechanics.",
    },
    WorldLayer.CULTURES: {
        "fields": ["name", "associated_race_or_nation", "core_values", "customs_and_traditions", "art_and_music", "cuisine", "clothing_style", "taboos", "rites_of_passage", "view_of_outsiders"],
        "count": "4-7",
        "prompt": "Create cultures — living, breathing ways of life. Each must feel distinct. Their values should create tension when cultures clash. Reference existing races, geography, religions.",
    },
    WorldLayer.RELIGIONS: {
        "fields": ["name", "deity_or_philosophy_worshipped", "core_doctrine", "rituals_and_practices", "clergy_hierarchy", "sacred_texts", "heresies", "holy_sites", "political_power", "stance_on_magic"],
        "count": "3-6",
        "prompt": "Create organized religions and philosophical traditions. They must relate to the divine system but can MISinterpret the gods. Include internal schisms and inter-faith conflicts.",
    },
    WorldLayer.SOCIETIES: {
        "fields": ["name", "governance_type", "social_classes", "how_class_is_determined", "justice_system", "gender_dynamics", "education_system", "military_structure", "what_outsiders_think"],
        "count": "3-5",
        "prompt": "Design social structures. Who has power? How is it maintained? What injustices exist that could drive a story? Reference existing nations, cultures, races.",
    },
    WorldLayer.LANGUAGES: {
        "fields": ["name", "spoken_by", "script_type", "sample_words_and_meanings", "naming_conventions_for_people", "naming_conventions_for_places", "related_languages"],
        "count": "3-5",
        "prompt": "Create languages. Focus on naming conventions — how people and places are named reveals culture. Include sample words that could appear in the story. Each race/nation should have linguistic identity.",
    },
    WorldLayer.FACTIONS: {
        "fields": ["name", "purpose", "leader", "membership_requirements", "resources_and_power", "allied_factions", "rival_factions", "secrets", "public_reputation", "role_in_current_conflicts"],
        "count": "8-12",
        "prompt": "Create organizations that drive the plot — guilds, knightly orders, spy networks, criminal syndicates, revolutionary movements, ancient brotherhoods. Each must have SECRETS, deep-seated alliances, and blood-feud enemies.",
    },
    WorldLayer.NATIONS: {
        "fields": ["name", "government_type", "ruler", "capital_city", "territory_description", "military_strength", "economic_base", "key_allies", "key_enemies", "internal_problems", "what_they_want"],
        "count": "4-7",
        "prompt": "Create political entities. Each nation must WANT something and be in conflict with at least one other. Internal tensions are as important as external ones.",
    },
    WorldLayer.ECONOMIES: {
        "fields": ["name", "primary_currency", "major_exports", "major_imports", "wealth_distribution", "trade_routes", "black_market_goods", "economic_tensions"],
        "count": "3-5",
        "prompt": "Design economic systems. What resources are scarce? Who controls trade? What's smuggled? Economic power drives political power — connect to nations and factions.",
    },
    WorldLayer.TECHNOLOGIES: {
        "fields": ["name", "description", "who_invented_it", "who_controls_it", "military_applications", "civilian_applications", "limitations", "relationship_to_magic"],
        "count": "4-6",
        "prompt": "Define the technology level and unique inventions. Magitech? Alchemy? Clockwork? What exists that our world doesn't? What's banned? Technology vs magic tension.",
    },
    WorldLayer.WONDERS: {
        "fields": ["name", "type", "builder", "age", "original_purpose", "current_state", "legends_about_it", "location", "who_controls_it_now", "hidden_secrets"],
        "count": "4-7",
        "prompt": "Create world wonders — massive structures, ancient ruins, natural phenomena, monuments. Each should have a mystery, a history, and narrative potential. Some should be lost, some contested.",
    },
    WorldLayer.ARTIFACTS: {
        "fields": ["name", "type", "creator", "power_description", "cost_of_use", "current_location_or_holder", "history_of_owners", "legend", "who_seeks_it", "can_it_be_destroyed"],
        "count": "5-8",
        "prompt": "Create legendary items — weapons, relics, cursed objects, royal regalia, keys to sealed places. Each must be WANTED by someone and DANGEROUS to use. At least one should be central to the seed story.",
    },
    WorldLayer.HISTORY: {
        "fields": ["era_name", "approximate_duration", "defining_events", "major_figures", "how_it_ended", "lasting_consequences", "what_was_lost", "what_legends_remain"],
        "count": "4-7",
        "prompt": "Create the historical timeline — ages, eras, cataclysms, golden periods, dark ages. History must explain WHY the current world is the way it is. The seed story should be a consequence of historical events.",
    },
    WorldLayer.PROPHECIES: {
        "fields": ["name", "source_or_prophet", "prophecy_text", "common_interpretation", "hidden_true_meaning", "conditions_for_fulfillment", "who_it_concerns", "current_status"],
        "count": "3-5",
        "prompt": "Create prophecies that drive the narrative. They should be AMBIGUOUS — multiple valid interpretations. At least one must directly concern the seed story's protagonist. Include prophecies that are WRONG or MISINTERPRETED.",
    },
    WorldLayer.CHARACTERS: {
        "fields": ["name", "age", "race", "role_in_story", "abilities", "personality_traits", "deepest_motivation", "dark_secret", "allies_and_friends", "romantic_interests", "rivals_and_enemies", "character_arc_summary"],
        "count": "15-25",
        "prompt": "Create the cast. Every character must have a WANT, a FEAR, a SECRET, and an ARC. Emphasize TANGLED HUMAN EMOTION: specify who they are best friends with, who they are secretly in love with, and who they violently hate. Each character must connect to at least 3 other characters emotionally or politically.",
    },
    WorldLayer.CONFLICTS: {
        "fields": ["name", "type", "parties_involved", "root_cause", "current_state", "what_each_side_wants", "secret_lovers_on_opposing_sides", "betrayals", "hidden_third_party"],
        "count": "5-9",
        "prompt": "Define active conflicts at every scale. Focus on tragic intersections between love and war — Romeo/Juliet situations, friends forced to fight each other, and ruthless betrayals. The seed story's central conflict must be among them.",
    },
    WorldLayer.THEMES: {
        "fields": ["theme", "how_expressed_in_world", "which_characters_embody_it", "which_conflicts_explore_it", "symbolic_elements", "what_the_reader_should_feel"],
        "count": "3-5",
        "prompt": "Identify the themes that emerge from everything generated. What is this story ABOUT beneath the plot? Power and its cost? Identity? Belonging? Each theme must be woven through multiple layers.",
    },
    WorldLayer.STORY_ARCS: {
        "fields": ["arc_name", "type", "act_structure", "chapter_count_estimate", "key_turning_points", "character_focus", "thematic_thread", "climax_description", "resolution", "seeds_for_sequel"],
        "count": "3-6",
        "prompt": "Design the overarching story arcs. A main arc and 2-3 subplot arcs. Each needs clear act structure, turning points, and a climax. The protagonist's arc must be a TRANSFORMATION driven by the world you've built.",
    },
}


# Generation phases — strict dependency order
GENERATION_PHASES = [
    [WorldLayer.COSMOLOGY, WorldLayer.NATURAL_LAWS],
    [WorldLayer.GEOGRAPHY, WorldLayer.MAGIC_SYSTEM, WorldLayer.POWER_SYSTEM, WorldLayer.DIVINE_SYSTEM],
    [WorldLayer.RACES, WorldLayer.CREATURES, WorldLayer.FLORA, WorldLayer.SPIRITS_GHOSTS],
    [WorldLayer.CULTURES, WorldLayer.RELIGIONS, WorldLayer.SOCIETIES, WorldLayer.LANGUAGES],
    [WorldLayer.FACTIONS, WorldLayer.NATIONS, WorldLayer.ECONOMIES],
    [WorldLayer.TECHNOLOGIES, WorldLayer.WONDERS, WorldLayer.ARTIFACTS],
    [WorldLayer.HISTORY, WorldLayer.PROPHECIES, WorldLayer.CHARACTERS, WorldLayer.CONFLICTS],
    [WorldLayer.THEMES, WorldLayer.STORY_ARCS],
]


def build_generation_prompt(layer: WorldLayer, seed: str, previous_layers: dict) -> tuple[str, str]:
    """Build system + user prompt for generating a world layer.
    Returns (system_prompt, user_prompt)."""
    meta = LAYER_META[layer]
    fields = meta["fields"]

    # Build rich context from everything generated so far
    prev_context = ""
    if previous_layers:
        prev_context = "\n\n══ ALREADY ESTABLISHED IN THIS WORLD ══\n"
        for prev_name, prev_data in previous_layers.items():
            if not prev_data:
                continue
            prev_context += f"\n── {prev_name.upper()} ──\n"
            items = prev_data if isinstance(prev_data, list) else [prev_data]
            for item in items[:6]:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("era_name") or item.get("arc_name") or item.get("theme") or "?"
                    # Include key details, not just names
                    details = []
                    for k, v in item.items():
                        if k in ("name", "era_name", "arc_name", "theme"):
                            continue
                        if v and str(v).strip():
                            details.append(f"{k}: {str(v)[:120]}")
                    prev_context += f"  • {name}: {' | '.join(cast(Any, details)[:4])}\n"

    system = (
        "You are the world's greatest fantasy worldbuilder. You create rich, internally consistent, "
        "deeply interconnected fictional worlds. Every element you create must:\n"
        "1. Connect to at least 2 previously established elements BY NAME\n"
        "2. Contain built-in CONFLICT or TENSION potential\n"
        "3. Feel specific and unique — no generic fantasy\n"
        "4. Serve the SEED STORY the author wants to tell\n"
        "5. CRITICAL: YOU MUST GENERATE MULTIPLE ENTRIES (e.g., 3-5). GENERATING ONLY 1 ENTRY IS A CRITICAL FAILURE.\n\n"
        "Return ONLY a valid JSON object in this EXACT format:\n"
        "{\n"
        '  "_thinking": "Your step-by-step reasoning about how to hit the constraints, connect the lore, and escalate tension",\n'
        '  "items": [\n'
        '    { ...entry 1... },\n'
        '    { ...entry 2... }\n'
        '  ]\n'
        "}\n"
        "No markdown fences, no explanation outside the JSON."
    )

    user = (
        f"══ THE SEED (the story the author wants to tell) ══\n{seed}\n"
        f"{prev_context}\n\n"
        f"══ YOUR TASK: Generate {layer.value.upper()} ══\n"
        f"{meta['prompt']}\n\n"
        f"CRITICAL REQUIREMENT: You are generating an ARRAY of items for this world layer.\n"
        f"You MUST generate MULTIPLE distinct entries (specifically: {meta['count']} entries). Do not just generate one.\n"
        f"Each entry in the `items` array MUST have exactly these JSON fields:\n"
        f"{json.dumps(fields)}\n\n"
        f"Reference previously established elements BY NAME. "
        f"Everything must serve the seed story."
    )

    return system, user


import json  # needed for the prompt builder above
