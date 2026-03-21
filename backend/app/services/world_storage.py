import sqlite3
import json
import os
from typing import List, Dict, Any

class WorldStorage:
    def __init__(self, db_path: str = "world_gen.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_entities (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    entity_type TEXT,
                    name TEXT,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON world_entities(project_id)")

    def save_entity(self, project_id: str, entity_type: str, name: str, data: Dict[str, Any]):
        entity_id = f"{project_id}_{entity_type}_{name}".replace(" ", "_").lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO world_entities (id, project_id, entity_type, name, data)
                VALUES (?, ?, ?, ?, ?)
            """, (entity_id, project_id, entity_type, name, json.dumps(data)))

    def get_entities(self, project_id: str, entity_type: str = None) -> List[Dict[str, Any]]:
        query = "SELECT data FROM world_entities WHERE project_id = ?"
        params = [project_id]
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return [json.loads(row[0]) for row in cursor.fetchall()]

    def delete_entity(self, project_id: str, entity_type: str, name: str):
        entity_id = f"{project_id}_{entity_type}_{name}".replace(" ", "_").lower()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM world_entities WHERE id = ?", (entity_id,))
