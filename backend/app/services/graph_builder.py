"""Neo4j knowledge graph builder with deep query support.

All methods gracefully handle Neo4j unavailability — they return empty
results instead of crashing, allowing the app to work without Docker.
"""
import logging
import os
from neo4j import GraphDatabase
from app.models.schemas import KnowledgeGraph, Entity, Relationship, InWorldAction

logger = logging.getLogger("novelswarm.graph")


class GraphBuilder:
    def __init__(self, uri, user, password):
        self._uri, self._user, self._password = uri, user, password
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
                self._driver.verify_connectivity()
                logger.info(f"Connected to Neo4j at {self._uri}")
            except Exception as e:
                logger.warning(f"Neo4j unavailable: {e}")
                self._driver = None
        return self._driver

    def build_graph(self, project_id, kg):
        if not self.driver:
            return {"status": "neo4j_unavailable"}
        stats = {"nodes_created": 0, "relationships_created": 0}
        try:
            with self.driver.session() as s:
                s.run("MATCH (n {project_id: $pid}) DETACH DELETE n", pid=project_id)
                for e in kg.entities:
                    s.run(
                        "MERGE (n:Entity {name: $name, project_id: $pid}) "
                        "SET n.type=$type, n.description=$desc, n.mentions=0, n.role='background'",
                        name=e.name, pid=project_id, type=e.type.value, desc=e.description,
                    )
                    stats["nodes_created"] += 1
                for r in kg.relationships:
                    s.run(
                        """MATCH (a:Entity {name:$src, project_id:$pid})
                           MATCH (b:Entity {name:$tgt, project_id:$pid})
                           MERGE (a)-[r:RELATES {type:$rt}]->(b)
                           SET r.description=$d, r.weight=$w""",
                        src=r.source, tgt=r.target, pid=project_id,
                        rt=r.type, d=r.description, w=r.weight,
                    )
                    stats["relationships_created"] += 1
        except Exception as e:
            logger.error(f"Graph build error: {e}")
            return {"status": "error", "error": str(e)}
        return {"status": "ok", **stats}

    def branch_project(self, old_pid, new_pid):
        """Duplicate a project's entities and relations to a new project_id."""
        if not self.driver:
            return {"status": "neo4j_unavailable"}
        try:
            with self.driver.session() as s:
                # Copy Entities
                s.run("""
                    MATCH (n:Entity {project_id: $old})
                    MERGE (m:Entity {name: n.name, project_id: $new})
                    SET m += properties(n)
                    SET m.project_id = $new
                """, old=old_pid, new=new_pid)

                # Copy Relationships (RELATES)
                s.run("""
                    MATCH (a1:Entity {project_id: $old})-[r:RELATES]->(b1:Entity {project_id: $old})
                    MATCH (a2:Entity {name: a1.name, project_id: $new})
                    MATCH (b2:Entity {name: b1.name, project_id: $new})
                    MERGE (a2)-[r2:RELATES]->(b2)
                    SET r2 += properties(r)
                """, old=old_pid, new=new_pid)

                # Copy Relationships (REFERENCES)
                s.run("""
                    MATCH (a1:Entity {project_id: $old})-[r:REFERENCES]->(b1:Entity {project_id: $old})
                    MATCH (a2:Entity {name: a1.name, project_id: $new})
                    MATCH (b2:Entity {name: b1.name, project_id: $new})
                    MERGE (a2)-[r2:REFERENCES]->(b2)
                    SET r2 += properties(r)
                """, old=old_pid, new=new_pid)
        except Exception as e:
            logger.error(f"Graph branch error: {e}")
            return {"status": "error", "error": str(e)}
        return {"status": "ok"}

    def query_entity(self, project_id, name):
        if not self.driver:
            return None
        try:
            with self.driver.session() as s:
                res = s.run(
                    """MATCH (n:Entity {name:$name, project_id:$pid})
                       OPTIONAL MATCH (n)-[r]->(m:Entity)
                       RETURN n, collect({rel_type:r.type, target:m.name, desc:r.description}) as rels""",
                    name=name, pid=project_id,
                )
                rec = res.single()
                if not rec:
                    return None
                return {
                    "entity": dict(rec["n"]),
                    "relationships": [r for r in rec["rels"] if r["target"]],
                }
        except Exception as e:
            logger.error(f"Query entity error: {e}")
            return None

    def query_neighborhood(self, project_id, entity_name, depth=2):
        if not self.driver:
            return {"nodes": [], "edges": []}
        try:
            with self.driver.session() as s:
                res = s.run(
                    f"""MATCH path=(start:Entity {{name:$name, project_id:$pid}})-[*1..{depth}]-(end:Entity)
                        UNWIND nodes(path) as n WITH DISTINCT n
                        RETURN collect(n) as nodes""",
                    name=entity_name, pid=project_id,
                )
                rec = res.single()
                nodes = [dict(n) for n in rec["nodes"]] if rec else []
                edges = []
                if nodes:
                    res2 = s.run(
                        """MATCH (a:Entity {project_id:$pid})-[r]->(b:Entity {project_id:$pid})
                           WHERE a.name IN $names AND b.name IN $names
                           RETURN a.name as source, b.name as target, r.type as type""",
                        pid=project_id, names=[n.get("name") for n in nodes],
                    )
                    edges = [dict(r) for r in res2]
                return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.error(f"Query neighborhood error: {e}")
            return {"nodes": [], "edges": []}

    def query_agent_full_context(self, project_id, entity_name):
        """Deep query: get allies, enemies, locations, artifacts, factions for persona building."""
        if not self.driver:
            return {}
        ctx = {"allies": [], "enemies": [], "locations": [], "artifacts": [], "factions": [], "all_rels": []}
        try:
            with self.driver.session() as s:
                res = s.run(
                    """MATCH (n:Entity {name:$name, project_id:$pid})-[r]-(m:Entity {project_id:$pid})
                       RETURN m.name as name, m.type as type, r.type as rel_type, m.description as desc""",
                    name=entity_name, pid=project_id,
                )
                for rec in res:
                    rel = rec["rel_type"] or ""
                    ctx["all_rels"].append(f"{entity_name} --[{rel}]--> {rec['name']} ({rec['type']})")
                    t = rec["type"] or ""
                    if "ally" in rel or "friend" in rel or "serves" in rel:
                        ctx["allies"].append(rec["name"])
                    elif "enemy" in rel or "rival" in rel or "betray" in rel:
                        ctx["enemies"].append(rec["name"])
                    elif t == "place":
                        ctx["locations"].append(rec["name"])
                    elif t == "artifact":
                        ctx["artifacts"].append(rec["name"])
                    elif t == "faction":
                        ctx["factions"].append(rec["name"])
                        if "member" in rel:
                            ctx["factions"][-1] += " (member)"
        except Exception as e:
            logger.error(f"Query agent context error: {e}")
        return ctx

    # ═══ METHODS USED BY SIMULATION ENGINE ═══

    def increment_mention(self, project_id, entity_name):
        """Increment mention count for an entity (used for character emergence tracking)."""
        if not self.driver:
            return
        try:
            with self.driver.session() as s:
                s.run(
                    """MATCH (n:Entity {name:$name, project_id:$pid})
                       SET n.mentions = COALESCE(n.mentions, 0) + 1""",
                    name=entity_name, pid=project_id,
                )
        except Exception as e:
            logger.debug(f"Increment mention error: {e}")

    def promote_character(self, project_id, entity_name, new_role):
        """Promote a character to a new narrative role."""
        if not self.driver:
            return
        try:
            with self.driver.session() as s:
                s.run(
                    """MATCH (n:Entity {name:$name, project_id:$pid})
                       SET n.role = $role""",
                    name=entity_name, pid=project_id, role=new_role,
                )
                logger.info(f"Character promoted: {entity_name} → {new_role}")
        except Exception as e:
            logger.debug(f"Promote character error: {e}")

    def get_emergent_candidates(self, project_id, min_mentions=3):
        """Get entities that could be promoted based on mention counts."""
        if not self.driver:
            return []
        try:
            with self.driver.session() as s:
                res = s.run(
                    """MATCH (n:Entity {project_id:$pid})
                       WHERE COALESCE(n.mentions, 0) >= $min
                       OPTIONAL MATCH (n)-[r]-()
                       WITH n, COALESCE(n.mentions, 0) as mentions, COUNT(r) as rels
                       RETURN n.name as name, n.role as role, n.type as type,
                              mentions, toFloat(rels) * 0.5 + toFloat(mentions) * 0.3 as weight
                       ORDER BY weight DESC
                       LIMIT 20""",
                    pid=project_id, min=min_mentions,
                )
                return [dict(r) for r in res]
        except Exception as e:
            logger.debug(f"Get emergent candidates error: {e}")
            return []

    def query_character_web(self, project_id, entity_name):
        """Get a character's relationship web as formatted text."""
        if not self.driver:
            return ""
        try:
            with self.driver.session() as s:
                res = s.run(
                    """MATCH (n:Entity {name:$name, project_id:$pid})-[r]-(m:Entity {project_id:$pid})
                       RETURN m.name as name, m.type as type, r.type as rel,
                              m.description as desc
                       LIMIT 15""",
                    name=entity_name, pid=project_id,
                )
                lines = [f"CHARACTER WEB for {entity_name}:"]
                for rec in res:
                    lines.append(f"  → {rec['rel']} → {rec['name']} ({rec['type']}): {(rec['desc'] or '')[:80]}")
                return "\n".join(lines) if len(lines) > 1 else ""
        except Exception as e:
            logger.debug(f"Query character web error: {e}")
            return ""

    def query_by_topic(self, project_id, keywords, limit=5):
        """Find entities matching topic keywords."""
        if not self.driver:
            return ""
        try:
            with self.driver.session() as s:
                # Build a WHERE clause that matches any keyword
                conditions = " OR ".join(
                    f"toLower(n.name) CONTAINS toLower('{kw}')" +
                    f" OR toLower(n.description) CONTAINS toLower('{kw}')"
                    for kw in keywords[:6]
                )
                res = s.run(
                    f"""MATCH (n:Entity {{project_id:$pid}})
                        WHERE {conditions}
                        RETURN n.name as name, n.type as type, n.description as desc
                        LIMIT $limit""",
                    pid=project_id, limit=limit,
                )
                lines = []
                for rec in res:
                    lines.append(f"  {rec['name']} ({rec['type']}): {(rec['desc'] or '')[:100]}")
                return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Query by topic error: {e}")
            return ""

    def get_faction_dynamics(self, project_id):
        """Get faction relationships and power dynamics."""
        if not self.driver:
            return ""
        try:
            with self.driver.session() as s:
                res = s.run(
                    """MATCH (f:Entity {project_id:$pid, type:'faction'})-[r]-(other:Entity {project_id:$pid})
                       RETURN f.name as faction, r.type as rel, other.name as other, other.type as other_type
                       LIMIT 20""",
                    pid=project_id,
                )
                lines = ["FACTION DYNAMICS:"]
                for rec in res:
                    lines.append(f"  {rec['faction']} --[{rec['rel']}]--> {rec['other']} ({rec['other_type']})")
                return "\n".join(lines) if len(lines) > 1 else ""
        except Exception as e:
            logger.debug(f"Get faction dynamics error: {e}")
            return ""

    def add_entity(self, project_id, name, entity_type, description):
        """Add a new entity to the graph (used for emergent entities during simulation)."""
        if not self.driver:
            return
        try:
            with self.driver.session() as s:
                s.run(
                    """MERGE (n:Entity {name:$name, project_id:$pid})
                       SET n.type=$type, n.description=$desc, n.mentions=1, n.role='background',
                           n.emergent=true""",
                    name=name, pid=project_id, type=entity_type, desc=description,
                )
        except Exception as e:
            logger.debug(f"Add entity error: {e}")

    def add_relationship(self, project_id, source, target, rel_type, description=""):
        """Add a relationship between two existing entities."""
        if not self.driver:
            return False
        try:
            with self.driver.session() as s:
                s.run(
                    """MATCH (a:Entity {name:$src, project_id:$pid})
                       MATCH (b:Entity {name:$tgt, project_id:$pid})
                       MERGE (a)-[r:RELATES {type:$rt}]->(b)
                       SET r.description=$d, r.weight=1.0""",
                    src=source, tgt=target, pid=project_id, rt=rel_type, d=description,
                )
            return True
        except Exception as e:
            logger.debug(f"Add relationship error: {e}")
            return False

    def delete_entity(self, project_id, name):
        """Delete an entity and all its relationships from the graph."""
        if not self.driver:
            return False
        try:
            with self.driver.session() as s:
                s.run(
                    "MATCH (n:Entity {name:$name, project_id:$pid}) DETACH DELETE n",
                    name=name, pid=project_id,
                )
            return True
        except Exception as e:
            logger.debug(f"Delete entity error: {e}")
            return False

    def delete_relationship(self, project_id, source, target, rel_type):
        """Delete a specific relationship between two entities."""
        if not self.driver:
            return False
        try:
            with self.driver.session() as s:
                s.run(
                    """MATCH (a:Entity {name:$src, project_id:$pid})
                          -[r:RELATES {type:$rt}]->
                          (b:Entity {name:$tgt, project_id:$pid})
                       DELETE r""",
                    src=source, tgt=target, pid=project_id, rt=rel_type,
                )
            return True
        except Exception as e:
            logger.debug(f"Delete relationship error: {e}")
            return False


    def get_full_graph(self, project_id):
        if not self.driver:
            return {"nodes": [], "edges": []}
        try:
            with self.driver.session() as s:
                nodes = [dict(r["n"]) for r in s.run(
                    "MATCH (n:Entity {project_id:$pid}) RETURN n", pid=project_id,
                )]
                edges = [dict(r) for r in s.run(
                    """MATCH (a:Entity {project_id:$pid})-[r]->(b:Entity {project_id:$pid})
                       RETURN a.name as source, b.name as target, r.type as type, r.description as description""",
                    pid=project_id,
                )]
            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.error(f"Get full graph error: {e}")
            return {"nodes": [], "edges": []}

    def search_entities(self, project_id, query):
        if not self.driver:
            return []
        try:
            with self.driver.session() as s:
                return [dict(r["n"]) for r in s.run(
                    """MATCH (n:Entity {project_id:$pid})
                       WHERE toLower(n.name) CONTAINS toLower($q) OR toLower(n.description) CONTAINS toLower($q)
                       RETURN n LIMIT 20""",
                    pid=project_id, q=query,
                )]
        except Exception as e:
            logger.error(f"Search entities error: {e}")
            return []

    def sync_agent_relationships(self, project_id, simulation_db_path):
        """Collect all relationships from simulation SQLite and push to Neo4j."""
        if not self.driver or not os.path.exists(simulation_db_path):
            return
        import sqlite3
        import json
        try:
            with sqlite3.connect(simulation_db_path) as conn:
                conn.row_factory = sqlite3.Row
                rels = conn.execute("SELECT * FROM relationships").fetchall()
                
                with self.driver.session() as s:
                    for r in rels:
                        # Determine relationship type based on sentiment
                        sent = r["sentiment"]
                        rel_type = "NEUTRAL"
                        if sent > 0.6: rel_type = "BOND"
                        elif sent > 0.2: rel_type = "FRIENDLY"
                        elif sent < -0.6: rel_type = "ENMITY"
                        elif sent < -0.2: rel_type = "RIVALRY"
                        
                        s.run(
                            """MATCH (a:Entity {name: $src, project_id: $pid})
                               MATCH (b:Entity {name: $tgt, project_id: $pid})
                               MERGE (a)-[rel:RELATES {type: $rt}]->(b)
                               SET rel.score = $score, rel.last_action = $la,
                                   rel.interaction_count = $ic""",
                            src=r["agent_id"], tgt=r["other_id"], pid=project_id,
                            rt=rel_type, score=sent, la=r["last_action"],
                            ic=r["interaction_count"]
                        )
            logger.info(f"Synced {len(rels)} agent relationships to Neo4j for {project_id}")
        except Exception as e:
            logger.error(f"Sync agent relationships error: {e}")

    def close(self):
        if self._driver:
            self._driver.close()
