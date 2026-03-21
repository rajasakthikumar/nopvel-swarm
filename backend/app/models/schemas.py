"""Data models for NovelSwarm."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Union, List, Dict, Any
from enum import Enum
import uuid
import time


# ═══════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════


class EntityType(str, Enum):
    CHARACTER = "character"
    PLACE = "place"
    FACTION = "faction"
    ARTIFACT = "artifact"
    MAGIC_SYSTEM = "magic_system"
    EVENT = "event"
    CONCEPT = "concept"
    CREATURE = "creature"
    CULTURE = "culture"
    KINGDOM = "kingdom"
    RELIGION = "religion"
    FAUNA = "fauna"


class Platform(str, Enum):
    CRITICS_FORUM = "critics_forum"  # Meta-narrative discussion
    INWORLD_FORUM = "inworld_forum"  # Diegetic roleplay


class SocialAction(str, Enum):
    # Critics Forum Actions
    POST = "post"
    REPLY = "reply"
    AGREE = "agree"
    DISAGREE = "disagree"
    EXPAND = "expand"
    CHALLENGE = "challenge"
    SYNTHESIZE = "synthesize"
    FORESHADOW = "foreshadow"
    CALLBACK = "callback"
    WORLDBUILD = "worldbuild"
    CHARACTERIZE = "characterize"
    CONFLICT = "conflict"
    RESOLVE = "resolve"
    THEME = "theme"
    OUTLINE = "outline"
    WHISPER = "whisper"
    LEAK_SECRET = "leak_secret"

    # InWorld Actions - Character
    MOVE = "move"
    SPEAK = "speak"
    ACT = "act"
    USE_ITEM = "use_item"
    GATHER_INTEL = "gather_intel"
    KISS = "kiss"
    HUG = "hug"
    APPRECIATE = "appreciate"
    PRAISE = "praise"
    CRY = "cry"
    FLEE = "flee"

    # InWorld Actions - Strategist
    INITIATE_CONFLICT = "initiate_conflict"
    FORM_ALLIANCE = "form_alliance"
    SABOTAGE = "sabotage"
    DEPLOY_RESOURCES = "deploy_resources"
    SCHEME = "scheme"
    WAGE_WAR = "wage_war"
    ASSASSINATE = "assassinate"
    NEGOTIATE = "negotiate"

    # InWorld Actions - Historian
    RECORD_LORE = "record_lore"
    UNCOVER_SECRET = "uncover_secret"
    PROPHESY = "prophesy"
    CHRONICLE = "chronicle"
    MOURN_LOSS = "mourn_loss"
    CELEBRATE_TRIUMPH = "celebrate_triumph"

    # InWorld Actions - Critic
    AUDIT_NARRATIVE = "audit_narrative"
    THEMATIC_INTERVENTION = "thematic_intervention"
    STRUCTURAL_SHIFT = "structural_shift"
    PRAISE_DEVELOPMENT = "praise_development"
    CRITICIZE_ACTION = "criticize_action"

    # InWorld Actions - Character Arc Planner
    TRIGGER_TRANSFORMATION = "trigger_transformation"
    CREATE_DILEMMA = "create_dilemma"
    EMOTIONAL_CATALYST = "emotional_catalyst"
    FORCE_BREAKTHROUGH = "force_breakthrough"
    ORCHESTRATE_TRAGEDY = "orchestrate_tragedy"

    # Universal InWorld Actions
    ATTACK = "attack"
    KILL = "kill"
    REACT = "react"
    BETRAY = "betray"

class InWorldAction(str, Enum):
    # Distinct from Social Actions, these are physical world state changes
    MOVE = "move"
    FIGHT = "fight"
    FLEE = "flee"
    USE_ITEM = "use_item"
    GIVE_ITEM = "give_item"
    TAKE_ITEM = "take_item"
    DISCOVER = "discover"
    DESTROY = "destroy"
    CREATE = "create"
    SABOTAGE = "sabotage"
    HEAL = "heal"
    CAST_SPELL = "cast_spell"
    STEAL = "steal"
    HIDE = "hide"
    WAIT = "wait"

class SimulationState(str, Enum):
    IDLE = "idle"
    EXTRACTING = "extracting"
    BUILDING_GRAPH = "building_graph"
    GENERATING_PERSONAS = "generating_personas"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    SYNTHESIZING = "synthesizing"
    ERROR = "error"


class Stance(str, Enum):
    STRONGLY_POSITIVE = "strongly_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    STRONGLY_NEGATIVE = "strongly_negative"


# ═══════════════════════════════════════════
# ENTITY & RELATIONSHIP (Knowledge Graph)
# ═══════════════════════════════════════════


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    type: EntityType
    description: str
    properties: dict = Field(default_factory=dict)


class Relationship(BaseModel):
    source: str
    target: str
    type: str
    description: str = ""
    weight: float = 1.0


class KnowledgeGraph(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


# ═══════════════════════════════════════════
# LIVING MEMORY — scars, interests, obsessions
# These form during simulation and reshape
# how an agent thinks, acts, and speaks.
# ═══════════════════════════════════════════


class MemoryType(str, Enum):
    SCAR = "scar"  # Painful experience → avoidance, defensiveness, or aggression on that topic
    OBSESSION = "obsession"  # Idea the agent keeps returning to unprompted
    INTEREST = "interest"  # Topic that makes agent more engaged, verbose, creative
    GRUDGE = "grudge"  # Negative fixation on a specific other agent
    ADMIRATION = (
        "admiration"  # Positive fixation → agent defers to, agrees with, defends target
    )
    REVELATION = (
        "revelation"  # Paradigm shift → agent's stance/worldview changed permanently
    )
    TRAUMA = "trauma"  # Deep wound → personality trait alteration (bold→cautious, etc.)
    AMBITION = (
        "ambition"  # Goal that biases action selection (toward outline, expand, post)
    )
    BOND = "bond"  # Deep connection → agent seeks out and protects target


class LivingMemory(BaseModel):
    """A persistent emotional/psychological mark that shapes an agent's behavior."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: MemoryType
    source_round: int
    trigger: str  # What caused it
    target: Optional[str] = None  # Agent/entity this is directed at
    intensity: float = 0.5  # 0.0 = fading, 1.0 = consuming
    description: str = ""  # How this manifests in behavior
    behavioral_effect: str = ""  # Concrete prompt instruction (e.g. "You become defensive when X is mentioned")
    decay_rate: float = 0.02  # Intensity drops per round (0 = permanent scar)


# ═══════════════════════════════════════════
# EMERGENT CHARACTER TRACKING
# ═══════════════════════════════════════════

ROLE_LADDER = ["background", "supporting", "secondary", "main", "protagonist"]


class CharacterPromotion(BaseModel):
    """Tracks when swarm consensus elevates a character's narrative importance."""

    entity_name: str
    previous_role: str = "supporting"
    new_role: str = "secondary"
    round_promoted: int = 0
    evidence: list[str] = Field(default_factory=list)
    champion_agents: list[str] = Field(default_factory=list)
    mention_count: int = 0
    narrative_weight: float = 0.0


# ═══════════════════════════════════════════
# AGENT
# ═══════════════════════════════════════════


class CognitiveProfile(BaseModel):
    """How this agent THINKS — not just what they think about."""

    intelligence: int = 100  # IQ equivalent: 70-160 range
    education_level: str = (
        "average"  # "illiterate", "basic", "educated", "scholar", "genius_autodidact"
    )
    worldly_exposure: str = (
        "local"  # "sheltered", "local", "traveled", "cosmopolitan", "otherworldly"
    )
    reasoning_style: str = "balanced"  # "intuitive", "analytical", "emotional", "dogmatic", "creative", "strategic"
    attention_span: str = "normal"  # "scattered", "normal", "focused", "obsessive"
    communication_style: str = "plain"  # "crude", "plain", "eloquent", "flowery", "cryptic", "academic", "street"
    literacy: bool = True
    speaks_in: str = ""  # Dialect/accent description, e.g. "broken common tongue with heavy dwarven accent"
    cognitive_biases: list[str] = Field(
        default_factory=list
    )  # e.g. ["confirmation_bias", "authority_worship", "paranoia"]
    blind_spots: list[str] = Field(
        default_factory=list
    )  # Topics they literally cannot see clearly


class LifeExperience(BaseModel):
    """What this agent has LIVED through — shapes their worldview."""

    formative_event: str = ""  # The thing that made them who they are
    greatest_achievement: str = ""
    deepest_wound: str = ""  # Emotional scar from their past
    social_class_origin: str = (
        "common"  # "destitute", "common", "merchant", "noble", "royal", "outcast"
    )
    current_social_position: str = ""
    has_killed: bool = False
    has_been_betrayed: bool = False
    has_loved_and_lost: bool = False
    years_of_experience: int = 0  # In their domain
    traveled_places: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list)
    mentors: list[str] = Field(default_factory=list)
    enemies_made: list[str] = Field(default_factory=list)


class AgentPersona(BaseModel):
    id: str = Field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str
    avatar: str = "🧙"
    age: int = 30
    race: str = "human"
    gender: str = "unknown"
    role: str  # Their narrative function in the simulation
    platform: Platform = Platform.CRITICS_FORUM

    # Deep characterization
    personality_traits: list[str] = Field(default_factory=list)
    personality_summary: str = (
        ""  # 2-3 sentence vivid description of WHO this person is
    )
    backstory: str = ""
    deep_persona: str = ""  # ~2000 word high-detail persona
    expertise: list[str] = Field(default_factory=list)
    speech_pattern: str = (
        ""  # How they talk: "formal and clipped", "rambling storyteller", etc.
    )
    catchphrase: str = ""  # Something they'd actually say
    quirks: list[str] = Field(
        default_factory=list
    )  # "taps fingers when thinking", "always mentions food"
    
    # Extended profile info
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: list[str] = Field(default_factory=list)

    # Cognitive profile — determines HOW they contribute
    cognitive: CognitiveProfile = Field(default_factory=CognitiveProfile)

    # Life experience — determines WHAT they draw from
    life: LifeExperience = Field(default_factory=LifeExperience)

    # World grounding from Neo4j
    grounded_entity: Optional[str] = None
    known_allies: list[str] = Field(default_factory=list)
    known_enemies: list[str] = Field(default_factory=list)
    known_locations: list[str] = Field(default_factory=list)
    known_artifacts: list[str] = Field(default_factory=list)
    faction_membership: Optional[str] = None
    graph_context_summary: str = ""

    # Stateful Simulation Properties
    location_id: str = "root"
    inventory: list[str] = Field(default_factory=list)
    health: float = 100.0
    current_goal: str = "Survive and prosper"
    faction_objective: str = ""
    status_effects: list[str] = Field(default_factory=list)

    # Behavioral parameters (0.0 - 1.0)
    influence_level: float = 0.5
    reaction_speed: float = 0.5
    susceptibility: float = 0.3
    creativity: float = 0.5
    contentiousness: float = 0.3

    # Living memory — evolves during simulation
    living_memories: list[LivingMemory] = Field(default_factory=list)

    # Dynamic state
    stance: Stance = Stance.NEUTRAL
    posts_count: int = 0
    replies_count: int = 0
    opinion_history: list[dict] = Field(default_factory=list)
    emotional_state: str = "neutral"
    fixation_target: Optional[str] = None


class AgentMemoryEntry(BaseModel):
    round: int
    action: SocialAction
    platform: Platform
    snippet: str
    timestamp: float = Field(default_factory=time.time)
    sentiment: str = "neutral"
    referenced_agents: list[str] = Field(default_factory=list)
    referenced_entities: list[str] = Field(default_factory=list)
    emotional_valence: float = 0.0


# ═══════════════════════════════════════════
# SIMULATION POST
# ═══════════════════════════════════════════


class SimPost(BaseModel):
    id: str = Field(default_factory=lambda: f"post_{uuid.uuid4().hex[:8]}")
    author_id: str
    author_name: str
    platform: Platform
    action: Union[SocialAction, InWorldAction]
    text: str
    round: int
    timestamp: float = Field(default_factory=time.time)
    reply_to: Optional[str] = None
    is_injection: bool = False
    visibility: str = "public"  # "public" or faction name e.g. "The Iron Guard"
    reactions: dict = Field(default_factory=dict)
    mentioned_entities: list[str] = Field(
        default_factory=list
    )  # Extracted after generation


# ═══════════════════════════════════════════
# PROJECT & SESSION
# ═══════════════════════════════════════════


class Project(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    mode: str = "lore"
    lore_text: str = ""
    outline_text: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationConfig(BaseModel):
    project_id: str
    agent_count: int = 12
    rounds: int = 20
    mode: str = "lore"
    prediction_requirement: str = ""
    critics_ratio: float = 0.5


class SimulationSession(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str
    config: SimulationConfig
    state: SimulationState = SimulationState.IDLE
    current_round: int = 0
    agents: list[AgentPersona] = Field(default_factory=list)
    knowledge_graph: Optional[KnowledgeGraph] = None
    posts: list[SimPost] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    error: Optional[str] = None

    # Emergent tracking
    character_promotions: list[CharacterPromotion] = Field(default_factory=list)
    emergent_entities: list[Entity] = Field(default_factory=list)
    entity_mention_counts: dict = Field(default_factory=dict)
