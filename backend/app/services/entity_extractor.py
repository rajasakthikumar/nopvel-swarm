"""LLM-based entity and relationship extraction from novel lore.
Equivalent to MiroFish's entity_extractor.py + ontology_generator.py."""

from app.services import llm_client
from app.models.schemas import Entity, Relationship, KnowledgeGraph, EntityType

EXTRACTION_SYSTEM = """You are a world-class literary analyst and knowledge graph engineer.
You extract structured entities and relationships from novel lore/world-building documents.

ENTITY TYPES you must identify:
- character: Named characters, including gods, spirits, historical figures
- place: Locations, cities, realms, dimensions, geographical features
- faction: Organizations, kingdoms, guilds, orders, houses, armies
- artifact: Magical objects, weapons, relics, important items
- magic_system: Magic systems, power types, abilities, supernatural rules
- event: Historical events, wars, cataclysms, prophecies
- concept: Abstract concepts, philosophies, religions, customs
- creature: Species, monsters, races, supernatural beings
- culture: Cultural practices, traditions, social structures

RELATIONSHIP TYPES to identify:
- Emotional relationships: loves, hates, friends_with, rivals_with, terrified_of, obsessed_with, betrothed_to, divorced_from
- Political relationships: ally_of, enemy_of, family_of, mentor_of, betrayed_by, serves, rules, worships
- Location relationships: located_in, capital_of, borders, connected_to
- Faction relationships: member_of, allied_with, at_war_with, founded_by, split_from
- Artifact relationships: wielded_by, created_by, hidden_in, destroys, empowers
- Event relationships: caused_by, led_to, involves, prophecy_of
- System relationships: governed_by, source_of, weakened_by, amplified_by

Be overly thorough. Extract EVERY entity mentioned or implied, and aggressively map out the interpersonal drama. For a rich novel bible, expect 15-40 entities and 30-70 relationships detailing intense emotional and political bonds."""

EXTRACTION_PROMPT = """Extract ALL entities and relationships from this lore text.

Return ONLY valid JSON with this exact structure (no markdown, no backticks, no preamble):
{{
  "entities": [
    {{
      "name": "entity name",
      "type": "character|place|faction|artifact|magic_system|event|concept|creature|culture",
      "description": "1-3 sentence description",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "source": "entity name",
      "target": "entity name",
      "type": "relationship_type",
      "description": "brief description",
      "weight": 0.8
    }}
  ]
}}

For character entities, include in properties: {{\"role\": \"protagonist|antagonist|supporting\", \"traits\": [\"trait1\", \"trait2\"]}}
For place entities: {{\"climate\": \"...\", \"significance\": \"...\"}}
For faction entities: {{\"alignment\": \"...\", \"size\": \"...\"}}

LORE TEXT:
{lore}"""


def extract_entities(lore: str) -> KnowledgeGraph:
    """Extract entities and relationships from lore text using LLM."""
    try:
        result = llm_client.chat_json(
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(lore=lore)}],
            system=EXTRACTION_SYSTEM,
            model=None,  # Use boost model
        )

        entities = []
        for e in result.get("entities", []):
            try:
                entity_type = EntityType(e.get("type", "concept"))
            except ValueError:
                entity_type = EntityType.CONCEPT
            entities.append(Entity(
                name=e["name"],
                type=entity_type,
                description=e.get("description", ""),
                properties=e.get("properties", {}),
            ))

        relationships = []
        for r in result.get("relationships", []):
            relationships.append(Relationship(
                source=r["source"],
                target=r["target"],
                type=r.get("type", "related_to"),
                description=r.get("description", ""),
                weight=r.get("weight", 1.0),
            ))

        return KnowledgeGraph(entities=entities, relationships=relationships)

    except Exception as e:
        print(f"[EntityExtractor] Extraction failed: {e}")
        # Fallback: create minimal graph
        return KnowledgeGraph(
            entities=[
                Entity(name="World", type=EntityType.CONCEPT, description="The story world"),
                Entity(name="Protagonist", type=EntityType.CHARACTER, description="The main character"),
            ],
            relationships=[],
        )
