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


@snowflake_bp.route("/steps", methods=["GET"])
def get_steps():
    """Return the metadata for all 10 Snowflake steps (for frontend reference)."""
    return jsonify(
        [
            {k: v for k, v in meta.items() if k != "arc_note"}
            for meta in STEP_META
        ]
    )
