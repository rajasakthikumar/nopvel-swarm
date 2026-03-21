"""Snowflake Method API — step-by-step LLM suggestions for webnovel writing.

The Snowflake Method (Randy Ingermanson) applied to webnovel structure:
  - 4 Story Arcs (each a major narrative volume)
  - 3 Plot Beats per Arc (Setup, Confrontation, Resolution)
  - 10 Steps per Beat/Arc to build from one-sentence hook → first draft

Steps 1-5  are Arc-level  (define the arc's premise, characters, synopsis)
Steps 6-10 are Beat-level (scene lists, character charts, narrative, prose)
"""
from flask import Blueprint, request, jsonify
from app.services import llm_client

snowflake_bp = Blueprint("snowflake", __name__)

# ---------------------------------------------------------------------------
# Step metadata — instructions shown to the user for each of the 10 steps
# ---------------------------------------------------------------------------

STEP_META = [
    {
        "step": 1,
        "title": "One-Sentence Hook",
        "icon": "🎯",
        "instruction": (
            "Write ONE sentence that captures the emotional core of this arc. "
            "The formula: [Protagonist] must [goal] before [stakes/deadline], "
            "but [central obstacle]. Every word counts — this is your pitch."
        ),
        "arc_note": {
            2: "Arc 2 escalates from Arc 1's foundation. How have the stakes risen? What new desire or wound has the protagonist gained from Arc 1's ending?",
            3: "Arc 3 deepens the crisis. The protagonist should be fundamentally changed. What impossible choice now defines them?",
            4: "Arc 4 is the endgame. Everything built across arcs 1-3 converges. The hook should feel inevitable and final.",
        },
        "placeholder": "e.g. A disgraced prince must forge an alliance with his sworn enemy to reclaim a kingdom that no longer wants him back, before the Void consumes everything he sacrificed to protect.",
    },
    {
        "step": 2,
        "title": "One-Paragraph Summary",
        "icon": "📄",
        "instruction": (
            "Expand your hook into 3–5 sentences, one per story beat:\n"
            "1. Setup: Who is the protagonist and what do they want?\n"
            "2. Inciting incident: What disrupts their world?\n"
            "3. Rising complication: What makes things worse?\n"
            "4. Dark moment / All Is Lost: What almost breaks them?\n"
            "5. Climax & resolution: How does this arc end?"
        ),
        "arc_note": {
            2: "Arc 2's setup should pick up directly from Arc 1's resolution. Show us what changed. New alliances, new enemies, new cost.",
            3: "Arc 3's paragraph should feel like a tightening vice. Each sentence should raise the pressure from the last.",
            4: "Arc 4's paragraph must pay off every promise made in arcs 1-3. The reader should feel this was inevitable.",
        },
        "placeholder": "Sentence 1 (Setup):\nSentence 2 (Inciting incident):\nSentence 3 (Complication):\nSentence 4 (Dark moment):\nSentence 5 (Climax/Resolution):",
    },
    {
        "step": 3,
        "title": "Character Summaries",
        "icon": "🎭",
        "instruction": (
            "For EACH major character appearing in this arc, write one paragraph:\n"
            "• Name & role in the story\n"
            "• Core motivation (what drives them deep down)\n"
            "• Surface goal (what they think they want this arc)\n"
            "• Deeper need (what they actually need to grow)\n"
            "• Central conflict (internal or external)\n"
            "• Epiphany (what realization will change them by arc's end)"
        ),
        "arc_note": {
            2: "Update your Arc 1 characters: how have they changed? Arc 2 may also introduce new characters — describe their role and how they complicate existing relationships.",
            3: "Characters in Arc 3 should be showing cracks. Their Arc 1 flaws should be at maximum pressure now.",
            4: "Final arc characters: describe where each one ends up. Who completes their arc? Who doesn't?",
        },
        "placeholder": "CHARACTER 1:\nName:\nRole:\nMotivation:\nGoal this arc:\nDeeper need:\nConflict:\nEpiphany:\n\nCHARACTER 2:\n...",
    },
    {
        "step": 4,
        "title": "Expanded 4-Paragraph Summary",
        "icon": "📝",
        "instruction": (
            "Take each sentence from Step 2 and expand it into a full paragraph. "
            "You should end up with 4–5 paragraphs:\n"
            "• Para 1: Setup — establish the world, the protagonist, the want\n"
            "• Para 2: Complication — what forces the protagonist into action\n"
            "• Para 3: Rising stakes — escalating consequences and cost\n"
            "• Para 4: Dark moment — what almost destroys them and why\n"
            "• Para 5: Climax + resolution — how the arc ends and what changes"
        ),
        "arc_note": {
            2: "Arc 2's expanded summary should show the consequences of Arc 1's choices. Don't rehash — escalate.",
            3: "By Arc 3's expanded summary, the protagonist's old coping strategies should fail. Force them to change.",
            4: "Arc 4's expanded summary should feel like every subplot converging into a single point of impact.",
        },
        "placeholder": "PARAGRAPH 1 — Setup:\n\nPARAGRAPH 2 — Complication:\n\nPARAGRAPH 3 — Rising Stakes:\n\nPARAGRAPH 4 — Dark Moment:\n\nPARAGRAPH 5 — Climax & Resolution:",
    },
    {
        "step": 5,
        "title": "Full Character Descriptions",
        "icon": "🧬",
        "instruction": (
            "Write a full one-page description per major character. Cover:\n"
            "• Physical description (what makes them visually distinctive)\n"
            "• Backstory that shapes their current wound\n"
            "• What they believe about the world (their lie)\n"
            "• What they fear more than anything\n"
            "• How they start this arc vs. how they end it\n"
            "• Their voice — how they talk, what they never say\n"
            "• Their relationship with the protagonist"
        ),
        "arc_note": {
            2: "Show the Arc 1 → Arc 2 transformation. What scars did Arc 1 leave? What new strengths?",
            3: "Characters in Arc 3 should be tested at their core wound. Show it cracking open.",
            4: "Final character descriptions: include their legacy — what impression do they leave on the world?",
        },
        "placeholder": "CHARACTER 1 — FULL DESCRIPTION:\n\nPhysical:\nBackstory:\nLie they believe:\nFear:\nArc start → Arc end:\nVoice:\nRelationship to protagonist:\n\nCHARACTER 2 — FULL DESCRIPTION:\n...",
    },
    {
        "step": 6,
        "title": "Full Beat Synopsis",
        "icon": "📖",
        "instruction": (
            "Write a 4-page detailed synopsis of THIS BEAT only. "
            "Every significant scene must appear. Focus on cause-and-effect:\n"
            "what happens → what changes in the characters → what new problem emerges.\n"
            "Use present tense. Name every character, location, and decision point. "
            "The reader of this synopsis should be able to describe every chapter."
        ),
        "arc_note": {
            2: "Arc 2 beats should feel more confined and personal than Arc 1. The world is darker. Trust is scarce.",
            3: "Arc 3 beats have a relentless quality. Each beat should end worse than it started — until the very last.",
            4: "Arc 4 beats are about payoff. Each one should close a loop opened in earlier arcs.",
        },
        "placeholder": "Full beat synopsis (write in present tense, be specific about events, characters, and stakes):\n",
    },
    {
        "step": 7,
        "title": "Character Charts",
        "icon": "📊",
        "instruction": (
            "Build a reference chart for every character active in this beat. "
            "For each character, define:\n"
            "• Physical: age, appearance, identifying marks\n"
            "• Goal this beat: what do they want right now?\n"
            "• Fear: what are they afraid will happen?\n"
            "• Lie: what false belief guides their decisions?\n"
            "• Truth: what do they need to learn to grow?\n"
            "• Relationship to protagonist: ally / rival / mirror / obstacle / mentor"
        ),
        "arc_note": {
            2: "Update charts from Arc 1 — what changed? New relationships, new wounds, new goals.",
            3: "Arc 3 charts should show characters at their most extreme version of their flaw.",
            4: "Final charts: note how each character's lie is resolved — do they accept the truth or reject it?",
        },
        "placeholder": "NAME | AGE | GOAL (this beat) | FEAR | LIE | TRUTH | ROLE\n---\n",
    },
    {
        "step": 8,
        "title": "Scene List",
        "icon": "🎬",
        "instruction": (
            "List every scene needed in this beat, in order. For each scene:\n"
            "• Chapter # and scene #\n"
            "• POV character\n"
            "• Location (specific — not 'a forest', but 'the Ashwood border, dusk')\n"
            "• Scene goal: what does the POV character want?\n"
            "• Scene conflict: what blocks them?\n"
            "• Scene outcome: do they succeed, fail, or get a complication?\n"
            "• Story change: how is the story different after this scene?"
        ),
        "arc_note": {
            2: "Arc 2 scenes should feel more claustrophobic. Fewer safe spaces, tighter knots.",
            3: "Every Arc 3 scene should have a ticking clock. Urgency must be felt.",
            4: "Arc 4 scenes are mirrors of Arc 1 scenes — same locations, different character. Show growth.",
        },
        "placeholder": "Ch.1 Sc.1 | POV: ... | Location: ... | Goal: ... | Conflict: ... | Outcome: ... | Change: ...\nCh.1 Sc.2 | ...",
    },
    {
        "step": 9,
        "title": "Scene Narratives",
        "icon": "✍️",
        "instruction": (
            "Take your scene list and expand each entry into 1–3 sentences of "
            "narrative description. Write it as if telling the story to a collaborator — "
            "enough detail that someone else could write the scene from your description. "
            "Include: the emotional texture, the key line of dialogue if any, and what "
            "the reader should feel when the scene ends."
        ),
        "arc_note": {
            2: "Arc 2 scene narratives should have a different emotional tone than Arc 1 — darker, more guarded.",
            3: "Arc 3 scene narratives — lean into the dread. Let the reader feel what's coming.",
            4: "Arc 4 scene narratives should carry weight. The reader has been with these characters for 3 arcs.",
        },
        "placeholder": "Scene 1: [Expanded narrative...]\n\nScene 2: [Expanded narrative...]\n\nScene 3: ...",
    },
    {
        "step": 10,
        "title": "First Draft",
        "icon": "🖊️",
        "instruction": (
            "Write the actual prose for this beat. Use your scene narratives as scaffolding. "
            "RULES:\n"
            "• Don't edit while you write — keep moving forward\n"
            "• Every scene must open with a sensory anchor (sight, sound, smell, touch)\n"
            "• Give each character a distinct voice — the reader should know who's speaking without tags\n"
            "• Let subtext do the work — don't state emotions, embody them\n"
            "• Aim for 3,000–10,000 words depending on beat length\n"
            "• End each chapter on a micro-hook"
        ),
        "arc_note": {
            2: "Arc 2 prose should feel different from Arc 1 — the protagonist's voice has changed. Show it.",
            3: "Arc 3 prose: shorter sentences, faster pace. The world is closing in.",
            4: "Arc 4 prose: write with intention. Every sentence matters. This is what the reader came for.",
        },
        "placeholder": "Begin your first draft here...\n\nChapter 1\n\n",
    },
]


def _build_context(arc: int, beat: int, step: int, all_inputs: dict) -> str:
    """Assemble all the user's previous inputs into a coherent LLM context string."""
    lines = []

    # Arc 1 foundation — always include if we're on arc 2+
    if arc > 1:
        arc1_content = []
        for s in range(1, 6):
            val = all_inputs.get(f"arc1_step{s}", "").strip()
            if val:
                arc1_content.append(
                    f"Arc 1 Step {s} — {STEP_META[s-1]['title']}:\n{val}"
                )
        if arc1_content:
            lines.append("=== ARC 1 FOUNDATION ===")
            lines.extend(arc1_content)
            lines.append("")

    # Previous arc's final summary for context
    if arc > 2:
        prev_arc_synopsis = all_inputs.get(f"arc{arc-1}_step4", "").strip()
        if prev_arc_synopsis:
            lines.append(f"=== ARC {arc-1} SUMMARY (Step 4) ===")
            lines.append(prev_arc_synopsis)
            lines.append("")

    # Current arc's completed steps (arc-level steps 1-5)
    current_arc_content = []
    for s in range(1, min(step, 6)):
        val = all_inputs.get(f"arc{arc}_step{s}", "").strip()
        if val:
            current_arc_content.append(
                f"Arc {arc} Step {s} — {STEP_META[s-1]['title']}:\n{val}"
            )
    if current_arc_content:
        lines.append(f"=== CURRENT ARC {arc} — STEPS 1-5 ===")
        lines.extend(current_arc_content)
        lines.append("")

    # Beat-level completed steps (6-10) for the current beat
    if step > 6:
        beat_content = []
        for s in range(6, step):
            val = all_inputs.get(f"arc{arc}_beat{beat}_step{s}", "").strip()
            if val:
                beat_content.append(
                    f"Arc {arc} Beat {beat} Step {s} — {STEP_META[s-1]['title']}:\n{val}"
                )
        if beat_content:
            beat_names = ["Setup & Inciting Incident", "Rising Action & Confrontation", "Climax & Resolution"]
            bname = beat_names[beat - 1] if 1 <= beat <= 3 else f"Beat {beat}"
            lines.append(f"=== CURRENT ARC {arc} BEAT {beat} ({bname}) — COMPLETED STEPS ===")
            lines.extend(beat_content)
            lines.append("")

    return "\n".join(lines)


@snowflake_bp.route("/suggest", methods=["POST"])
def suggest():
    """Generate an LLM suggestion for the current Snowflake step."""
    data = request.json or {}
    arc = max(1, min(4, int(data.get("arc", 1))))
    beat = max(1, min(3, int(data.get("beat", 1))))
    step = max(1, min(10, int(data.get("step", 1))))
    all_inputs = data.get("all_inputs", {})

    meta = STEP_META[step - 1]
    context = _build_context(arc, beat, step, all_inputs)

    beat_names = ["Setup & Inciting Incident", "Rising Action & Confrontation", "Climax & Resolution"]
    beat_name = beat_names[beat - 1] if 1 <= beat <= 3 else f"Beat {beat}"
    arc_names = ["Opening Arc", "Rising Arc", "Escalation Arc", "Climax Arc"]
    arc_name = arc_names[arc - 1]

    arc_note = meta.get("arc_note", {}).get(arc, "")
    arc_note_block = f"\nARCNOTE FOR ARC {arc}: {arc_note}\n" if arc_note else ""

    user_prompt = f"""{context}
=== YOUR TASK ===
Generate a suggestion for:
  Arc {arc} ({arc_name}) — Beat {beat} ({beat_name}) — Step {step}: {meta['title']}

WHAT THIS STEP REQUIRES:
{meta['instruction']}
{arc_note_block}
Write the suggestion directly — no preamble, no "Here is my suggestion".
Output only the content itself, ready to paste into the field."""

    try:
        suggestion = llm_client.chat(
            [{"role": "user", "content": user_prompt}],
            system=(
                "You are a master webnovel author and story architect. "
                f"You are helping the author develop Arc {arc} of their webnovel "
                "using the Snowflake Method. Your suggestions must be specific, "
                "vivid, and directly usable — never generic. "
                "Build naturally on everything the author has already written."
            ),
            max_tokens=1500,
        )
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snowflake_bp.route("/node-suggest", methods=["POST"])
def node_suggest():
    """Generate an LLM suggestion for a single plot-graph node.

    Receives the node label, its branch, the current content (if any),
    and the full ancestor chain from root → parent so the suggestion
    builds naturally on everything written above it.
    """
    data = request.json or {}
    label = data.get("label", "Untitled plot point")
    branch = data.get("branch", "main")
    current_content = data.get("current_content", "").strip()
    ancestor_chain = data.get("ancestor_chain", [])   # [{label, content}]
    siblings = data.get("siblings", [])               # [{label, content}] same-branch neighbours

    # Build ancestor context
    ctx_lines = []
    if ancestor_chain:
        ctx_lines.append("STORY SO FAR (ancestor chain, root → parent):")
        for i, anc in enumerate(ancestor_chain):
            ctx_lines.append(f"  [{i+1}] {anc.get('label', '?')}")
            if anc.get("content", "").strip():
                ctx_lines.append(f"      {anc['content'][:300]}")
        ctx_lines.append("")

    if siblings:
        ctx_lines.append("NEIGHBOURING NODES ON THIS BRANCH:")
        for s in siblings[:4]:
            ctx_lines.append(f"  • {s.get('label', '?')}: {s.get('content', '')[:150]}")
        ctx_lines.append("")

    context = "\n".join(ctx_lines)

    edit_note = ""
    if current_content:
        edit_note = f"\nThe author has already written:\n{current_content}\n\nExpand or improve on this."

    user_prompt = f"""{context}
CURRENT NODE (branch: "{branch}"): "{label}"
{edit_note}

Write the plot-point content for this node. Be specific:
- What happens here? (events, decisions, conflicts)
- How does this node change the story?
- What is the emotional beat the reader should feel?
- What does the protagonist do, learn, or lose?

Write 2-4 sentences of tight, specific narrative description — ready to use directly."""

    try:
        suggestion = llm_client.chat(
            [{"role": "user", "content": user_prompt}],
            system=(
                "You are a master story architect and webnovel author. "
                f"You are writing plot point content for the '{branch}' branch of a story. "
                "Generate specific, vivid, immediately usable content that flows naturally "
                "from everything that came before it."
            ),
            max_tokens=600,
        )
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snowflake_bp.route("/steps", methods=["GET"])
def get_steps():
    """Return the metadata for all 10 Snowflake steps (for frontend reference)."""
    return jsonify(
        [
            {k: v for k, v in meta.items() if k != "arc_note"}
            for meta in STEP_META
        ]
    )


# ---------------------------------------------------------------------------
# Recursive expansion — the core of the loop
# ---------------------------------------------------------------------------

LEVEL_NAMES = ["Novel", "Arc", "Beat", "Chapter", "Scene", "Moment"]

# Which step triggers the expansion prompt at each level
# Level 0-2: expand after step 4 (Expanded Summary)
# Level 3+:  expand after step 9 (Scene Narratives) or step 8 (Scene List)
EXPAND_TRIGGER_STEP = {0: 4, 1: 4, 2: 4, 3: 9, 4: 9, 5: 9}

# Suggested number of children per level
EXPAND_CHILD_COUNT = {0: 4, 1: 3, 2: 5, 3: 8, 4: 6, 5: 4}


@snowflake_bp.route("/expand", methods=["POST"])
def expand():
    """Extract child-level seeds from the current node's completed step content.

    The recursive loop:
      Level 0 (Novel)   → Step 4 paragraphs  → Level 1 (Arcs)
      Level 1 (Arc)     → Step 4 paragraphs  → Level 2 (Beats)
      Level 2 (Beat)    → Step 4 paragraphs  → Level 3 (Chapters)
      Level 3 (Chapter) → Step 9 scenes      → Level 4 (Scenes)
      Level 4+ (Scene)  → Step 9 narratives  → Level 5 (Moments)

    Returns a list of {title, hook} objects — each becomes the Step 1 content
    for a new child node, pre-seeded and ready for the user to expand further.
    """
    data = request.json or {}
    current_level = max(0, int(data.get("level", 0)))
    node_label = data.get("node_label", "")
    step_content = data.get("step_content", "")   # content of the trigger step
    ancestors = data.get("ancestors", [])          # [{label, step1, step4}] parent chain
    child_count_hint = data.get("child_count", None)

    if not step_content.strip():
        return jsonify({"error": "No content to expand from"}), 400

    next_level = current_level + 1
    next_level_name = LEVEL_NAMES[min(next_level, len(LEVEL_NAMES) - 1)]
    child_level_name = next_level_name
    child_count = child_count_hint or EXPAND_CHILD_COUNT.get(current_level, 4)
    trigger_step = EXPAND_TRIGGER_STEP.get(current_level, 4)
    trigger_step_name = STEP_META[trigger_step - 1]["title"]

    # Build ancestor context
    ancestor_ctx = ""
    if ancestors:
        ancestor_ctx = "STORY LINEAGE (parent levels, for context):\n"
        for i, anc in enumerate(ancestors):
            ancestor_ctx += f"  Level {i} ({LEVEL_NAMES[i]}) — {anc.get('label', '')}:\n"
            if anc.get("step1"):
                ancestor_ctx += f"    Hook: {anc['step1']}\n"
            if anc.get("step4"):
                ancestor_ctx += f"    Summary: {str(anc['step4'])[:300]}\n"
        ancestor_ctx += "\n"

    user_prompt = f"""{ancestor_ctx}
CURRENT LEVEL {current_level} — {LEVEL_NAMES[current_level]}: "{node_label}"

This is the content of Step {trigger_step} ({trigger_step_name}) for this node:
---
{step_content[:3000]}
---

TASK: Extract exactly {child_count} distinct {child_level_name}s from this content.
Each {child_level_name} should be a self-contained story unit that can be expanded further.

For each {child_level_name}, provide:
- title: a short, evocative name (3-8 words)
- hook: a single sentence capturing the core conflict/premise — vivid, specific, immediately usable as a Snowflake Step 1 input

IMPORTANT:
- The {child_level_name}s should cover the FULL scope of the content above — don't skip any major elements
- Each hook must be specific to this story, not generic advice
- Order them chronologically as they would appear in the story

Return ONLY valid JSON:
{{
  "children": [
    {{"title": "Short evocative title", "hook": "One-sentence hook for this {child_level_name}..."}},
    ...
  ]
}}"""

    try:
        result = llm_client.chat_json(
            [{"role": "user", "content": user_prompt}],
            system=(
                f"You are a master story architect. Extract {child_count} distinct "
                f"{child_level_name}s from the provided story content. "
                "Each must have a specific, compelling one-sentence hook that fully "
                "captures its narrative essence — ready to use as a Snowflake Step 1 input."
            ),
            max_tokens=2000,
        )

        children = []
        if isinstance(result, dict) and "children" in result:
            children = result["children"]
        elif isinstance(result, list):
            children = result

        # Normalise to {title, hook}
        normalised = []
        for c in children:
            if isinstance(c, dict):
                normalised.append({
                    "title": c.get("title", f"{child_level_name} {len(normalised)+1}"),
                    "hook": c.get("hook", c.get("one_sentence_hook", "")),
                })

        return jsonify({
            "children": normalised,
            "next_level": next_level,
            "next_level_name": next_level_name,
            "child_count": len(normalised),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
