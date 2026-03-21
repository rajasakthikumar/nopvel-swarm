"""Core swarm simulation engine v3.

Improvements over v2:
- Parallel LLM calls via ThreadPoolExecutor (respects MAX_CONCURRENT_AGENTS)
- SQLite WAL mode for safe concurrent access
- Agent-to-agent post threading (reply_to populated)
- Cross-forum vector similarity selection
- Checkpoint/resume support
- Proper logging throughout
"""

from typing import List, Dict, Optional, Any, Union, cast
import random
import time
import json
import os
import logging
import threading
import queue
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services import llm_client
from app.config import Config
from app.models.schemas import (
    AgentPersona,
    SimPost,
    SocialAction,
    Platform,
    Stance,
    KnowledgeGraph,
    SimulationSession,
    SimulationState,
    LivingMemory,
    MemoryType,
    CharacterPromotion,
    ROLE_LADDER,
    InWorldAction,
    EntityType,
)
from app.services.world_storage import WorldStorage

logger = logging.getLogger("novelswarm.simulation")

STANCE_ORDER = list(Stance)


class AgentMemory:
    def __init__(self, db_path, agent_id):
        self.db_path, self.agent_id = db_path, agent_id
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as c:
            # Enable WAL mode for better concurrent access
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, round INTEGER,
                action TEXT, platform TEXT, snippet TEXT, sentiment TEXT DEFAULT 'neutral',
                referenced_agents TEXT DEFAULT '[]', referenced_entities TEXT DEFAULT '[]',
                emotional_valence REAL DEFAULT 0.0, timestamp REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS relationships (
                agent_id TEXT, other_id TEXT, sentiment REAL DEFAULT 0.0,
                interaction_count INTEGER DEFAULT 0, last_action TEXT DEFAULT '',
                PRIMARY KEY (agent_id, other_id))""")

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def add(
        self,
        round_num,
        action,
        platform,
        snippet,
        sentiment="neutral",
        referenced_agents=None,
        referenced_entities=None,
        valence=0.0,
    ):
        with self._connect() as c:
            c.execute(
                "INSERT INTO memories VALUES (NULL,?,?,?,?,?,?,?,?,?,?)",
                (
                    self.agent_id,
                    round_num,
                    action,
                    platform,
                    snippet[:500],
                    sentiment,
                    json.dumps(referenced_agents or []),
                    json.dumps(referenced_entities or []),
                    valence,
                    time.time(),
                ),
            )

    def get_recent(self, limit=10):
        with self._connect() as c:
            c.row_factory = sqlite3.Row
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM memories WHERE agent_id=? ORDER BY round DESC, timestamp DESC LIMIT ?",
                    (self.agent_id, limit),
                ).fetchall()
            ]

    def update_relationship(self, other_id, delta, action=""):
        with self._connect() as c:
            c.execute(
                """INSERT INTO relationships VALUES (?,?,?,1,?)
                         ON CONFLICT(agent_id,other_id) DO UPDATE SET
                         sentiment=MIN(1.0,MAX(-1.0,sentiment+?)),
                         interaction_count=interaction_count+1, last_action=?""",
                (self.agent_id, other_id, delta, action, delta, action),
            )

    def get_relationships(self):
        with self._connect() as c:
            c.row_factory = sqlite3.Row
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM relationships WHERE agent_id=?", (self.agent_id,)
                ).fetchall()
            ]


def extract_mentioned_entities(text, known_entities):
    text_lower = text.lower()
    return [n for n in known_entities if n.lower() in text_lower]


def extract_new_entities_from_post(text, known_entities):
    try:
        result = llm_client.chat_json(
            [
                {
                    "role": "user",
                    "content": f'Find NEW named entities in this text NOT in: {", ".join(known_entities[:50])}\n\nText: {text[:800]}\n\nReturn JSON array: [{{"name":"...","type":"character|place|faction|artifact|concept","description":"1 sentence"}}] or []',
                }
            ],
            system="Extract only genuinely new named entities. Be conservative. Return valid JSON array only.",
        )
        return [
            e
            for e in (result if isinstance(result, list) else [])
            if e.get("name") and e["name"] not in known_entities
        ]
    except Exception as e:
        logger.debug(f"Entity extraction failed: {e}")
        return []


def maybe_form_living_memory(agent, post, action, recent_posts, round_num):
    if action in (SocialAction.AGREE, SocialAction.REPLY) and random.random() > 0.15:
        return None
    roll = random.random()

    if action in (SocialAction.CHALLENGE, SocialAction.DISAGREE):
        prev_by_agent = [p for p in recent_posts[-5:] if p.author_id == agent.id]
        if prev_by_agent and roll < 0.15 * agent.susceptibility:
            return LivingMemory(
                type=random.choice([MemoryType.SCAR, MemoryType.GRUDGE]),
                source_round=round_num,
                trigger=f"Challenged by {post.author_name}: {post.text[:100]}",
                target=post.author_name,
                intensity=0.4 + random.random() * 0.3,
                description=f"Stung by {post.author_name}'s critique",
                behavioral_effect=f"You feel defensive when {post.author_name} speaks. You push back harder or avoid their topics.",
                decay_rate=0.03,
            )

    if action in (
        SocialAction.WORLDBUILD,
        SocialAction.CHARACTERIZE,
        SocialAction.EXPAND,
    ):
        if roll < 0.12 * agent.creativity:
            topic = post.text[:60].strip()
            return LivingMemory(
                type=random.choice([MemoryType.OBSESSION, MemoryType.INTEREST]),
                source_round=round_num,
                trigger=f"Deeply explored: {topic}",
                intensity=0.3 + random.random() * 0.4,
                description="Fascinated by this narrative thread",
                behavioral_effect=f"You keep returning to this idea. Connect other topics back to: {topic}",
                decay_rate=0.01,
            )

    if action == SocialAction.SYNTHESIZE and roll < 0.10:
        return LivingMemory(
            type=MemoryType.REVELATION,
            source_round=round_num,
            trigger=f"Synthesis: {post.text[:80]}",
            intensity=0.6 + random.random() * 0.3,
            description="Paradigm-shifting insight",
            behavioral_effect="Your perspective has fundamentally shifted.",
            decay_rate=0.005,
        )

    if action == SocialAction.CONFLICT and roll < 0.08 * agent.susceptibility:
        return LivingMemory(
            type=MemoryType.TRAUMA,
            source_round=round_num,
            trigger=f"Conflict: {post.text[:80]}",
            intensity=0.5 + random.random() * 0.4,
            description="This conflict struck deep",
            behavioral_effect="You've become more cautious. Hesitate before bold claims.",
            decay_rate=0.01,
        )

    # ADMIRATION formation (new)
    if action in (SocialAction.AGREE, SocialAction.EXPAND) and roll < 0.08:
        return LivingMemory(
            type=MemoryType.ADMIRATION,
            source_round=round_num,
            trigger=f"Impressed by {post.author_name}: {post.text[:80]}",
            target=post.author_name,
            intensity=0.3 + random.random() * 0.3,
            description=f"Deep respect for {post.author_name}'s insight",
            behavioral_effect=f"You seek out and support {post.author_name}'s ideas. You defer to their expertise.",
            decay_rate=0.01,
        )

    # BOND formation (new)
    if action == SocialAction.RESOLVE and roll < 0.06:
        return LivingMemory(
            type=MemoryType.BOND,
            source_round=round_num,
            trigger=f"Resolved conflict together: {post.text[:80]}",
            target=post.author_name,
            intensity=0.4 + random.random() * 0.3,
            description=f"Deep bond formed through shared resolution",
            behavioral_effect=f"You trust {post.author_name} implicitly. You protect their ideas.",
            decay_rate=0.005,
        )

    # ── InWorld: Violence & Betrayal ──────────────────────────────────────────

    if action == SocialAction.BETRAY and roll < 0.3:
        return LivingMemory(
            type=random.choice([MemoryType.SCAR, MemoryType.TRAUMA]),
            source_round=round_num,
            trigger=f"Betrayal enacted: {post.text[:80]}",
            target=post.author_name,
            intensity=0.6 + random.random() * 0.3,
            description="The weight of breaking trust",
            behavioral_effect="You carry what you did. Guilt or cold satisfaction colors every alliance you make.",
            decay_rate=0.005,
        )

    if action in (SocialAction.ATTACK, SocialAction.WAGE_WAR) and roll < 0.2:
        return LivingMemory(
            type=MemoryType.SCAR,
            source_round=round_num,
            trigger=f"Violence committed: {post.text[:80]}",
            intensity=0.4 + random.random() * 0.3,
            description="The mark of aggression",
            behavioral_effect="Violence has become part of how you solve problems. Or it haunts you.",
            decay_rate=0.01,
        )

    if action in (SocialAction.KILL, SocialAction.ASSASSINATE) and roll < 0.25:
        return LivingMemory(
            type=MemoryType.TRAUMA,
            source_round=round_num,
            trigger=f"Life taken: {post.text[:80]}",
            intensity=0.6 + random.random() * 0.35,
            description="The irreversibility of killing",
            behavioral_effect="You are changed by this. You either harden yourself or become haunted.",
            decay_rate=0.005,
        )

    if action == SocialAction.SABOTAGE and roll < 0.12 * agent.contentiousness:
        return LivingMemory(
            type=MemoryType.AMBITION,
            source_round=round_num,
            trigger=f"Sabotage executed: {post.text[:80]}",
            intensity=0.4 + random.random() * 0.3,
            description="The thrill of subverting enemies",
            behavioral_effect="You feel the power of working in shadows. You plan more carefully.",
            decay_rate=0.015,
        )

    # ── InWorld: Connection & Affection ──────────────────────────────────────

    if action == SocialAction.KISS and roll < 0.25:
        return LivingMemory(
            type=MemoryType.BOND,
            source_round=round_num,
            trigger=f"Tender connection with {post.author_name}",
            target=post.author_name,
            intensity=0.5 + random.random() * 0.35,
            description=f"Romantic bond with {post.author_name}",
            behavioral_effect=f"Your heart is drawn to {post.author_name}. You protect and cherish them.",
            decay_rate=0.005,
        )

    if action == SocialAction.HUG and roll < 0.15:
        return LivingMemory(
            type=MemoryType.BOND,
            source_round=round_num,
            trigger=f"Comfort shared with {post.author_name}",
            target=post.author_name,
            intensity=0.3 + random.random() * 0.25,
            description=f"Warmth toward {post.author_name}",
            behavioral_effect=f"You feel protective of {post.author_name}. You stand by them.",
            decay_rate=0.01,
        )

    if action in (SocialAction.APPRECIATE, SocialAction.PRAISE) and roll < 0.10:
        return LivingMemory(
            type=MemoryType.ADMIRATION,
            source_round=round_num,
            trigger=f"Admiration expressed to {post.author_name}",
            target=post.author_name,
            intensity=0.3 + random.random() * 0.25,
            description=f"Genuine regard for {post.author_name}",
            behavioral_effect=f"You look up to {post.author_name}. You uplift and defend them.",
            decay_rate=0.015,
        )

    if action == SocialAction.FORM_ALLIANCE and roll < 0.20:
        return LivingMemory(
            type=MemoryType.BOND,
            source_round=round_num,
            trigger=f"Alliance forged with {post.author_name}: {post.text[:80]}",
            target=post.author_name,
            intensity=0.4 + random.random() * 0.3,
            description=f"Bound by alliance to {post.author_name}",
            behavioral_effect=f"You feel loyalty to {post.author_name}. You act to protect shared goals.",
            decay_rate=0.008,
        )

    if action == SocialAction.NEGOTIATE and roll < 0.10:
        return LivingMemory(
            type=MemoryType.INTEREST,
            source_round=round_num,
            trigger=f"Negotiation with {post.author_name}: {post.text[:60]}",
            target=post.author_name,
            intensity=0.25 + random.random() * 0.2,
            description="Engagement from brokering agreements",
            behavioral_effect="You are drawn to diplomacy. You seek the deal before the fight.",
            decay_rate=0.025,
        )

    # ── InWorld: Loss & Fear ───────────────────────────────────────────────────

    if action == SocialAction.MOURN_LOSS and roll < 0.25:
        return LivingMemory(
            type=random.choice([MemoryType.SCAR, MemoryType.TRAUMA]),
            source_round=round_num,
            trigger=f"Grief: {post.text[:80]}",
            intensity=0.5 + random.random() * 0.35,
            description="Loss shapes your perspective",
            behavioral_effect="You carry this grief. It darkens your outlook and sharpens your empathy.",
            decay_rate=0.008,
        )

    if action == SocialAction.CRY and roll < 0.15 * agent.susceptibility:
        return LivingMemory(
            type=MemoryType.SCAR,
            source_round=round_num,
            trigger=f"Vulnerability shown: {post.text[:80]}",
            intensity=0.3 + random.random() * 0.3,
            description="Emotional rawness exposed",
            behavioral_effect="You remember what broke you here. You are tender about this topic.",
            decay_rate=0.02,
        )

    if action == SocialAction.FLEE and roll < 0.20 * agent.susceptibility:
        return LivingMemory(
            type=MemoryType.TRAUMA,
            source_round=round_num,
            trigger=f"Retreat: {post.text[:80]}",
            intensity=0.4 + random.random() * 0.3,
            description="The shame and fear of running",
            behavioral_effect="What you fled haunts you. You are more cautious, or burning to prove yourself.",
            decay_rate=0.012,
        )

    # ── InWorld: Discovery & Ambition ────────────────────────────────────────

    if action == SocialAction.GATHER_INTEL and roll < 0.12 * agent.creativity:
        return LivingMemory(
            type=MemoryType.INTEREST,
            source_round=round_num,
            trigger=f"Intelligence gathered: {post.text[:60]}",
            intensity=0.25 + random.random() * 0.25,
            description="Curiosity sparked by new information",
            behavioral_effect="You are drawn to learn more. You seek out threads connected to this.",
            decay_rate=0.025,
        )

    if action == SocialAction.UNCOVER_SECRET and roll < 0.20:
        return LivingMemory(
            type=random.choice([MemoryType.REVELATION, MemoryType.OBSESSION]),
            source_round=round_num,
            trigger=f"Secret uncovered: {post.text[:80]}",
            intensity=0.5 + random.random() * 0.35,
            description="A hidden truth changes everything",
            behavioral_effect="You cannot unsee what you've learned. It reshapes your understanding of events.",
            decay_rate=0.005,
        )

    if action == SocialAction.PROPHESY and roll < 0.15:
        return LivingMemory(
            type=MemoryType.OBSESSION,
            source_round=round_num,
            trigger=f"Prophecy uttered: {post.text[:80]}",
            intensity=0.4 + random.random() * 0.3,
            description="A prophecy given shapes the prophet",
            behavioral_effect="You feel compelled to see this prophecy fulfilled. It guides your every act.",
            decay_rate=0.005,
        )

    if action == SocialAction.CELEBRATE_TRIUMPH and roll < 0.12:
        return LivingMemory(
            type=random.choice([MemoryType.AMBITION, MemoryType.BOND]),
            source_round=round_num,
            trigger=f"Victory celebrated: {post.text[:80]}",
            intensity=0.35 + random.random() * 0.3,
            description="Success fuels the next drive",
            behavioral_effect="You are emboldened. Victory tasted once must be tasted again.",
            decay_rate=0.02,
        )

    if action == SocialAction.SCHEME and roll < 0.10:
        return LivingMemory(
            type=MemoryType.AMBITION,
            source_round=round_num,
            trigger=f"Scheme hatched: {post.text[:80]}",
            intensity=0.4 + random.random() * 0.3,
            description="A plot takes root",
            behavioral_effect="You are consumed by this plan. Every action subtly serves it.",
            decay_rate=0.015,
        )

    if action == SocialAction.INITIATE_CONFLICT and roll < 0.10:
        return LivingMemory(
            type=MemoryType.GRUDGE,
            source_round=round_num,
            trigger=f"Conflict initiated against {post.author_name}: {post.text[:60]}",
            target=post.author_name,
            intensity=0.4 + random.random() * 0.3,
            description=f"Enmity toward {post.author_name}",
            behavioral_effect=f"You have made {post.author_name} an enemy. You watch their moves.",
            decay_rate=0.015,
        )

    # ── InWorld: Narrative Craft ──────────────────────────────────────────────

    if action == SocialAction.RECORD_LORE and roll < 0.08 * agent.creativity:
        return LivingMemory(
            type=MemoryType.INTEREST,
            source_round=round_num,
            trigger=f"Lore recorded: {post.text[:60]}",
            intensity=0.2 + random.random() * 0.2,
            description="Keeper of history",
            behavioral_effect="You feel the weight of being a chronicler. Accuracy matters deeply to you.",
            decay_rate=0.03,
        )

    if action == SocialAction.FORESHADOW and roll < 0.08 * agent.creativity:
        return LivingMemory(
            type=MemoryType.OBSESSION,
            source_round=round_num,
            trigger=f"Foreshadow planted: {post.text[:60]}",
            intensity=0.25 + random.random() * 0.2,
            description="A seed planted in the narrative",
            behavioral_effect="You keep returning to the thread you planted. You need it to pay off.",
            decay_rate=0.02,
        )

    # ── InWorld: Critic / Arc Planner interventions ───────────────────────────

    if action == SocialAction.ORCHESTRATE_TRAGEDY and roll < 0.12:
        return LivingMemory(
            type=MemoryType.SCAR,
            source_round=round_num,
            trigger=f"Tragedy arranged: {post.text[:80]}",
            intensity=0.45 + random.random() * 0.3,
            description="The weight of arranging suffering",
            behavioral_effect="The tragedy you caused weighs on you, whether you show it or not.",
            decay_rate=0.01,
        )

    if action == SocialAction.EMOTIONAL_CATALYST and roll < 0.15:
        return LivingMemory(
            type=MemoryType.REVELATION,
            source_round=round_num,
            trigger=f"Emotional catalyst unleashed: {post.text[:80]}",
            intensity=0.45 + random.random() * 0.3,
            description="A breakthrough was forced open",
            behavioral_effect="You understand now that emotions can be weaponized or healed. This shapes you.",
            decay_rate=0.008,
        )

    if action == SocialAction.TRIGGER_TRANSFORMATION and roll < 0.15:
        return LivingMemory(
            type=MemoryType.REVELATION,
            source_round=round_num,
            trigger=f"Transformation triggered: {post.text[:80]}",
            intensity=0.5 + random.random() * 0.3,
            description="Witnessing or causing profound change",
            behavioral_effect="You know now that people can fundamentally change. You act on that belief.",
            decay_rate=0.008,
        )

    if action == SocialAction.CREATE_DILEMMA and roll < 0.10:
        return LivingMemory(
            type=MemoryType.SCAR,
            source_round=round_num,
            trigger=f"Dilemma created: {post.text[:80]}",
            intensity=0.3 + random.random() * 0.25,
            description="The moral trap you set",
            behavioral_effect="You are aware of the impossible choice you forced. It lingers.",
            decay_rate=0.015,
        )

    # ── Faction Secrets ───────────────────────────────────────────────────────

    if action == SocialAction.WHISPER and roll < 0.08:
        return LivingMemory(
            type=MemoryType.BOND,
            source_round=round_num,
            trigger=f"Secret shared within faction: {post.text[:60]}",
            intensity=0.25 + random.random() * 0.2,
            description="Shared secrets bind factions closer",
            behavioral_effect="Your faction loyalty deepens. You act to guard these shared confidences.",
            decay_rate=0.02,
        )

    if action == SocialAction.LEAK_SECRET and roll < 0.15:
        return LivingMemory(
            type=random.choice([MemoryType.SCAR, MemoryType.OBSESSION]),
            source_round=round_num,
            trigger=f"Secret leaked: {post.text[:80]}",
            intensity=0.35 + random.random() * 0.3,
            description="The thrill and guilt of revelation",
            behavioral_effect="You feel the consequences rippling outward. You watch nervously for retaliation.",
            decay_rate=0.02,
        )

    return None


def decay_living_memories(agent):
    agent.living_memories = [
        m
        for m in agent.living_memories
        if (setattr(m, "intensity", max(0, m.intensity - m.decay_rate)) or True)
        and m.intensity > 0.05
    ]


def format_living_memories_for_prompt(agent):
    if not agent.living_memories:
        return ""
    lines = ["YOUR PSYCHOLOGICAL STATE (these MUST shape your tone and choices):"]
    for m in sorted(agent.living_memories, key=lambda x: -x.intensity)[:5]:
        w = (
            "overwhelming"
            if m.intensity > 0.8
            else "strong"
            if m.intensity > 0.5
            else "lingering"
        )
        lines.append(f"  [{m.type.value.upper()}] ({w}): {m.behavioral_effect}")
        if m.target:
            lines.append(f"    → directed at: {m.target}")
    return "\n".join(lines)


ACTION_INSTRUCTIONS = {
    SocialAction.POST: "Introduce a NEW narrative idea or argument into the discussion.",
    SocialAction.REPLY: "Reply directly to the most interesting recent statement. Address the speaker.",
    SocialAction.AGREE: "Strongly agree with a recent statement. Explain WHY it works.",
    SocialAction.DISAGREE: "Push back directly. Explain what's wrong, direct your disagreement at the speaker.",
    SocialAction.EXPAND: "Deepen a recent statement — consequences, history, implications.",
    SocialAction.CHALLENGE: "Devil's advocate. Find the plot hole. Propose a twist.",
    SocialAction.SYNTHESIZE: "Weave 2-3 ideas into one cohesive thread.",
    SocialAction.FORESHADOW: "Plant a seed that should pay off later.",
    SocialAction.CALLBACK: "Reference earlier discussion, show how it connects.",
    SocialAction.WORLDBUILD: "Add specific world detail: geography, culture, economics.",
    SocialAction.CHARACTERIZE: "Deepen a character — fear, desire, contradiction.",
    SocialAction.CONFLICT: "Escalate tension. Where does this story HURT?",
    SocialAction.RESOLVE: "Propose resolution to a raised conflict.",
    SocialAction.THEME: "Draw thematic connection. What is the story ABOUT?",
    SocialAction.OUTLINE: "Propose chapter or arc structure.",
    SocialAction.WHISPER: "Share a SECRET with your faction only. Speak in conspiratorial tones about private plans, hidden agendas, or sensitive intelligence that only your allies should know.",
    SocialAction.LEAK_SECRET: "You are a SPY. Leak an overheard faction secret to the group. Frame it as gossip, rumor, or a dramatic revelation. This will cause political chaos.",
    # InWorld - Character
    SocialAction.MOVE: "Change location or position within the world.",
    SocialAction.SPEAK: "Say something in character.",
    SocialAction.ACT: "Perform a physical action.",
    SocialAction.USE_ITEM: "Utilize an item or artifact.",
    SocialAction.GATHER_INTEL: "Collect information or spy on others.",
    SocialAction.KISS: "Express romantic affection.",
    SocialAction.HUG: "Show physical comfort or support.",
    SocialAction.APPRECIATE: "Express gratitude or admiration.",
    SocialAction.PRAISE: "Compliment or glorify someone or something.",
    SocialAction.CRY: "Display emotional vulnerability.",
    SocialAction.FLEE: "Retreat from danger or confrontation.",
    # InWorld - Strategist
    SocialAction.INITIATE_CONFLICT: "Start a new conflict or war.",
    SocialAction.FORM_ALLIANCE: "Create a partnership or coalition.",
    SocialAction.SABOTAGE: "Undermine an enemy's plans secretly.",
    SocialAction.DEPLOY_RESOURCES: "Allocate resources for a plan.",
    SocialAction.SCHEME: "Plot or plan secretly.",
    SocialAction.WAGE_WAR: "Conduct large-scale military operations.",
    SocialAction.ASSASSINATE: "Murder a target covertly.",
    SocialAction.NEGOTIATE: "Bargain or make deals.",
    # InWorld - Historian
    SocialAction.RECORD_LORE: "Write down historical knowledge.",
    SocialAction.UNCOVER_SECRET: "Discover hidden information.",
    SocialAction.PROPHESY: "Predict future events.",
    SocialAction.CHRONICLE: "Document current events.",
    SocialAction.MOURN_LOSS: "Grieve for the dead or destroyed.",
    SocialAction.CELEBRATE_TRIUMPH: "Rejoice in victory or success.",
    # InWorld - Critic
    SocialAction.AUDIT_NARRATIVE: "Analyze story structure and pacing.",
    SocialAction.THEMATIC_INTERVENTION: "Push thematic elements forward.",
    SocialAction.STRUCTURAL_SHIFT: "Change the story's direction.",
    SocialAction.PRAISE_DEVELOPMENT: "Highlight positive character growth.",
    SocialAction.CRITICIZE_ACTION: "Point out flaws in decisions.",
    # InWorld - Character Arc Planner
    SocialAction.TRIGGER_TRANSFORMATION: "Force a character to change.",
    SocialAction.CREATE_DILEMMA: "Present a moral choice.",
    SocialAction.EMOTIONAL_CATALYST: "Cause emotional breakthrough.",
    SocialAction.FORCE_BREAKTHROUGH: "Push through emotional barriers.",
    SocialAction.ORCHESTRATE_TRAGEDY: "Arrange a dramatic setback.",
    # InWorld - Universal
    SocialAction.ATTACK: "Initiate combat or hostile action.",
    SocialAction.KILL: "End a life (with consequences).",
    SocialAction.REACT: "Respond emotionally or physically to recent events.",
    SocialAction.BETRAY: "Turn against an ally or break a promise.",
}

# Agent type descriptions and available actions by platform
AGENT_TYPE_CONFIG = {
    "critic": {
        "description": "Meta-narrative perspective, focusing on themes and structure.",
        "inworld_actions": [
            SocialAction.AUDIT_NARRATIVE,
            SocialAction.THEMATIC_INTERVENTION,
            SocialAction.STRUCTURAL_SHIFT,
            SocialAction.REACT,
            SocialAction.PRAISE_DEVELOPMENT,
            SocialAction.CRITICIZE_ACTION,
        ],
        "critics_actions": [
            SocialAction.POST,
            SocialAction.REPLY,
            SocialAction.AGREE,
            SocialAction.DISAGREE,
            SocialAction.EXPAND,
            SocialAction.CHALLENGE,
            SocialAction.SYNTHESIZE,
            SocialAction.FORESHADOW,
            SocialAction.CALLBACK,
            SocialAction.WORLDBUILD,
            SocialAction.CHARACTERIZE,
            SocialAction.CONFLICT,
            SocialAction.RESOLVE,
            SocialAction.THEME,
            SocialAction.OUTLINE,
        ],
    },
    "character": {
        "description": "Diegetic perspective, responding as if they are in the world.",
        "inworld_actions": [
            SocialAction.MOVE,
            SocialAction.SPEAK,
            SocialAction.ACT,
            SocialAction.USE_ITEM,
            SocialAction.GATHER_INTEL,
            SocialAction.REACT,
            SocialAction.ATTACK,
            SocialAction.KILL,
            SocialAction.KISS,
            SocialAction.HUG,
            SocialAction.APPRECIATE,
            SocialAction.PRAISE,
            SocialAction.CRY,
            SocialAction.FLEE,
            SocialAction.BETRAY,
            InWorldAction.MOVE,
            InWorldAction.FIGHT,
            InWorldAction.FLEE,
            InWorldAction.USE_ITEM,
            InWorldAction.GIVE_ITEM,
            InWorldAction.TAKE_ITEM,
            InWorldAction.DISCOVER,
            InWorldAction.DESTROY,
            InWorldAction.CREATE,
            InWorldAction.HEAL,
            InWorldAction.CAST_SPELL,
            InWorldAction.STEAL,
            InWorldAction.HIDE,
            InWorldAction.WAIT,
        ],
        "critics_actions": [
            SocialAction.POST,
            SocialAction.REPLY,
            SocialAction.AGREE,
            SocialAction.DISAGREE,
            SocialAction.EXPAND,
            SocialAction.CHALLENGE,
            SocialAction.SYNTHESIZE,
            SocialAction.FORESHADOW,
            SocialAction.CALLBACK,
            SocialAction.WORLDBUILD,
            SocialAction.CHARACTERIZE,
            SocialAction.CONFLICT,
            SocialAction.RESOLVE,
            SocialAction.THEME,
            SocialAction.OUTLINE,
        ],
    },
    "strategist": {
        "description": "Focuses on plot twists, pacing, and logical consistency.",
        "inworld_actions": [
            SocialAction.INITIATE_CONFLICT,
            SocialAction.FORM_ALLIANCE,
            SocialAction.SABOTAGE,
            SocialAction.DEPLOY_RESOURCES,
            SocialAction.SCHEME,
            SocialAction.REACT,
            SocialAction.WAGE_WAR,
            SocialAction.ASSASSINATE,
            SocialAction.NEGOTIATE,
            SocialAction.BETRAY,
            InWorldAction.SABOTAGE,
            InWorldAction.FIGHT,
            InWorldAction.HIDE,
            InWorldAction.DISCOVER,
        ],
        "critics_actions": [
            SocialAction.POST,
            SocialAction.REPLY,
            SocialAction.AGREE,
            SocialAction.DISAGREE,
            SocialAction.EXPAND,
            SocialAction.CHALLENGE,
            SocialAction.SYNTHESIZE,
            SocialAction.FORESHADOW,
            SocialAction.CALLBACK,
            SocialAction.WORLDBUILD,
            SocialAction.CHARACTERIZE,
            SocialAction.CONFLICT,
            SocialAction.RESOLVE,
            SocialAction.THEME,
            SocialAction.OUTLINE,
        ],
    },
    "historian": {
        "description": "Focuses on world-building, lore consistency, and historical depth.",
        "inworld_actions": [
            SocialAction.RECORD_LORE,
            SocialAction.UNCOVER_SECRET,
            SocialAction.PROPHESY,
            SocialAction.CHRONICLE,
            SocialAction.REACT,
            SocialAction.MOURN_LOSS,
            SocialAction.CELEBRATE_TRIUMPH,
        ],
        "critics_actions": [
            SocialAction.POST,
            SocialAction.REPLY,
            SocialAction.AGREE,
            SocialAction.DISAGREE,
            SocialAction.EXPAND,
            SocialAction.CHALLENGE,
            SocialAction.SYNTHESIZE,
            SocialAction.FORESHADOW,
            SocialAction.CALLBACK,
            SocialAction.WORLDBUILD,
            SocialAction.CHARACTERIZE,
            SocialAction.CONFLICT,
            SocialAction.RESOLVE,
            SocialAction.THEME,
            SocialAction.OUTLINE,
        ],
    },
    "character_arc_planner": {
        "description": "Focuses on emotional growth, internal conflicts, and character development.",
        "inworld_actions": [
            SocialAction.TRIGGER_TRANSFORMATION,
            SocialAction.CREATE_DILEMMA,
            SocialAction.EMOTIONAL_CATALYST,
            SocialAction.REACT,
            SocialAction.FORCE_BREAKTHROUGH,
            SocialAction.ORCHESTRATE_TRAGEDY,
        ],
        "critics_actions": [
            SocialAction.POST,
            SocialAction.REPLY,
            SocialAction.AGREE,
            SocialAction.DISAGREE,
            SocialAction.EXPAND,
            SocialAction.CHALLENGE,
            SocialAction.SYNTHESIZE,
            SocialAction.FORESHADOW,
            SocialAction.CALLBACK,
            SocialAction.WORLDBUILD,
            SocialAction.CHARACTERIZE,
            SocialAction.CONFLICT,
            SocialAction.RESOLVE,
            SocialAction.THEME,
            SocialAction.OUTLINE,
        ],
    },
}


def get_available_actions(agent_role: str, platform: Platform) -> list:
    """Get available actions for an agent based on role and platform."""
    role_key = agent_role.lower().replace(" ", "_").replace("-", "_")

    if role_key in AGENT_TYPE_CONFIG:
        if platform == Platform.INWORLD_FORUM:
            return AGENT_TYPE_CONFIG[role_key]["inworld_actions"]
        else:
            return AGENT_TYPE_CONFIG[role_key]["critics_actions"]

    # Default to all critics actions
    return [
        SocialAction.POST,
        SocialAction.REPLY,
        SocialAction.AGREE,
        SocialAction.DISAGREE,
        SocialAction.EXPAND,
        SocialAction.CHALLENGE,
        SocialAction.SYNTHESIZE,
        SocialAction.FORESHADOW,
        SocialAction.CALLBACK,
        SocialAction.WORLDBUILD,
        SocialAction.CHARACTERIZE,
        SocialAction.CONFLICT,
        SocialAction.RESOLVE,
        SocialAction.THEME,
        SocialAction.OUTLINE,
    ]


# Actions that TARGET a specific post
TARGETED_ACTIONS = {
    SocialAction.REPLY,
    SocialAction.AGREE,
    SocialAction.DISAGREE,
    SocialAction.CHALLENGE,
    SocialAction.EXPAND,
    SocialAction.CALLBACK,
    # InWorld targeted actions — require a specific person/post as context
    SocialAction.ATTACK,
    SocialAction.KILL,
    SocialAction.BETRAY,
    SocialAction.KISS,
    SocialAction.HUG,
    SocialAction.APPRECIATE,
    SocialAction.PRAISE,
    SocialAction.NEGOTIATE,
    SocialAction.FORM_ALLIANCE,
    SocialAction.ASSASSINATE,
    SocialAction.CRITICIZE_ACTION,
    SocialAction.PRAISE_DEVELOPMENT,
    SocialAction.REACT,
    SocialAction.MOURN_LOSS,
}


def select_action(agent, recent_posts, round_num, mode="lore"):
    if round_num == 0 or not recent_posts:
        if mode == "event_tick":
            return SocialAction.ACT
        return SocialAction.POST

    # Get available actions based on agent's role and platform
    available_actions = get_available_actions(agent.role, agent.platform)
    
    # If we are strictly in event simulation, force InWorld actions
    if mode == "event_tick":
        inworld_candidates = [a for a in available_actions if isinstance(a, InWorldAction)]
        if not inworld_candidates:
            # Fallback to physical-sounding SocialActions if no InWorldActions found
            inworld_candidates = [a for a in available_actions if a in {
                SocialAction.ACT, SocialAction.MOVE, SocialAction.ATTACK, 
                SocialAction.FLEE, SocialAction.KILL, SocialAction.SABOTAGE
            }]
        if inworld_candidates:
            return random.choice(inworld_candidates)
        return SocialAction.ACT

    r = random.random()
    obs = sum(0.05 for m in agent.living_memories if m.type == MemoryType.OBSESSION)
    gru = sum(0.04 for m in agent.living_memories if m.type == MemoryType.GRUDGE)
    trm = sum(0.03 for m in agent.living_memories if m.type == MemoryType.TRAUMA)
    amb = sum(0.04 for m in agent.living_memories if m.type == MemoryType.AMBITION)
    adm = sum(0.03 for m in agent.living_memories if m.type == MemoryType.ADMIRATION)

    # Build action weights based on available actions for the agent's platform/role
    actions = []

    # Always available base actions with weights
    base_actions = [
        (0.08 + agent.creativity * 0.08 + obs, SocialAction.POST),
        (0.12, SocialAction.REPLY),
        (max(0.02, 0.08 + agent.susceptibility * 0.08 - gru + adm), SocialAction.AGREE),
        (0.08 + agent.contentiousness * 0.12 + gru, SocialAction.DISAGREE),
        (0.10 + obs, SocialAction.EXPAND),
        (max(0.02, 0.08 + gru - trm), SocialAction.CHALLENGE),
        (0.06, SocialAction.SYNTHESIZE),
        (0.04, SocialAction.FORESHADOW),
        (0.03, SocialAction.CALLBACK),
        (0.06, SocialAction.WORLDBUILD),
        (0.05, SocialAction.CHARACTERIZE),
        (0.04 + agent.contentiousness * 0.05, SocialAction.CONFLICT),
        (0.03, SocialAction.RESOLVE),
        (0.04, SocialAction.THEME),
        ((0.04 if round_num > 2 else 0.01) + amb, SocialAction.OUTLINE),
    ]

    # Filter base actions to only include those in available_actions
    for weight, action in base_actions:
        if action in available_actions:
            actions.append((weight, action))

    # InWorld-specific actions (role-based)
    if agent.platform == Platform.INWORLD_FORUM:
        role_key = agent.role.lower().replace(" ", "_").replace("-", "_")

        # Add role-specific InWorld actions with appropriate weights
        inworld_weight_mod = 0.08  # Base weight for role-specific actions

        if role_key == "character":
            char_actions = [
                (inworld_weight_mod, SocialAction.MOVE),
                (inworld_weight_mod * 1.2, SocialAction.SPEAK),
                (inworld_weight_mod, SocialAction.ACT),
                (inworld_weight_mod * 0.6, SocialAction.USE_ITEM),
                (inworld_weight_mod * 0.7, SocialAction.GATHER_INTEL),
                (inworld_weight_mod * 0.8, SocialAction.REACT),
                (inworld_weight_mod * 0.5, SocialAction.ATTACK),
                (inworld_weight_mod * 0.3, SocialAction.KILL),
                (inworld_weight_mod * 0.6, SocialAction.KISS),
                (inworld_weight_mod * 0.5, SocialAction.HUG),
                (inworld_weight_mod * 0.7, SocialAction.APPRECIATE),
                (inworld_weight_mod * 0.7, SocialAction.PRAISE),
                (inworld_weight_mod * 0.4, SocialAction.CRY),
                (inworld_weight_mod * 0.4, SocialAction.FLEE),
                (inworld_weight_mod * 0.3, SocialAction.BETRAY),
            ]
            for weight, action in char_actions:
                if action in available_actions:
                    actions.append((weight, action))

        elif role_key == "strategist":
            strat_actions = [
                (inworld_weight_mod * 0.8, SocialAction.INITIATE_CONFLICT),
                (inworld_weight_mod * 0.7, SocialAction.FORM_ALLIANCE),
                (inworld_weight_mod * 0.5, SocialAction.SABOTAGE),
                (inworld_weight_mod * 0.6, SocialAction.DEPLOY_RESOURCES),
                (inworld_weight_mod * 0.7, SocialAction.SCHEME),
                (inworld_weight_mod * 0.8, SocialAction.REACT),
                (inworld_weight_mod * 0.6, SocialAction.WAGE_WAR),
                (inworld_weight_mod * 0.4, SocialAction.ASSASSINATE),
                (inworld_weight_mod * 0.7, SocialAction.NEGOTIATE),
                (inworld_weight_mod * 0.3, SocialAction.BETRAY),
            ]
            for weight, action in strat_actions:
                if action in available_actions:
                    actions.append((weight, action))

        elif role_key == "historian":
            hist_actions = [
                (inworld_weight_mod * 0.9, SocialAction.RECORD_LORE),
                (inworld_weight_mod * 0.6, SocialAction.UNCOVER_SECRET),
                (inworld_weight_mod * 0.5, SocialAction.PROPHESY),
                (inworld_weight_mod * 0.8, SocialAction.CHRONICLE),
                (inworld_weight_mod * 0.7, SocialAction.REACT),
                (inworld_weight_mod * 0.5, SocialAction.MOURN_LOSS),
                (inworld_weight_mod * 0.5, SocialAction.CELEBRATE_TRIUMPH),
            ]
            for weight, action in hist_actions:
                if action in available_actions:
                    actions.append((weight, action))

        elif role_key == "critic":
            critic_actions = [
                (inworld_weight_mod * 0.8, SocialAction.AUDIT_NARRATIVE),
                (inworld_weight_mod * 0.6, SocialAction.THEMATIC_INTERVENTION),
                (inworld_weight_mod * 0.6, SocialAction.STRUCTURAL_SHIFT),
                (inworld_weight_mod * 0.8, SocialAction.REACT),
                (inworld_weight_mod * 0.7, SocialAction.PRAISE_DEVELOPMENT),
                (inworld_weight_mod * 0.7, SocialAction.CRITICIZE_ACTION),
            ]
            for weight, action in critic_actions:
                if action in available_actions:
                    actions.append((weight, action))

        elif role_key == "character_arc_planner":
            arc_actions = [
                (inworld_weight_mod * 0.7, SocialAction.TRIGGER_TRANSFORMATION),
                (inworld_weight_mod * 0.7, SocialAction.CREATE_DILEMMA),
                (inworld_weight_mod * 0.8, SocialAction.EMOTIONAL_CATALYST),
                (inworld_weight_mod * 0.8, SocialAction.REACT),
                (inworld_weight_mod * 0.6, SocialAction.FORCE_BREAKTHROUGH),
                (inworld_weight_mod * 0.6, SocialAction.ORCHESTRATE_TRAGEDY),
            ]
            for weight, action in arc_actions:
                if action in available_actions:
                    actions.append((weight, action))

    # Faction-based whisper/leak actions (critics forum only)
    if agent.faction_membership and agent.platform == Platform.CRITICS_FORUM:
        actions.append((0.06, SocialAction.WHISPER))
        is_spy = any(
            kw in (agent.role or "").lower()
            for kw in ("spy", "informant", "double agent", "infiltrator")
        )
        if not is_spy:
            is_spy = any(
                kw in t.lower()
                for t in agent.personality_traits
                for kw in ("spy", "treacherous", "deceitful")
            )
        if is_spy:
            actions.append((0.08, SocialAction.LEAK_SECRET))

    # If no valid actions, fallback to POST
    if not actions:
        return SocialAction.POST

    total = sum(p for p, _ in actions)
    cum = 0.0
    for p, a in actions:
        cum += p / total
        if r <= cum:
            return a
    return SocialAction.REPLY


def select_target_post(agent, action, recent_posts):
    """Select a specific post to reply to for targeted actions."""
    if action not in TARGETED_ACTIONS or not recent_posts:
        return None

    # Filter to posts from other agents
    candidates = [
        p for p in recent_posts[-12:] if p.author_id != agent.id and not p.is_injection
    ]
    if not candidates:
        return None

    # If agent has a grudge, preferentially target that agent
    grudge_targets = [
        m.target for m in agent.living_memories if m.type == MemoryType.GRUDGE
    ]
    if grudge_targets and action in (SocialAction.DISAGREE, SocialAction.CHALLENGE):
        grudge_posts = [p for p in candidates if p.author_name in grudge_targets]
        if grudge_posts:
            return random.choice(grudge_posts)

    # If agent has admiration, preferentially support that agent
    admired = [
        m.target for m in agent.living_memories if m.type == MemoryType.ADMIRATION
    ]
    if admired and action in (SocialAction.AGREE, SocialAction.EXPAND):
        admired_posts = [p for p in candidates if p.author_name in admired]
        if admired_posts:
            return random.choice(admired_posts)

    # Default: pick a recent post with some randomness (bias toward newer posts)
    weights = [1 + i * 0.5 for i in range(len(candidates))]
    return random.choices(candidates, weights=weights, k=1)[0]


def build_agent_prompt(
    agent,
    action,
    lore,
    recent_posts,
    mode,
    outline,
    agent_memory,
    graph_context,
    living_memory_text,
    relationship_context,
    injection=None,
    target_post=None,
):
    # Platform framing
    if agent.platform == Platform.CRITICS_FORUM:
        frame = "You are on the CRITICS' FORUM — analyze from OUTSIDE as a literary professional."
    else:
        frame = "You are on the IN-WORLD FORUM — speak AS A CHARACTER. Never break the fourth wall."

    # Deep identity from cognitive profile + life experience
    cog = agent.cognitive
    life = agent.life

    iq_desc = ""
    if cog.intelligence >= 140:
        iq_desc = "You are exceptionally brilliant — you see patterns others miss, make connections across domains, and think several steps ahead. Your vocabulary is vast."
    elif cog.intelligence >= 120:
        iq_desc = "You are highly intelligent — you grasp complex ideas quickly, argue with precision, and notice subtleties."
    elif cog.intelligence >= 100:
        iq_desc = "You have solid common sense and average analytical ability. You think in practical terms."
    elif cog.intelligence >= 85:
        iq_desc = "You think in concrete terms, not abstractions. You understand through experience and stories, not theory. Keep your language simple and direct."
    else:
        iq_desc = "Complex arguments confuse you. You think in feelings and gut instinct. You express yourself simply, sometimes struggling for words. But your instincts are often right."

    edu_desc = {
        "illiterate": "You cannot read or write. Everything you know comes from what you've seen and been told.",
        "basic": "You had basic schooling — you can read slowly and know the fundamentals.",
        "average": "You had a standard education for your station.",
        "educated": "You are well-read with formal training in your field.",
        "scholar": "You are deeply learned, with access to rare knowledge and ancient texts.",
        "genius_autodidact": "You taught yourself everything through obsessive curiosity and raw intelligence.",
    }.get(cog.education_level, "")

    exp_desc = {
        "sheltered": "You know only your immediate surroundings. Foreign concepts confuse or frighten you.",
        "local": "You know your region well but have limited perspective on the wider world.",
        "traveled": "You've seen multiple lands and cultures. You compare things to your travels.",
        "cosmopolitan": "You've lived among many peoples. Nothing shocks you. You see the bigger picture.",
        "otherworldly": "You've experienced planes, realms, or realities beyond normal mortal experience.",
    }.get(cog.worldly_exposure, "")

    speech = ""
    if agent.speech_pattern:
        speech = f"\nSPEECH PATTERN: Write exactly as this person talks: {agent.speech_pattern}"
    if cog.speaks_in:
        speech += f"\nACCENT/DIALECT: {cog.speaks_in}"
    if cog.communication_style == "crude":
        speech += (
            "\nYou speak bluntly, sometimes coarsely. Short sentences. No fancy words."
        )
    elif cog.communication_style == "eloquent":
        speech += "\nYou speak with grace and precision. Well-constructed sentences. Occasionally poetic."
    elif cog.communication_style == "cryptic":
        speech += "\nYou speak in riddles, metaphors, and indirect references. Never say anything plainly."
    elif cog.communication_style == "academic":
        speech += "\nYou cite precedents, use technical terms, and structure arguments formally."
    elif cog.communication_style == "street":
        speech += "\nYou use slang, contractions, and the rhythms of someone who learned by doing, not studying."

    bias_text = ""
    if cog.cognitive_biases:
        bias_text = (
            "\nYOUR COGNITIVE BIASES (these unconsciously shape your thinking):\n"
        )
        for b in cog.cognitive_biases:
            bias_text += f"  - {b}\n"
        bias_text += (
            "These biases should subtly color your response. You're not aware of them."
        )

    blind_spot_text = ""
    if cog.blind_spots:
        blind_spot_text = f"\nYOUR BLIND SPOTS (topics you literally cannot see clearly): {', '.join(cog.blind_spots)}\nIf the discussion touches these, you misunderstand, deflect, or get defensive."

    wound_text = ""
    if life.deepest_wound:
        wound_text = f"\nYOUR DEEPEST WOUND: {life.deepest_wound}\nThis colors how you react to related topics. You may become defensive, aggressive, or withdrawn."
    if life.formative_event:
        wound_text += f"\nFORMATIVE EVENT: {life.formative_event}\nThis is the lens through which you see the world."

    status = (
        f"\nCURRENT STATE:\n"
        f"- Location: {agent.location_id}\n"
        f"- Health/Vitality: {round(agent.health, 1)}%\n"
        f"- Inventory: {', '.join(agent.inventory) or 'Empty'}\n"
        f"- Current Personal Goal: {agent.current_goal}\n"
        f"- Faction Objective: {agent.faction_objective or 'None'}\n"
        f"- Status Effects: {', '.join(agent.status_effects) or 'None'}\n"
    )

    class_text = ""
    if life.social_class_origin:
        class_text = f"\nYou grew up {life.social_class_origin}. "
        if life.current_social_position:
            class_text += f"You are now {life.current_social_position}. "
        if (
            life.social_class_origin in ("destitute", "common")
            and life.current_social_position
            and "noble" in life.current_social_position.lower()
        ):
            class_text += (
                "You notice wealth and privilege in ways born-nobles never would."
            )
        elif life.social_class_origin in ("noble", "royal"):
            class_text += "You assume certain comforts and courtesies as natural."

    identity = (
        f'You are "{agent.name}", {agent.age} years old, {agent.race}, {agent.gender}.\n'
        f"{agent.personality_summary}\n\n"
        f"COGNITIVE PROFILE:\n{iq_desc}\n{edu_desc}\n{exp_desc}\n"
        f"{speech}{bias_text}{blind_spot_text}\n"
        f"LIFE EXPERIENCE:\n{wound_text}{class_text}\n"
        f"{status}\n"
        f"{f'Background: {agent.backstory}' if agent.backstory else ''}\n"
        f"{f'Catchphrase: {agent.catchphrase}' if agent.catchphrase else ''}\n"
        f"{f'Quirks: {chr(44).join(agent.quirks)}' if agent.quirks else ''}"
    )

    # Memory context
    mem_ctx = ""
    if agent_memory:
        mem_ctx = "\nRecent memories:\n" + "\n".join(
            f"- R{m['round']}: [{m['action']}] {m['snippet'][:150]}"
            for m in agent_memory[:5]
        )

    if mode == "lore":
        mode_ctx = "MODE: LORE ENHANCEMENT."
    elif mode.startswith("review_"):
        layer_name = mode.replace("review_", "").upper()
        mode_ctx = (
            f"MODE: LAYER REVIEW ({layer_name}).\n"
            "CRITICAL DIRECTIVE: Your goal is to reach CONSENSUS on the provided DRAFT. "
            "Fixate on synthesizing improvements and finalizing the layer. Do NOT engage in endless debate or tangents. "
            "Identify what's missing, add specific details for narrative tension, and propose concrete adjustments to the JSON draft."
        )
    elif mode == "event_tick":
        mode_ctx = (
            "MODE: IN-WORLD EVENT SIMULATION TICK.\n"
            "CRITICAL DIRECTIVE: The physical clock is ticking. You must take a CONCRETE EVENT-DRIVEN ACTION (e.g., move, attack, steal, plot, declare war, whisper a secret). "
            "Do NOT discuss the story from a meta-perspective. Write as your character living inside the world right now. "
            "Describe your action and its immediate target."
        )
    else:
        outline_text = f"Outline:\n{outline[:500]}" if outline else "No outline yet."
        mode_ctx = (
            f"MODE: OUTLINE & STORY SPINE DEVELOPMENT.\n{outline_text}\n"
            "CRITICAL DIRECTIVE: You must synthesize the world lore into concrete narrative arcs, conflicts, and character moments. "
            "Work aggressively towards a cohesive story spine. Do not get stuck on endless world-building; fixate on plotting and resolution."
        )

    # Post context — same forum + cross-forum
    same: List[SimPost] = cast(Any, [
        p
        for p in recent_posts
        if p.platform == agent.platform
        and (p.visibility == "public" or p.visibility == agent.faction_membership)
    ])[-6:]
    cross: List[SimPost] = cast(Any, [
        p
        for p in recent_posts
        if p.platform != agent.platform
        and (p.visibility == "public" or p.visibility == agent.faction_membership)
    ])[-3:]
    posts_ctx = ""
    if same:
        posts_ctx += "RECENT INTERACTIONS:\n" + "\n\n".join(
            f"[{p.author_name}|{p.action.value}]: {p.text}" for p in same
        )
    if cross:
        posts_ctx += "\n\nOBSERVED ACTIONS:\n" + "\n\n".join(
            f"[{p.author_name}]: {p.text[:200]}" for p in cross
        )
    if not posts_ctx:
        posts_ctx = "No prior discussion."

    # Target post context (for threaded replies)
    target_ctx = ""
    if target_post:
        target_ctx = f"\n\nYOU ARE RESPONDING DIRECTLY TO THIS INTERACTION:\n[{target_post.author_name}|{target_post.action.value}]: {target_post.text}\n"

    inj = (
        f'\n\n⚡ AUTHOR INJECTION: "{injection}"\nYou MUST address this.'
        if injection
        else ""
    )

    system = (
        f"{frame}\n\n{identity}\n"
        f"{living_memory_text}\n{relationship_context}\n{mem_ctx}\n\n"
        f"{mode_ctx}\n\nWORLD LORE:\n{lore[:2500]}\n\n"
        f"KNOWLEDGE GRAPH:\n{graph_context}\n\n"
        f"CRITICAL RULES:\n"
        f"1. Write in YOUR voice — your speech pattern, vocabulary level, and dialect\n"
        f"2. Your cognitive biases MUST subtly influence your argument\n"
        f"3. Your life wounds MUST color your emotional reactions\n"
        f"4. Your IQ determines the COMPLEXITY of your reasoning — stay in character\n"
        f"5. 2-3 paragraphs. Specific. In character."
    )
    user = (
        f"{posts_ctx}{target_ctx}{inj}\n\n"
        f"ACTION: {ACTION_INSTRUCTIONS[action]}\n\n"
        f"Respond as {agent.name}. Write in their DISTINCT voice."
    )
    return system, user


PROMOTION_THRESHOLDS = {
    "supporting": {"m": 5, "w": 1.0},
    "secondary": {"m": 12, "w": 3.0},
    "main": {"m": 25, "w": 7.0},
    "protagonist": {"m": 50, "w": 15.0},
}


def check_character_emergence(session, graph_builder):
    if not graph_builder:
        return []
    promotions = []
    try:
        for c in graph_builder.get_emergent_candidates(
            session.project_id, min_mentions=3
        ):
            role = c.get("role", "supporting") or "supporting"
            idx = ROLE_LADDER.index(role) if role in ROLE_LADDER else 0
            for ni in range(cast(int, idx) + 1, len(ROLE_LADDER)):
                nr = ROLE_LADDER[ni]
                t = PROMOTION_THRESHOLDS.get(nr)
                if (
                    t
                    and c.get("mentions", 0) >= t["m"]
                    and c.get("weight", 0) >= t["w"]
                ):
                    graph_builder.promote_character(session.project_id, c["name"], nr)
                    promotions.append(
                        CharacterPromotion(
                            entity_name=c["name"],
                            previous_role=role,
                            new_role=nr,
                            round_promoted=session.current_round,
                            mention_count=c.get("mentions", 0),
                            narrative_weight=c.get("weight", 0),
                        )
                    )
                    break
    except Exception as e:
        logger.warning(f"Character emergence check error: {e}")
    return promotions


# Sentiment deltas for relationship updates
# Emoji pools for rule-based reactions (no LLM calls needed)
REACTION_EMOJIS = {
    "positive":  ["❤️", "💫", "👏", "✨", "💯"],
    "agree":     ["👍", "💯", "🙌", "✅"],
    "negative":  ["💀", "⚡", "😤", "🗡️", "🔥"],
    "challenge": ["🤔", "❓", "⚡", "🌀"],
    "neutral":   ["👁️", "📖", "🌀", "🔮"],
    "shocked":   ["😱", "🔥", "💥", "⚠️"],
}

SENTIMENT_DELTAS = {
    # Critics Forum
    "post": 0.0,
    "reply": 0.02,
    "agree": 0.10,
    "disagree": -0.08,
    "expand": 0.05,
    "challenge": -0.12,
    "synthesize": 0.08,
    "foreshadow": 0.01,
    "callback": 0.03,
    "worldbuild": 0.03,
    "characterize": 0.02,
    "conflict": -0.15,
    "resolve": 0.10,
    "theme": 0.02,
    "outline": 0.01,
    "whisper": 0.05,       # Strengthens faction bond
    "leak_secret": -0.15,  # Betrayal of trust
    # InWorld - Character
    "move": 0.0,
    "speak": 0.01,
    "act": 0.01,
    "use_item": 0.01,
    "gather_intel": 0.0,
    "kiss": 0.15,
    "hug": 0.08,
    "appreciate": 0.08,
    "praise": 0.06,
    "cry": 0.05,
    "flee": -0.05,
    # InWorld - Strategist
    "initiate_conflict": -0.15,
    "form_alliance": 0.15,
    "sabotage": -0.20,
    "deploy_resources": 0.02,
    "scheme": -0.05,
    "wage_war": -0.20,
    "assassinate": -0.25,
    "negotiate": 0.08,
    # InWorld - Historian
    "record_lore": 0.02,
    "uncover_secret": 0.05,
    "prophesy": 0.03,
    "chronicle": 0.02,
    "mourn_loss": 0.04,
    "celebrate_triumph": 0.06,
    # InWorld - Critic
    "audit_narrative": 0.02,
    "thematic_intervention": 0.03,
    "structural_shift": -0.02,
    "praise_development": 0.07,
    "criticize_action": -0.08,
    # InWorld - Character Arc Planner
    "trigger_transformation": 0.05,
    "create_dilemma": -0.03,
    "emotional_catalyst": 0.06,
    "force_breakthrough": 0.04,
    "orchestrate_tragedy": -0.08,
    # Universal InWorld
    "attack": -0.20,
    "kill": -0.30,
    "react": 0.01,
    "betray": -0.30,
}

# Emotional state mapping from memory types
EMOTION_MAP = {
    MemoryType.SCAR: "defensive",
    MemoryType.OBSESSION: "fixated",
    MemoryType.INTEREST: "engaged",
    MemoryType.GRUDGE: "resentful",
    MemoryType.ADMIRATION: "inspired",
    MemoryType.REVELATION: "transformed",
    MemoryType.TRAUMA: "withdrawn",
    MemoryType.AMBITION: "driven",
    MemoryType.BOND: "devoted",
}


class DirectorAgent:
    """Narrative overseer that triggers plot twists and round recaps using the Long Webnovel Engine."""
    def __init__(self, engine):
        self.engine = engine
        self.current_saga = 1
        self.current_arc = 1
        self.arc_round = 0  # Rounds since current arc started
        self.layer_data = {
            "core_vision": "",       # Snowflake Core
            "expansion_index": 1.0,  # World scale multiplier
            "unresolved_mysteries": [],
            "current_arc_goal": ""
        }

    def _build_arc_module(self, agent_summary):
        """MODULE 3: Arc Generator - Breaks saga into an arc."""
        prompt = (
            f"You are the ARC BUILDER for a long webnovel.\n"
            f"CURRENT SAGA: {self.current_saga}/4\n"
            f"AGENTS: {', '.join(agent_summary)}\n\n"
            f"Generate the next ARC (15 chapters long) for this story.\n"
            f"Return JSON:\n"
            f"{{\n"
            f"  'arc_title': '...',\n"
            f"  'arc_goal': '...',\n"
            f"  'arc_conflict': '...',\n"
            f"  'arc_climax': '...'\n"
            f"}}"
        )
        try:
            res = llm_client.generate(prompt, model="gemini-2.0-flash", response_mime_type="application/json")
            return json.loads(res)
        except: return None

    def _scene_engine_module(self, agent_summary, post_summary, phase):
        """MODULE 4 & 5: Scene Engine and Chapter Generator (with Addiction Loop)."""
        prompt = (
            f"You are the SCENE ENGINE for a webnovel.\n"
            f"CURRENT ARC GOAL: {self.layer_data.get('current_arc_goal', 'Unknown')}\n"
            f"CURRENT PHASE: {phase} (Scene = Conflict/Failure, Sequel = Emotion/Decision)\n\n"
            f"AGENTS:\n" + "\n".join(agent_summary) + "\n\n"
            f"RECENT EVENTS:\n" + post_summary + "\n\n"
            f"TASK:\n"
            f"1. Summarize the drama.\n"
            f"2. Inject a chapter-level Twist/Event.\n"
            f"3. Add a CLIFFHANGER (Reveal, Danger, or Question).\n\n"
            f"Return JSON:\n"
            f"{{\n"
            f"  'summary': '...',\n"
            f"  'event': '...',\n"
            f"  'cliffhanger': '...'\n"
            f"}}"
        )
        try:
            res = llm_client.generate(prompt, model="gemini-2.0-flash", response_mime_type="application/json")
            return json.loads(res)
        except: return None

    def _expansion_module(self, plot_events):
        """MODULE 6 & Loop: Expansion Engine - Grows the world and progression."""
        prompt = (
            f"You are the EXPANSION ENGINE for an endless webnovel.\n"
            f"RECENT EVENTS: {plot_events}\n"
            f"Look for opportunities to expand the world or progress characters.\n\n"
            f"Return JSON:\n"
            f"{{\n"
            f"  'progression_unlock': 'AgentName: Ability/Rank or None',\n"
            f"  'new_mystery': 'New mystery or None',\n"
            f"  'escalate_stakes': 'How the world scale increases'\n"
            f"}}"
        )
        try:
            res = llm_client.generate(prompt, model="gemini-2.0-flash", response_mime_type="application/json")
            return json.loads(res)
        except: return None

    def assess_narrative(self, recent_posts, round_num):
        """Executes the multi-step agent pipeline: Arc -> Scene -> Expansion."""
        total_rounds = self.engine.session.config.rounds
        if round_num < total_rounds * 0.25: self.current_saga = 1
        elif round_num < total_rounds * 0.75: self.current_saga = 2
        else: self.current_saga = 4

        # Arc tracking
        arc_size = 15
        is_new_arc = (self.arc_round == 0)
        
        if self.arc_round >= arc_size:
            self.current_arc += 1
            self.arc_round = 0
            is_new_arc = True
        self.arc_round += 1

        if round_num % 5 != 0 or not recent_posts:
            return None

        agent_summary = [f"{a.name}: {a.role}, Health: {a.health}%, Goal: {a.current_goal}" for a in self.engine.session.agents]
        post_summary = "\n".join([f"[{p.author_name}]: {p.text[:100]}" for p in recent_posts[-10:]])
        phase = "SCENE (Action/Conflict/Failure)" if (round_num // 5) % 2 == 0 else "SEQUEL (Emotion/Thought/Decision)"

        result_data = {}

        # 1. ARC MODULE (Runs at start of new arcs)
        if is_new_arc:
            arc_data = self._build_arc_module(agent_summary)
            if arc_data and "arc_goal" in arc_data:
                self.layer_data["current_arc_goal"] = arc_data["arc_goal"]

        # 2. SCENE MODULE (Runs every 5 rounds)
        scene_data = self._scene_engine_module(agent_summary, post_summary, phase)
        if scene_data:
            result_data.update(scene_data)

        # 3. EXPANSION MODULE (Runs every 10 rounds to evaluate stakes/mysteries)
        if round_num % 10 == 0:
            exp_data = self._expansion_module(post_summary)
            if exp_data:
                if exp_data.get("progression_unlock") and exp_data["progression_unlock"] != "None":
                    result_data["progression_unlock"] = exp_data["progression_unlock"]
                if exp_data.get("new_mystery") and exp_data["new_mystery"] != "None":
                    self.layer_data["unresolved_mysteries"].append(exp_data["new_mystery"])
                    result_data["new_mystery"] = exp_data["new_mystery"]
                    
        return result_data if result_data else None

class SimulationEngine:
    def __init__(self, session, upload_dir, graph_builder=None):
        self.session = session
        self.upload_dir = upload_dir
        self.graph_builder = graph_builder
        self.director = DirectorAgent(self)
        self.world_db = WorldStorage(os.path.join(upload_dir, "world_gen.db"))
        self.event_queue = queue.Queue()
        self._stop = self._pause = False
        self._injection = None
        self._lock = threading.Lock()
        self.vector_mem = None  # Set by pipeline if available

        sim_dir = os.path.join(upload_dir, "simulations", session.id)
        os.makedirs(sim_dir, exist_ok=True)
        self.sim_dir = sim_dir
        self.action_log_path = os.path.join(sim_dir, "actions.jsonl")

        self.known_entities = [
            e.name
            for e in (
                session.knowledge_graph.entities if session.knowledge_graph else []
            )
        ]
        db_path = os.path.join(sim_dir, "agent_memory.db")
        self.memories = {a.id: AgentMemory(db_path, a.id) for a in session.agents}

        # Parallel execution config
        self.max_concurrent = Config.MAX_CONCURRENT_AGENTS
        # Spotlight cap: max agents that act per round regardless of swarm size
        self.max_active_per_round = Config.MAX_ACTIVE_AGENTS_PER_ROUND

    def emit(self, t, d):
        self.event_queue.put({"type": t, "data": d})

    def log_action(self, p):
        with open(self.action_log_path, "a") as f:
            f.write(json.dumps(p.model_dump(), default=str) + "\n")

    def inject(self, text):
        with self._lock:
            self._injection = text
        p = SimPost(
            author_id="god",
            author_name="Author (God's Eye)",
            platform=Platform.CRITICS_FORUM,
            action=SocialAction.POST,
            text=text,
            round=-1,
            is_injection=True,
        )
        self.session.posts.append(p)
        self.emit("injection", p.model_dump())

    def pause(self):
        self._pause = not self._pause
        return self._pause

    def stop(self):
        self._stop = True

    def _build_semantic_context(self, agent, action, recent_posts: list) -> str:
        """
        Query ChromaDB vector memory for semantically relevant past posts.

        Retrieves posts from earlier in the simulation that are thematically
        relevant to the current topic, enabling long-range coherence beyond the
        last-12-post window.
        """
        if not self.vector_mem:
            return ""
        try:
            # Build a query from the most recent post text + agent role + expertise
            query_parts = [agent.role]
            if recent_posts:
                query_parts.append(recent_posts[-1].text[:200])
            if agent.expertise:
                query_parts.append(" ".join(agent.expertise[:3]))
            query = " ".join(query_parts)[:500]

            results = self.vector_mem.search_posts(
                query=query,
                n_results=4,
                platform=agent.platform.value,
            )
            if not results:
                return ""

            lines = ["SEMANTICALLY RELEVANT EARLIER DISCUSSION:"]
            for r in results:
                meta = r.get("metadata", {})
                author = meta.get("author", "Unknown")
                text = r.get("document", "")[:180]
                rnd = meta.get("round", "?")
                lines.append(f"  [R{rnd} — {author}]: {text}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Semantic context error: {e}")
            return ""

    def _store_post_to_vector_mem(self, post) -> None:
        """Store a completed post into ChromaDB for future semantic retrieval."""
        if not self.vector_mem:
            return
        try:
            self.vector_mem.store_post(
                post_id=post.id,
                author_name=post.author_name,
                action=post.action.value,
                text=post.text[:800],
                round_num=post.round,
                platform=post.platform.value,
            )
            # Also store as agent memory for per-agent semantic recall
            self.vector_mem.store_agent_memory(
                agent_id=post.author_id,
                agent_name=post.author_name,
                round_num=post.round,
                action=post.action.value,
                text=post.text[:800],
                platform=post.platform.value,
                entities_mentioned=post.mentioned_entities or [],
            )
        except Exception as e:
            logger.debug(f"Vector store error: {e}")

    def _build_graph_context(self, agent, recent_posts):
        if not self.graph_builder:
            return agent.graph_context_summary or ""
        parts = []
        try:
            if agent.grounded_entity:
                web = self.graph_builder.query_character_web(
                    self.session.project_id, agent.grounded_entity
                )
                if web:
                    parts.append(web)
            recent_text = " ".join(p.text[:100] for p in recent_posts[-3:])
            kws = [w for w in recent_text.split() if len(w) > 4 and w.isalpha()][:6]
            if kws:
                topic = self.graph_builder.query_by_topic(
                    self.session.project_id, kws, limit=5
                )
                if topic:
                    parts.append("TOPIC-RELEVANT:\n" + topic)
            if agent.faction_membership or agent.role in (
                "Political Strategist",
                "Court Diplomat",
            ):
                fac = self.graph_builder.get_faction_dynamics(self.session.project_id)
                if fac:
                    parts.append("FACTIONS:\n" + fac)
        except Exception as e:
            logger.debug(f"Graph context build error: {e}")
        return "\n\n".join(parts)

    def _build_relationship_context(self, agent):
        rels = self.memories[agent.id].get_relationships()
        if not rels:
            return ""
        lines = ["YOUR RELATIONSHIPS:"]
        for r in sorted(rels, key=lambda x: abs(x["sentiment"]), reverse=True)[:6]:
            other = next(
                (a for a in self.session.agents if a.id == r["other_id"]), None
            )
            if not other:
                continue
            s = r["sentiment"]
            label = (
                "strong ally"
                if s > 0.5
                else "friendly"
                if s > 0.15
                else "neutral"
                if s > -0.15
                else "tense"
                if s > -0.5
                else "antagonistic"
            )
            lines.append(
                f"  {other.name}: {label} ({s:+.2f}) — {r['interaction_count']} interactions"
            )
        return "\n".join(lines)

    def _add_round_reactions(self, round_posts: list, all_agents: list) -> None:
        """Add rule-based emoji reactions from non-posting agents to this round's posts.

        No LLM calls — purely driven by stance, contentiousness, and living memories
        (BOND/GRUDGE toward the post author). Each non-posting agent has a chance to
        react based on their personality and relationship to the author.
        """
        if not round_posts or not all_agents:
            return

        poster_ids = {p.author_id for p in round_posts}
        reactors   = [a for a in all_agents if a.id not in poster_ids]
        if not reactors:
            return

        for post in round_posts:
            if post.visibility != "public":
                continue  # Don't react to faction-only whispers

            n_reactors = random.randint(1, min(4, len(reactors)))
            chosen     = random.sample(reactors, n_reactors)

            for reactor in chosen:
                bond   = any(m.type == MemoryType.BOND  and m.target == post.author_name
                             for m in reactor.living_memories)
                grudge = any(m.type == MemoryType.GRUDGE and m.target == post.author_name
                             for m in reactor.living_memories)

                if grudge or reactor.stance in (Stance.STRONGLY_NEGATIVE, Stance.NEGATIVE):
                    if random.random() > reactor.contentiousness:
                        continue  # Low-contentiousness agents swallow their hostility
                    pool = (REACTION_EMOJIS["challenge"]
                            if random.random() < 0.5 else REACTION_EMOJIS["negative"])
                elif bond or reactor.stance in (Stance.STRONGLY_POSITIVE, Stance.POSITIVE):
                    pool = (REACTION_EMOJIS["agree"]
                            if random.random() < 0.5 else REACTION_EMOJIS["positive"])
                else:
                    if random.random() > 0.3:
                        continue  # Neutral agents mostly scroll past
                    pool = REACTION_EMOJIS["neutral"]

                emoji = random.choice(pool)
                with self._lock:
                    if emoji not in post.reactions:
                        post.reactions[emoji] = []
                    if reactor.name not in post.reactions[emoji]:
                        post.reactions[emoji].append(reactor.name)

            # Emit once per post (if any reactions landed)
            if post.reactions:
                self.emit("reactions_updated", {
                    "post_id":   post.id,
                    "author":    post.author_name,
                    "reactions": post.reactions,
                })

    def _writeback(self, post):
        if not self.graph_builder:
            return
        try:
            mentioned = extract_mentioned_entities(post.text, self.known_entities)
            post.mentioned_entities = mentioned
            for n in mentioned:
                self.graph_builder.increment_mention(self.session.project_id, n)
                self.session.entity_mention_counts[n] = (
                    self.session.entity_mention_counts.get(n, 0) + 1
                )
            if len(self.session.posts) % 5 == 0:
                for e in extract_new_entities_from_post(post.text, self.known_entities):
                    name = e.get("name", "")
                    if name and len(name) > 2:
                        self.graph_builder.add_entity(
                            self.session.project_id,
                            name,
                            e.get("type", "concept"),
                            e.get("description", ""),
                        )
                        self.known_entities.append(name)
                        from app.models.schemas import Entity, EntityType

                        try:
                            etype = EntityType(e.get("type", "concept"))
                        except (ValueError, KeyError):
                            etype = EntityType.CONCEPT
                        self.session.emergent_entities.append(
                            Entity(
                                name=name,
                                type=etype,
                                description=e.get("description", ""),
                            )
                        )
                        self.emit(
                            "entity_emerged",
                            {
                                "name": name,
                                "type": e.get("type"),
                                "description": e.get("description", ""),
                            },
                        )
        except Exception as e:
            logger.warning(f"Writeback error: {e}")

    def _autonomous_replan(self, agent, recent_posts):
        """Hidden autonomous phase where agent re-evaluates their goal using LLM (Mental Model)."""
        # Limit to event_tick mode to save tokens or if health is low
        if not self.session.config.mode == "event_tick" and agent.health > 80:
            return

        # Build a small mental assessment prompt
        posts_list = list(recent_posts) if recent_posts else []
        relevant = [p for p in posts_list if agent.name.lower() in p.text.lower() or p.author_id == agent.id][-5:]
        context = "\n".join([f"[{p.author_name}]: {p.text[:100]}" for p in relevant])
        
        prompt = (
            f"You are {agent.name}. Assess your current situation and update your mental state.\n"
            f"CURRENT STATE: Health {agent.health}%, Goal: {agent.current_goal}, Effects: {agent.status_effects}\n"
            f"RECENT EVENTS:\n{context}\n\n"
            f"Return a JSON object with these fields:\n"
            f"- 'updated_goal': string (a short-term actionable goal)\n"
            f"- 'new_status_effects': list (any new states like 'paranoid', 'hungry', 'determined')\n"
            f"- 'internal_monologue': string (a short private thought about your next move)\n"
        )

        try:
            # Use a faster/cheaper model if possible
            assessment = llm_client.chat_json(prompt, model_override="gpt-4o-mini" if "mini" in Config.LLM_MODEL_NAME else None)
            if assessment:
                agent.current_goal = assessment.get("updated_goal", agent.current_goal)
                agent.status_effects = list(set(agent.status_effects + assessment.get("new_status_effects", [])))
                # We could store monologue in memory
                logger.debug(f"[{agent.name}] Rethink: {assessment.get('internal_monologue')}")
        except Exception as e:
            logger.warning(f"Autonomous replan error for {agent.name}: {e}")

        # Rule-based overrides (safety)
        if agent.health < 30 and "injured" not in agent.status_effects:
            agent.status_effects.append("injured")
            agent.current_goal = "Find healing or safety"

    def _execute_physical_action(self, agent, action, text, target_post):
        """Execute state changes based on InWorldAction or physical SocialAction."""
        try:
            action_val = action.value if hasattr(action, 'value') else str(action)
            
            # Location updates
            if action == InWorldAction.MOVE or action == SocialAction.MOVE:
                # Extract location from text if possible, else random known location
                if "to" in text.lower():
                    # Very simple extraction for demo
                    parts = text.lower().split("to")
                    new_loc = parts[-1].strip().split(".")[0].split(",")[0][:30]
                    agent.location_id = new_loc
            
            # Health / Combat
            if action == InWorldAction.FIGHT or action == SocialAction.ATTACK:
                if target_post:
                    # Find target agent
                    target_agent = next((a for a in self.session.agents if a.id == target_post.author_id), None)
                    if target_agent:
                        dmg = 10 + random.random() * 20
                        target_agent.health -= dmg
                        # Also update graph
                        if self.graph_builder:
                            self.graph_builder.add_relationship(
                                self.session.project_id, agent.name, target_agent.name, "ATTACKED"
                            )

            # Inventory / Items
            if action in (InWorldAction.GIVE_ITEM, InWorldAction.TAKE_ITEM, InWorldAction.STEAL):
                # Simple extraction of "item"
                # For now just add to inventory if they 'find' or 'take'
                if action == InWorldAction.DISCOVER:
                    if "found" in text.lower():
                        item = text.lower().split("found")[-1].strip()[:20]
                        agent.inventory.append(item)

            # Cast Spell / Heal
            if action == InWorldAction.HEAL:
                agent.health = min(100, agent.health + 20)
                if "injured" in agent.status_effects:
                    agent.status_effects.remove("injured")

        except Exception as e:
            logger.warning(f"Action execution error: {e}")

    def _process_agent(self, agent, round_num, injection):
        """Process a single agent — this runs in a thread pool."""
        action = select_action(agent, self.session.posts, round_num, mode=self.session.config.mode)
        target_post = select_target_post(agent, action, self.session.posts)

        self.emit(
            "agent_start",
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "avatar": agent.avatar,
                "role": agent.role,
                "platform": agent.platform.value,
                "action": action.value,
                "round": round_num,
                "living_memories": len(agent.living_memories),
                "emotional_state": agent.emotional_state,
            },
        )

        graph_ctx = self._build_graph_context(agent, self.session.posts[-6:])
        semantic_ctx = self._build_semantic_context(agent, action, self.session.posts[-3:])
        living_text = format_living_memories_for_prompt(agent)
        rel_ctx = self._build_relationship_context(agent)
        agent_mem = self.memories[agent.id].get_recent(8)

        # Merge graph and semantic context
        combined_graph_ctx = "\n\n".join(filter(None, [graph_ctx, semantic_ctx]))

        system, user = build_agent_prompt(
            agent,
            action,
            self.session.config.prediction_requirement or "",
            self.session.posts[-12:],
            self.session.config.mode,
            "",
            agent_mem,
            combined_graph_ctx,
            living_text,
            rel_ctx,
            injection,
            target_post,
        )

        try:
            response = llm_client.chat(
                [{"role": "user", "content": user}],
                system=system,
                temperature=0.7 + agent.creativity * 0.2,
            )
            post = SimPost(
                author_id=agent.id,
                author_name=agent.name,
                platform=agent.platform,
                action=action,
                text=response,
                round=round_num,
                reply_to=target_post.id if target_post else None,
                visibility=agent.faction_membership
                if action == SocialAction.WHISPER
                else "public",
            )
            
            # Independent Thinking: Autonomous Replanning
            self._autonomous_replan(agent, self.session.posts)

            with self._lock:
                self.session.posts.append(post)
                self.log_action(post)

            # Physical Execution: State changes in the world
            self._execute_physical_action(agent, action, response, target_post)

            self._writeback(post)
            self._store_post_to_vector_mem(post)
            self.memories[agent.id].add(
                round_num,
                action.value,
                agent.platform.value,
                response[:500],
                referenced_entities=post.mentioned_entities,
            )

            # Relationship update based on target
            if (
                target_post
                and target_post.author_id != agent.id
                and not target_post.is_injection
            ):
                delta = SENTIMENT_DELTAS.get(action.value, 0)
                self.memories[agent.id].update_relationship(
                    target_post.author_id, delta, action.value
                )

            # Living memory formation
            new_mem = maybe_form_living_memory(
                agent, post, action, self.session.posts, round_num
            )
            if new_mem:
                agent.living_memories.append(new_mem)
                dom = (
                    max(agent.living_memories, key=lambda m: m.intensity)
                    if agent.living_memories
                    else None
                )
                if dom:
                    agent.emotional_state = EMOTION_MAP.get(dom.type, "neutral")
                self.emit(
                    "memory_formed",
                    {
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "memory_type": new_mem.type.value,
                        "intensity": new_mem.intensity,
                        "description": new_mem.description,
                        "target": new_mem.target,
                    },
                )

            # Stance drift
            if random.random() < agent.susceptibility * 0.35:
                idx = STANCE_ORDER.index(agent.stance)
                ni = max(0, min(len(STANCE_ORDER) - 1, idx + random.choice([-1, 1])))
                agent.stance = STANCE_ORDER[ni]
                agent.opinion_history.append(
                    {"round": round_num, "stance": agent.stance.value}
                )

            if action == SocialAction.POST:
                agent.posts_count += 1
            else:
                agent.replies_count += 1

            self.emit(
                "agent_post",
                {
                    "post": post.model_dump(),
                    "agent_update": {
                        "id": agent.id,
                        "stance": agent.stance.value,
                        "posts_count": agent.posts_count,
                        "replies_count": agent.replies_count,
                        "emotional_state": agent.emotional_state,
                        "living_memories_count": len(agent.living_memories),
                    },
                },
            )
            return post

        except Exception as e:
            logger.error(f"Agent {agent.name} error in round {round_num}: {e}")
            self.emit(
                "agent_error",
                {"agent_id": agent.id, "error": str(e), "round": round_num},
            )
            return None

    def _spotlight_select(self, agents: list, round_num: int) -> list:
        """Select the most 'provoked' agents for this round.

        With large swarms (100-5000 agents) we cannot fire an LLM call for every
        agent every round.  Instead we score each agent's urgency and keep only
        the top ``max_active_per_round`` loudest voices — simulating a crowd where
        only the most motivated people speak up at any given moment.

        Scoring factors:
        - reaction_speed          — base willingness to act
        - living memory intensity — grudges, obsessions, trauma increase urgency
        - name mentioned recently — if agents are talking about you, you respond
        - small random jitter     — prevents the same agents dominating every round
        """
        cap = self.max_active_per_round
        # If swarm is small enough, apply the lighter reaction_speed gate instead
        if len(agents) <= cap:
            if round_num == 0:
                return agents
            return [a for a in agents if random.random() < a.reaction_speed]

        # Build a recent-text corpus for mention detection (last 15 posts)
        recent_text = " ".join(p.text.lower() for p in self.session.posts[-15:])

        def _score(agent: "AgentPersona") -> float:
            s = agent.reaction_speed

            # Living memory boosts
            for m in agent.living_memories:
                if m.type in (MemoryType.GRUDGE, MemoryType.OBSESSION):
                    s += m.intensity * 0.5
                elif m.type in (MemoryType.TRAUMA, MemoryType.AMBITION):
                    s += m.intensity * 0.35
                elif m.type in (
                    MemoryType.REVELATION,
                    MemoryType.BOND,
                    MemoryType.ADMIRATION,
                ):
                    s += m.intensity * 0.2
                elif m.type == MemoryType.SCAR:
                    s += m.intensity * 0.15

            # Mention boost — someone talked about this agent recently
            if agent.name.lower() in recent_text:
                s += 0.4

            # Small jitter so the ranking shifts each round
            s += random.random() * 0.15

            return s

        scored = sorted(agents, key=_score, reverse=True)
        selected = scored[:cap]
        logger.debug(
            f"Spotlight R{round_num}: {len(selected)}/{len(agents)} agents active "
            f"(cap={cap}, top={selected[0].name if selected else '-'})"
        )
        return selected

    def save_checkpoint(self, round_num):
        """Save full simulation state for resume capability."""
        checkpoint = {
            "round": round_num,
            "session_id": self.session.id,
            "posts": [p.model_dump() for p in self.session.posts],
            "agents": [a.model_dump() for a in self.session.agents],
            "entity_mentions": self.session.entity_mention_counts,
            "emergent_entities": [
                e.model_dump() for e in self.session.emergent_entities
            ],
            "promotions": [p.model_dump() for p in self.session.character_promotions],
            "known_entities": self.known_entities,
            "state": self.session.state.value,
            "token_usage": llm_client.get_token_usage(),
        }
        cp_path = os.path.join(self.sim_dir, "checkpoint.json")
        with open(cp_path, "w") as f:
            json.dump(checkpoint, f, default=str, indent=2)
        logger.info(f"Checkpoint saved at round {round_num}")

    def run(self):
        self.session.state = SimulationState.RUNNING
        self.emit(
            "sim_start",
            {"rounds": self.session.config.rounds, "agents": len(self.session.agents)},
        )
        config = self.session.config

        for round_num in range(config.rounds):
            if self._stop:
                break

            self.session.current_round = round_num
            self.emit(
                "round_start",
                {
                    "round": round_num,
                    "total": config.rounds,
                    "total_agents": len(self.session.agents),
                },
            )

            # Decay living memories
            for a in self.session.agents:
                decay_living_memories(a)

            # --- MASSIVE SWARM OPTIMIZATION ---
            # In swarms of 1000+, we cannot let them all talk at once.
            # We select the most "reactive/provoked" agents, up to the active cap.
            agents = list(self.session.agents)
            random.shuffle(agents)  # Base shuffle for fairness

            # Boost the selection score of agents who have active intense living memories
            # or high baseline reaction speed.
            def get_reactivity_score(ag):
                base = ag.reaction_speed + random.random() * 0.2
                if ag.living_memories:
                    base += max(m.intensity for m in ag.living_memories)
                return base

            agents_scored = sorted(agents, key=get_reactivity_score, reverse=True)

            # Filter mathematically active ones
            active = [
                a
                for a in agents_scored
                if random.random() < a.reaction_speed or round_num == 0
            ]

            # Hard limit based on Config.MAX_ACTIVE_AGENTS_PER_ROUND
            active_cap = getattr(self.session.config, "MAX_ACTIVE_AGENTS_PER_ROUND", 30)
            active = active[:active_cap]

            logger.info(
                f"Round {round_num}: {len(active)} agents selected to act (out of {len(agents)})"
            )

            self.emit(
                "round_spotlight",
                {
                    "round": round_num,
                    "active_count": len(active),
                    "total_agents": len(agents),
                    "active_names": [a.name for a in active[:10]],  # preview first 10
                },
            )

            # Check for pause/stop
            while self._pause:
                time.sleep(0.3)
                if self._stop:
                    break

            # Get injection if any
            with self._lock:
                injection = self._injection
                self._injection = None

            # --- DIRECTOR TURN ---
            director_event = self.director.assess_narrative(self.session.posts, round_num)
            if director_event:
                self.emit("director_event", director_event)
                # Build powerful context for the next round's actors
                context_parts = [f"[NARRATIVE UPDATE]: {director_event.get('event', '')}"]
                if director_event.get("cliffhanger"):
                    context_parts.append(f"[CLIFFHANGER]: {director_event['cliffhanger']}")
                if director_event.get("progression_unlock"):
                    context_parts.append(f"[PROGRESSION]: {director_event['progression_unlock']}")
                
                if not injection:
                    injection = "\n".join(context_parts)

            # PARALLEL agent processing using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                futures = {}
                for agent in active:
                    if self._stop:
                        break
                    future = executor.submit(
                        self._process_agent, agent, round_num, injection
                    )
                    futures[future] = agent
                    injection = None  # Only first agent gets the injection

                for future in as_completed(futures):
                    try:
                        future.result()  # Raises any exception from the thread
                    except Exception as e:
                        agent = futures[future]
                        logger.error(f"Thread error for agent {agent.name}: {e}")

            # Reactions pass — non-posting agents react to this round's posts
            round_posts = [p for p in self.session.posts
                           if p.round == round_num and not p.is_injection]
            self._add_round_reactions(round_posts, agents)

            # Character emergence check
            promos = check_character_emergence(self.session, self.graph_builder)
            for p in promos:
                self.session.character_promotions.append(p)
                self.emit(
                    "character_promoted",
                    {
                        "entity": p.entity_name,
                        "from": p.previous_role,
                        "to": p.new_role,
                        "mentions": p.mention_count,
                        "weight": p.narrative_weight,
                        "round": round_num,
                    },
                )

            self.emit("round_end", {"round": round_num})

            # Save checkpoint every 5 rounds
            if (round_num + 1) % 5 == 0:
                self.save_checkpoint(round_num)

            # Save run state
            with open(os.path.join(self.sim_dir, "run_state.json"), "w") as f:
                json.dump(
                    {
                        "round": round_num,
                        "posts": len(self.session.posts),
                        "state": self.session.state.value,
                        "emergent": len(self.session.emergent_entities),
                        "promotions": len(self.session.character_promotions),
                        "token_usage": llm_client.get_token_usage(),
                    },
                    f,
                )

        self.session.state = SimulationState.COMPLETED
        self.save_checkpoint(self.session.current_round)
        # --- CHRONICLE GENERATION ---
        try:
            summary_prompt = "Write the 'Chronicle of the Age' for this simulation in a mythic style."
            chronicle = llm_client.generate(summary_prompt, model="gemini-2.0-flash")
            self.emit("chronicle_ready", {"content": chronicle})
        except: pass

        self.emit(
            "sim_end",
            {
                "total_posts": len(self.session.posts),
                "emergent_entities": [e.name for e in self.session.emergent_entities],
                "character_promotions": [
                    {"name": p.entity_name, "role": p.new_role}
                    for p in self.session.character_promotions
                ],
                "token_usage": llm_client.get_token_usage(),
            },
        )
