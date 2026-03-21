"""
Vector Memory Service — ChromaDB + Ollama embeddings.

Replaces flat SQLite memory with semantic retrieval.

What this fixes:
1. CONTEXT WINDOW PROBLEM — agents can semantically search ALL past discussion,
   not just last N posts. "What did anyone say about the ash magic?" actually works.
2. WORLD COHERENCE — every generated entity gets embedded. When generating layer 20,
   we can retrieve the 10 most relevant entities from layers 1-19, even if they were
   generated hours ago and are way outside the context window.
3. AGENT MEMORY — agents remember semantically, not chronologically. An agent who
   discussed a character 50 posts ago still remembers when that character comes up again.
4. CROSS-LAYER RETRIEVAL — when the outliner needs "all foreshadowing about the prince",
   it does a vector search, not a keyword grep.

Uses Ollama's nomic-embed-text for local embeddings (no API costs).
"""

import json, os, time, hashlib
import chromadb
import httpx
from app.config import Config


class VectorMemory:
    """ChromaDB-backed semantic memory for the entire system."""

    def __init__(self, project_id: str, persist_dir: str = None):
        self.project_id = project_id
        persist_dir = persist_dir or Config.CHROMA_PERSIST_DIR or "./chroma_data"
        persist_path = os.path.join(persist_dir, project_id)
        os.makedirs(persist_path, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_path)

        # Collections — separate namespaces for different data types
        self.world_entities = self._get_or_create("world_entities")
        self.agent_memories = self._get_or_create("agent_memories")
        self.simulation_posts = self._get_or_create("simulation_posts")
        self.outline_chunks = self._get_or_create("outline_chunks")

    @classmethod
    def branch_project(cls, old_pid: str, new_pid: str, persist_dir: str = None) -> bool:
        """Duplicate an entire project's vector database by copying the underlying directory."""
        import shutil
        persist_dir = persist_dir or Config.CHROMA_PERSIST_DIR or "./chroma_data"
        old_path = os.path.join(persist_dir, old_pid)
        new_path = os.path.join(persist_dir, new_pid)
        if not os.path.exists(old_path):
            return False
        try:
            shutil.copytree(old_path, new_path)
            return True
        except Exception as e:
            print(f"[VectorMemory] Failed to branch from {old_pid} to {new_pid}: {e}")
            return False

    def _get_or_create(self, name):
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from Ollama."""
        embeddings = []
        model = Config.EMBEDDING_MODEL or "nomic-embed-text"
        base_url = (Config.EMBEDDING_BASE_URL or "http://localhost:11434").rstrip("/")

        for text in texts:
            try:
                resp = httpx.post(
                    f"{base_url}/api/embeddings",
                    json={"model": model, "prompt": text[:2000]},
                    timeout=30.0,
                )
                resp.raise_for_status()
                embeddings.append(resp.json()["embedding"])
            except Exception as e:
                print(f"[VectorMemory] Embedding error: {e}")
                # Fallback: zero vector (won't match well but won't crash)
                embeddings.append([0.0] * 768)
        return embeddings

    def _make_id(self, prefix: str, content: str) -> str:
        return f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    # ═══ WORLD ENTITY OPERATIONS ═══

    def store_world_entity(self, name: str, entity_type: str, description: str,
                           layer: str, properties: dict = None):
        """Store a world entity with its full description for semantic retrieval."""
        doc = f"{name} ({entity_type}, {layer}): {description}"
        if properties:
            extras = " | ".join(f"{k}: {v}" for k, v in properties.items() if v)[:500]
            doc += f" | {extras}"

        doc_id = self._make_id("entity", f"{self.project_id}_{name}_{layer}")
        embeddings = self._embed([doc])

        self.world_entities.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[doc],
            metadatas=[{
                "name": name, "type": entity_type, "layer": layer,
                "project_id": self.project_id, "timestamp": str(time.time()),
            }],
        )

    def store_world_layer(self, layer: str, items: list[dict]):
        """Store all items from a world layer."""
        for item in items:
            name = item.get("name") or item.get("era_name") or item.get("arc_name") or item.get("theme") or "unnamed"
            desc_parts = [f"{k}: {v}" for k, v in item.items() if k != "name" and v]
            description = " | ".join(desc_parts[:5])[:500]
            self.store_world_entity(name, layer, description, layer, item)

    def search_world(self, query: str, n_results: int = 10, layer_filter: str = None) -> list[dict]:
        """Semantic search across all world entities."""
        embeddings = self._embed([query])
        where = {"project_id": self.project_id}
        if layer_filter:
            where["layer"] = layer_filter

        try:
            results = self.world_entities.query(
                query_embeddings=embeddings,
                n_results=min(n_results, self.world_entities.count() or 1),
                where=where if self.world_entities.count() > 0 else None,
            )
            return self._format_results(results)
        except Exception:
            return []

    # ═══ AGENT MEMORY OPERATIONS ═══

    def store_agent_memory(self, agent_id: str, agent_name: str, round_num: int,
                           action: str, text: str, platform: str,
                           emotional_valence: float = 0.0, entities_mentioned: list = None):
        """Store an agent's post/action as a searchable memory."""
        doc = f"[{agent_name}|R{round_num}|{action}|{platform}]: {text}"
        doc_id = self._make_id("mem", f"{agent_id}_{round_num}_{time.time()}")
        embeddings = self._embed([doc])

        self.agent_memories.upsert(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[doc],
            metadatas=[{
                "agent_id": agent_id, "agent_name": agent_name,
                "round": str(round_num), "action": action, "platform": platform,
                "emotional_valence": str(emotional_valence),
                "entities": json.dumps(entities_mentioned or []),
                "project_id": self.project_id, "timestamp": str(time.time()),
            }],
        )

    def search_agent_memory(self, agent_id: str, query: str, n_results: int = 8) -> list[dict]:
        """Search a specific agent's memories semantically."""
        embeddings = self._embed([query])
        try:
            results = self.agent_memories.query(
                query_embeddings=embeddings,
                n_results=min(n_results, max(1, self.agent_memories.count())),
                where={"agent_id": agent_id},
            )
            return self._format_results(results)
        except Exception:
            return []

    def search_all_memories(self, query: str, n_results: int = 10) -> list[dict]:
        """Search across ALL agents' memories."""
        embeddings = self._embed([query])
        try:
            results = self.agent_memories.query(
                query_embeddings=embeddings,
                n_results=min(n_results, max(1, self.agent_memories.count())),
            )
            return self._format_results(results)
        except Exception:
            return []

    # ═══ SIMULATION POST OPERATIONS ═══

    def store_post(self, post_id: str, author_name: str, action: str,
                   text: str, round_num: int, platform: str):
        """Store a simulation post for retrieval."""
        doc = f"[{author_name}|{action}|R{round_num}]: {text}"
        embeddings = self._embed([doc])

        self.simulation_posts.upsert(
            ids=[post_id],
            embeddings=embeddings,
            documents=[doc],
            metadatas=[{
                "author": author_name, "action": action,
                "round": str(round_num), "platform": platform,
                "project_id": self.project_id, "timestamp": str(time.time()),
            }],
        )

    def search_posts(self, query: str, n_results: int = 10,
                     platform: str = None, action: str = None) -> list[dict]:
        """Semantic search across simulation posts."""
        embeddings = self._embed([query])
        where = {"project_id": self.project_id}
        if platform: where["platform"] = platform
        if action: where["action"] = action

        try:
            results = self.simulation_posts.query(
                query_embeddings=embeddings,
                n_results=min(n_results, max(1, self.simulation_posts.count())),
                where=where if len(where) > 1 else None,
            )
            return self._format_results(results)
        except Exception:
            return []

    # ═══ OUTLINE CHUNK OPERATIONS ═══

    def store_outline_chunk(self, chunk_id: str, chapter_num: int, content: str,
                            chunk_type: str = "chapter"):
        """Store outline chunks for retrieval during deepening passes."""
        embeddings = self._embed([content[:1500]])
        self.outline_chunks.upsert(
            ids=[chunk_id],
            embeddings=embeddings,
            documents=[content[:2000]],
            metadatas=[{
                "chapter": str(chapter_num), "type": chunk_type,
                "project_id": self.project_id,
            }],
        )

    def search_outline(self, query: str, n_results: int = 5) -> list[dict]:
        embeddings = self._embed([query])
        try:
            results = self.outline_chunks.query(
                query_embeddings=embeddings,
                n_results=min(n_results, max(1, self.outline_chunks.count())),
            )
            return self._format_results(results)
        except Exception:
            return []

    # ═══ CONTEXT BUILDER — the key integration point ═══

    def build_context_for_agent(self, agent_id: str, agent_name: str,
                                 current_discussion_topic: str,
                                 grounded_entity: str = None) -> str:
        """Build rich context for an agent by combining:
        1. Relevant world entities (semantic match to current discussion)
        2. Agent's own relevant memories
        3. Related posts from other agents
        4. Entity's graph neighborhood
        """
        context_parts = []

        # 1. World entities relevant to current discussion
        world_hits = self.search_world(current_discussion_topic, n_results=8)
        if world_hits:
            context_parts.append("RELEVANT WORLD KNOWLEDGE:")
            for hit in world_hits:
                context_parts.append(f"  • {hit['document'][:200]}")

        # 2. If grounded in an entity, get that entity's full context
        if grounded_entity:
            entity_hits = self.search_world(grounded_entity, n_results=5)
            if entity_hits:
                context_parts.append(f"\nYOUR ENTITY ({grounded_entity}) CONTEXT:")
                for hit in entity_hits:
                    context_parts.append(f"  • {hit['document'][:200]}")

        # 3. Agent's own relevant memories
        own_memories = self.search_agent_memory(agent_id, current_discussion_topic, n_results=5)
        if own_memories:
            context_parts.append("\nYOUR RELEVANT MEMORIES:")
            for hit in own_memories:
                context_parts.append(f"  • {hit['document'][:150]}")

        # 4. Related posts from all agents
        related_posts = self.search_posts(current_discussion_topic, n_results=5)
        if related_posts:
            context_parts.append("\nRELATED DISCUSSION:")
            for hit in related_posts:
                context_parts.append(f"  • {hit['document'][:150]}")

        return "\n".join(context_parts) if context_parts else ""

    def build_context_for_layer_generation(self, layer_name: str,
                                            seed: str, n_results: int = 15) -> str:
        """Build rich context for generating a world layer by pulling
        the most relevant entities from ALL previously generated layers."""
        query = f"{seed} {layer_name}"
        hits = self.search_world(query, n_results=n_results)
        if not hits:
            return ""

        context = "SEMANTICALLY RELEVANT WORLD ELEMENTS:\n"
        for hit in hits:
            meta = hit.get("metadata", {})
            context += f"  [{meta.get('layer', '?')}] {hit['document'][:200]}\n"
        return context

    def build_context_for_outline(self, chapter_topic: str, character_name: str = None) -> str:
        """Build context for outline generation by pulling relevant world + debate data."""
        parts = []

        world_hits = self.search_world(chapter_topic, n_results=8)
        if world_hits:
            parts.append("WORLD CONTEXT:")
            for h in world_hits:
                parts.append(f"  • {h['document'][:200]}")

        if character_name:
            char_hits = self.search_world(character_name, n_results=5)
            if char_hits:
                parts.append(f"\n{character_name} CONTEXT:")
                for h in char_hits:
                    parts.append(f"  • {h['document'][:200]}")

        debate_hits = self.search_posts(chapter_topic, n_results=5)
        if debate_hits:
            parts.append("\nAGENT INSIGHTS:")
            for h in debate_hits:
                parts.append(f"  • {h['document'][:150]}")

        return "\n".join(parts)

    # ═══ UTILITIES ═══

    def _format_results(self, results) -> list[dict]:
        formatted = []
        if not results or not results.get("documents"):
            return []
        for i, doc in enumerate(results["documents"][0]):
            entry = {"document": doc, "id": results["ids"][0][i] if results.get("ids") else ""}
            if results.get("metadatas") and results["metadatas"][0]:
                entry["metadata"] = results["metadatas"][0][i]
            if results.get("distances") and results["distances"][0]:
                entry["distance"] = results["distances"][0][i]
            formatted.append(entry)
        return formatted

    def get_stats(self) -> dict:
        return {
            "world_entities": self.world_entities.count(),
            "agent_memories": self.agent_memories.count(),
            "simulation_posts": self.simulation_posts.count(),
            "outline_chunks": self.outline_chunks.count(),
        }
