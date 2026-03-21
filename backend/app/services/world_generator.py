"""
World Generator — Systematically builds every layer of a fictional world.

Uses the ontology to generate layers in dependency order.
Each layer's generation is informed by previously generated layers.
Everything gets written to Neo4j as it's created.
Agents from the simulation can then MODIFY, EXPAND, or CHALLENGE any layer.
"""

import json
import time
from app.services import llm_client
from app.services.world_ontology import (
    WorldLayer, LAYER_META, GENERATION_PHASES, build_generation_prompt
)
from app.models.schemas import Entity, EntityType, Relationship, KnowledgeGraph
from app.services.world_storage import WorldStorage


# Map world layers to entity types for Neo4j storage
LAYER_TO_ENTITY_TYPE = {
    WorldLayer.COSMOLOGY: EntityType.CONCEPT,
    WorldLayer.NATURAL_LAWS: EntityType.CONCEPT,
    WorldLayer.GEOGRAPHY: EntityType.PLACE,
    WorldLayer.MAGIC_SYSTEM: EntityType.MAGIC_SYSTEM,
    WorldLayer.POWER_SYSTEM: EntityType.MAGIC_SYSTEM,
    WorldLayer.DIVINE_SYSTEM: EntityType.CHARACTER,
    WorldLayer.RACES: EntityType.CREATURE,
    WorldLayer.CREATURES: EntityType.FAUNA,
    WorldLayer.FLORA: EntityType.FAUNA,
    WorldLayer.SPIRITS_GHOSTS: EntityType.FAUNA,
    WorldLayer.CULTURES: EntityType.CULTURE,
    WorldLayer.RELIGIONS: EntityType.RELIGION,
    WorldLayer.SOCIETIES: EntityType.CULTURE,
    WorldLayer.FACTIONS: EntityType.FACTION,
    WorldLayer.NATIONS: EntityType.KINGDOM,
    WorldLayer.ECONOMIES: EntityType.CONCEPT,
    WorldLayer.TECHNOLOGIES: EntityType.CONCEPT,
    WorldLayer.LANGUAGES: EntityType.CULTURE,
    WorldLayer.WONDERS: EntityType.PLACE,
    WorldLayer.ARTIFACTS: EntityType.ARTIFACT,
    WorldLayer.HISTORY: EntityType.EVENT,
    WorldLayer.PROPHECIES: EntityType.EVENT,
    WorldLayer.CHARACTERS: EntityType.CHARACTER,
    WorldLayer.CONFLICTS: EntityType.EVENT,
    WorldLayer.THEMES: EntityType.CONCEPT,
    WorldLayer.STORY_ARCS: EntityType.EVENT,
}


class WorldGenerator:
    """Systematically generates every layer of a fictional world."""
    
    def __init__(self, graph_builder=None, project_id=None, db_path=None):
        self.graph_builder = graph_builder
        self.project_id = project_id
        self.storage = WorldStorage(db_path) if db_path else None
        self.generated_layers: dict[str, list[dict]] = {}
        self.all_entities: list[Entity] = []
        self.all_relationships: list[Relationship] = []
        self.generation_log: list[dict] = []
    
    def generate_layer(self, layer: WorldLayer, lore: str, 
                       selected_layers: list[WorldLayer] = None) -> list[dict]:
        """Generate a single world layer using LLM."""
        system_prompt, user_prompt = build_generation_prompt(layer, lore, self.generated_layers)
        
        try:
            result = llm_client.chat_json(
                [{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
            
            if not isinstance(result, list):
                result = [result]
            
            # Store generated data
            self.generated_layers[layer.value] = result
            
            # Convert to entities for Neo4j
            entity_type = LAYER_TO_ENTITY_TYPE.get(layer, EntityType.CONCEPT)
            for item in result:
                name = item.get("name") or item.get("era_name") or item.get("arc_name") or item.get("theme") or f"{layer.value}_{len(self.all_entities)}"
                
                entity = Entity(
                    name=name,
                    type=entity_type,
                    description=self._build_description(item),
                    properties={
                        "world_layer": layer.value,
                        **{k: str(v)[:500] for k, v in item.items() if k != "name"}
                    },
                )
                self.all_entities.append(entity)
                
                # Auto-detect relationships from field values
                self._extract_relationships(name, item, layer)
            
            # Persist to separate DB
            if self.storage:
                for item in result:
                    name = item.get("name") or item.get("era_name") or "Unnamed"
                    self.storage.save_entity(self.project_id, layer.value, name, item)

            # Write to Neo4j immediately
            self._persist_to_graph(layer, result)
            
            self.generation_log.append({
                "layer": layer.value,
                "count": len(result),
                "timestamp": time.time(),
                "entity_names": [item.get("name", "?") for item in result],
            })
            
            return result
            
        except Exception as e:
            self.generation_log.append({
                "layer": layer.value,
                "error": str(e),
                "timestamp": time.time(),
            })
            return []
    
    def generate_all(self, lore: str, selected_layers: list[WorldLayer] = None,
                     progress_callback=None) -> dict:
        """Generate all world layers in dependency order."""
        results = {}
        
        for phase_idx, phase in enumerate(GENERATION_PHASES):
            layers_to_gen = phase
            if selected_layers:
                layers_to_gen = [l for l in phase if l in selected_layers]
            
            for layer in layers_to_gen:
                if progress_callback:
                    progress_callback(f"Generating {layer.value}...", phase_idx, len(GENERATION_PHASES))
                
                layer_data = self.generate_layer(layer, lore)
                results[layer.value] = layer_data
        
        return results
    
    def generate_selected(self, lore: str, layers: list[str],
                          progress_callback=None) -> dict:
        """Generate only selected layers."""
        results = {}
        layer_enums = []
        for l in layers:
            try:
                layer_enums.append(WorldLayer(l))
            except ValueError:
                pass
        
        for i, layer in enumerate(layer_enums):
            if progress_callback:
                progress_callback(f"Generating {layer.value}...", i, len(layer_enums))
            results[layer.value] = self.generate_layer(layer, lore)
        
        return results
    
    def _build_description(self, item: dict) -> str:
        """Build a rich description from all fields of a generated item."""
        parts = []
        for key, val in item.items():
            if key == "name" or not val:
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            parts.append(f"{key}: {val}")
        return ". ".join(parts[:5])[:500]
    
    def _extract_relationships(self, source_name: str, item: dict, layer: WorldLayer):
        """Auto-detect relationships from generated data by finding entity name references."""
        existing_names = {e.name.lower(): e.name for e in self.all_entities}
        
        text_to_scan = json.dumps(item)
        for existing_lower, existing_real in existing_names.items():
            if existing_lower in text_to_scan.lower() and existing_real != source_name:
                # Determine relationship type from context
                rel_type = "related_to"
                if layer == WorldLayer.CHARACTERS:
                    rel_type = "interacts_with"
                elif layer in (WorldLayer.FACTIONS, WorldLayer.NATIONS):
                    rel_type = "political_connection"
                elif layer in (WorldLayer.RELIGIONS, WorldLayer.CULTURES):
                    rel_type = "cultural_connection"
                elif layer == WorldLayer.GEOGRAPHY:
                    rel_type = "located_near"
                elif layer == WorldLayer.HISTORY:
                    rel_type = "involved_in"
                
                self.all_relationships.append(Relationship(
                    source=source_name,
                    target=existing_real,
                    type=rel_type,
                    description=f"Connection from {layer.value} generation",
                ))
    
    def _persist_to_graph(self, layer: WorldLayer, items: list[dict]):
        """Write generated items to Neo4j with the world_layer label."""
        if not self.graph_builder or not self.graph_builder.driver:
            return
        
        pid = self.project_id
        entity_type = LAYER_TO_ENTITY_TYPE.get(layer, EntityType.CONCEPT)
        
        try:
            with self.graph_builder.driver.session() as session:
                for item in items:
                    name = item.get("name") or item.get("era_name") or item.get("arc_name") or item.get("theme", "unnamed")
                    desc = self._build_description(item)
                    
                    # Create node with world_layer label
                    session.run(
                        f"""MERGE (n:Entity {{name: $name, project_id: $pid}})
                            SET n.type = $type, n.description = $desc,
                                n.world_layer = $layer
                            SET n:{layer.value.title().replace('_', '')}""",
                        name=name, pid=pid, type=entity_type.value,
                        desc=desc, layer=layer.value,
                    )
                    
                    # Store all properties
                    for key, val in item.items():
                        if key == "name":
                            continue
                        prop_val = json.dumps(val) if isinstance(val, (list, dict)) else str(val)
                        if len(prop_val) < 1000:
                            session.run(
                                f"MATCH (n:Entity {{name: $name, project_id: $pid}}) SET n.`prop_{key}` = $val",
                                name=name, pid=pid, val=prop_val[:500],
                            )
        except Exception as e:
            print(f"[WorldGenerator] Neo4j persist error for {layer.value}: {e}")
    
    def get_knowledge_graph(self) -> KnowledgeGraph:
        """Return the accumulated knowledge graph."""
        return KnowledgeGraph(
            entities=self.all_entities,
            relationships=self.all_relationships,
        )
    
    def get_summary(self) -> dict:
        """Summary of what's been generated."""
        return {
            "layers_generated": list(self.generated_layers.keys()),
            "total_entities": len(self.all_entities),
            "total_relationships": len(self.all_relationships),
            "per_layer": {
                layer: len(items) for layer, items in self.generated_layers.items()
            },
            "log": self.generation_log,
        }
