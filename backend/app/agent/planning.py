"""
Planning system for agents to sequence actions toward goals.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from enum import Enum
import time
import uuid


class PlanStatus(Enum):
    """Plan execution status."""
    PENDING = "pending"      # Created but not started
    ACTIVE = "active"        # Currently executing
    PAUSED = "paused"        # Temporarily halted
    COMPLETED = "completed"  # All steps done
    FAILED = "failed"        # Could not complete
    ABANDONED = "abandoned"  # Intentionally dropped


class ActionStatus(Enum):
    """Individual action status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Action:
    """
    A single step in a plan.
    
    Actions have preconditions and postconditions that
    enable chain planning.
    """
    id: str = field(default_factory=lambda: f"action_{uuid.uuid4().hex[:6]}")
    description: str = ""
    action_type: str = ""  # e.g., "post", "reply", "agree", "challenge"
    
    # Execution
    status: ActionStatus = ActionStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    
    # Context
    target_agent: Optional[str] = None
    target_topic: Optional[str] = None
    required_resources: list[str] = field(default_factory=list)
    
    # Preconditions (what must be true to execute)
    preconditions: list[str] = field(default_factory=list)
    
    # Postconditions (what will be true after execution)
    postconditions: list[str] = field(default_factory=list)
    
    # Estimated difficulty/time
    estimated_difficulty: float = 0.5  # 0-1
    
    def can_execute(self, context: dict[str, Any]) -> bool:
        """Check if preconditions are met."""
        for pre in self.preconditions:
            if pre not in str(context):
                return False
        return True
    
    def mark_started(self) -> None:
        """Mark action as started."""
        self.status = ActionStatus.IN_PROGRESS
        self.started_at = time.time()
    
    def mark_completed(self, result: str) -> None:
        """Mark action as completed."""
        self.status = ActionStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result
    
    def mark_failed(self, reason: str) -> None:
        """Mark action as failed."""
        self.status = ActionStatus.FAILED
        self.result = reason


@dataclass
class Plan:
    """
    A sequence of actions to achieve a goal.
    
    Plans can be linear or have conditional branches.
    They adapt to execution context.
    """
    id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    goal_id: str = ""
    description: str = ""
    
    # Actions in order
    actions: list[Action] = field(default_factory=list)
    current_step: int = 0
    
    # Status
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Adaptation
    revision_count: int = 0  # How many times plan was modified
    max_revisions: int = 3
    
    def get_current_action(self) -> Optional[Action]:
        """Get the current action to execute."""
        if self.current_step < len(self.actions):
            return self.actions[self.current_step]
        return None
    
    def advance(self) -> Optional[Action]:
        """Move to next action, return it."""
        self.current_step += 1
        if self.current_step < len(self.actions):
            return self.actions[self.current_step]
        
        # Plan complete
        self.status = PlanStatus.COMPLETED
        self.completed_at = time.time()
        return None
    
    def is_complete(self) -> bool:
        """Check if all actions are done."""
        return all(a.status == ActionStatus.COMPLETED for a in self.actions)
    
    def get_progress(self) -> float:
        """Get completion percentage."""
        if not self.actions:
            return 0.0
        
        completed = sum(1 for a in self.actions if a.status == ActionStatus.COMPLETED)
        return completed / len(self.actions)
    
    def insert_action(self, action: Action, at_index: Optional[int] = None) -> None:
        """Insert an action into the plan."""
        if at_index is None:
            at_index = self.current_step + 1
        
        self.actions.insert(at_index, action)
        self.revision_count += 1
    
    def replan_from(self, step_index: int, new_actions: list[Action]) -> bool:
        """
        Replace remaining plan from a step.
        
        Returns True if replanning succeeded.
        """
        if self.revision_count >= self.max_revisions:
            return False
        
        # Keep completed actions, replace the rest
        self.actions = self.actions[:step_index] + new_actions
        self.revision_count += 1
        
        if self.current_step >= len(self.actions):
            self.current_step = len(self.actions) - 1
        
        return True


class Planner:
    """
    Planning system for agents.
    
    Creates plans to achieve goals using available actions.
    Can do:
    - Linear planning (simple step-by-step)
    - Conditional planning (if-then branches)
    - Replanning when things go wrong
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        
        # Library of action templates
        self.action_templates: dict[str, Callable] = {}
        
        # Plans being executed
        self.active_plans: dict[str, Plan] = {}
        
        # Plan history for learning
        self.plan_history: list[Plan] = []
    
    def register_action_template(self, action_type: str,
                                  template_fn: Callable) -> None:
        """Register a template function for creating actions."""
        self.action_templates[action_type] = template_fn
    
    def create_simple_plan(self, goal_id: str, goal_description: str,
                          action_sequence: list[tuple[str, dict]]) -> Plan:
        """
        Create a simple linear plan.
        
        action_sequence: list of (action_type, params)
        """
        actions = []
        
        for action_type, params in action_sequence:
            action = Action(
                action_type=action_type,
                description=params.get("description", f"{action_type} action"),
                target_agent=params.get("target_agent"),
                target_topic=params.get("target_topic"),
                preconditions=params.get("preconditions", []),
                postconditions=params.get("postconditions", []),
            )
            actions.append(action)
        
        plan = Plan(
            goal_id=goal_id,
            description=goal_description,
            actions=actions,
        )
        
        self.active_plans[plan.id] = plan
        return plan
    
    def plan_for_discussion_goal(self, goal_id: str, goal_desc: str,
                                target_topic: str,
                                desired_outcome: str) -> Plan:
        """
        Create a plan for a discussion-based goal.
        
        Example: "Convince others that X is true"
        """
        actions = [
            Action(
                action_type="post",
                description=f"Introduce viewpoint on {target_topic}",
                target_topic=target_topic,
                postconditions=["viewpoint_introduced"],
            ),
            Action(
                action_type="observe",
                description="Observe reactions from others",
                target_topic=target_topic,
                preconditions=["viewpoint_introduced"],
                postconditions=["reactions_observed"],
            ),
            Action(
                action_type="reply",
                description=f"Respond to counter-arguments on {target_topic}",
                target_topic=target_topic,
                preconditions=["reactions_observed", "counter_argument_present"],
                postconditions=["counter_arguments_addressed"],
            ),
            Action(
                action_type="expand",
                description=f"Strengthen argument with evidence for {desired_outcome}",
                target_topic=target_topic,
                preconditions=["counter_arguments_addressed"],
                postconditions=["argument_strengthened", desired_outcome],
            ),
        ]
        
        plan = Plan(
            goal_id=goal_id,
            description=goal_desc,
            actions=actions,
        )
        
        self.active_plans[plan.id] = plan
        return plan
    
    def plan_for_social_goal(self, goal_id: str, goal_desc: str,
                            target_agent: str,
                            relationship_target: str) -> Plan:
        """
        Create a plan for a social/relationship goal.
        
        Example: "Improve relationship with Agent X"
        """
        actions = [
            Action(
                action_type="agree",
                description=f"Find common ground with {target_agent}",
                target_agent=target_agent,
                postconditions=["common_ground_found"],
            ),
            Action(
                action_type="reply",
                description=f"Engage positively with {target_agent}'s ideas",
                target_agent=target_agent,
                preconditions=["common_ground_found"],
                postconditions=["positive_engagement"],
            ),
            Action(
                action_type="expand",
                description=f"Build on shared interests with {target_agent}",
                target_agent=target_agent,
                preconditions=["positive_engagement"],
                postconditions=["relationship_improved", relationship_target],
            ),
        ]
        
        plan = Plan(
            goal_id=goal_id,
            description=goal_desc,
            actions=actions,
        )
        
        self.active_plans[plan.id] = plan
        return plan
    
    def replan_on_failure(self, plan_id: str, failed_step: int,
                         failure_reason: str) -> Optional[Plan]:
        """
        Attempt to replan when an action fails.
        
        Returns new plan if replanning successful, None otherwise.
        """
        if plan_id not in self.active_plans:
            return None
        
        plan = self.active_plans[plan_id]
        
        # Try alternative approach
        alternatives = self._generate_alternatives(plan, failed_step, failure_reason)
        
        if alternatives and plan.replan_from(failed_step, alternatives):
            return plan
        
        # Can't replan
        plan.status = PlanStatus.FAILED
        return None
    
    def _generate_alternatives(self, plan: Plan, failed_step: int,
                               reason: str) -> list[Action]:
        """Generate alternative actions for a failed step."""
        alternatives = []
        
        # Get the failed action
        failed_action = plan.actions[failed_step] if failed_step < len(plan.actions) else None
        
        if failed_action:
            # Simple alternatives based on action type
            if failed_action.action_type == "post":
                # Try replying instead of posting
                alternatives.append(Action(
                    action_type="reply",
                    description=f"Alternative: reply to existing post instead",
                    target_topic=failed_action.target_topic,
                ))
            
            elif failed_action.action_type == "challenge":
                # Try disagree instead of challenge
                alternatives.append(Action(
                    action_type="disagree",
                    description=f"Alternative: express disagreement more mildly",
                    target_topic=failed_action.target_topic,
                ))
            
            # Always have a "wait and observe" fallback
            alternatives.append(Action(
                action_type="observe",
                description="Alternative: wait and observe before acting",
            ))
        
        return alternatives
    
    def get_active_plan(self, goal_id: str) -> Optional[Plan]:
        """Get the active plan for a goal."""
        for plan in self.active_plans.values():
            if plan.goal_id == goal_id and plan.status in [PlanStatus.PENDING, PlanStatus.ACTIVE]:
                return plan
        return None
    
    def execute_next_step(self, plan_id: str, context: dict[str, Any]) -> dict:
        """
        Execute the next step of a plan.
        
        Returns result dict with status and any new actions.
        """
        if plan_id not in self.active_plans:
            return {"status": "error", "message": "Plan not found"}
        
        plan = self.active_plans[plan_id]
        action = plan.get_current_action()
        
        if not action:
            # Plan is complete
            plan.status = PlanStatus.COMPLETED
            return {"status": "completed", "plan_id": plan_id}
        
        # Check if we can execute
        if not action.can_execute(context):
            action.status = ActionStatus.BLOCKED
            return {
                "status": "blocked",
                "action_id": action.id,
                "reason": "preconditions not met",
            }
        
        # Mark as started
        action.mark_started()
        plan.status = PlanStatus.ACTIVE
        if plan.started_at is None:
            plan.started_at = time.time()
        
        return {
            "status": "executing",
            "action_id": action.id,
            "action_type": action.action_type,
            "description": action.description,
        }
    
    def complete_step(self, plan_id: str, action_id: str,
                     result: str, success: bool) -> dict:
        """Mark a step as completed and advance the plan."""
        if plan_id not in self.active_plans:
            return {"status": "error", "message": "Plan not found"}
        
        plan = self.active_plans[plan_id]
        
        # Find and complete the action
        for action in plan.actions:
            if action.id == action_id:
                if success:
                    action.mark_completed(result)
                else:
                    action.mark_failed(result)
                    
                    # Try to replan
                    failed_idx = plan.actions.index(action)
                    new_plan = self.replan_on_failure(plan_id, failed_idx, result)
                    
                    if new_plan:
                        return {
                            "status": "replanned",
                            "message": "Plan adapted to failure",
                            "new_action": new_plan.get_current_action(),
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": "Could not recover from failure",
                        }
                break
        
        # Advance to next step
        next_action = plan.advance()
        
        return {
            "status": "advanced",
            "completed": plan.is_complete(),
            "next_action": next_action,
            "progress": plan.get_progress(),
        }
    
    def get_plan_summary(self, plan_id: str) -> str:
        """Generate human-readable plan summary."""
        if plan_id not in self.active_plans:
            return "Plan not found"
        
        plan = self.active_plans[plan_id]
        
        lines = [f"PLAN: {plan.description}", f"Status: {plan.status.value}"]
        lines.append(f"Progress: {plan.get_progress()*100:.0f}%")
        lines.append("\nActions:")
        
        for i, action in enumerate(plan.actions):
            status_marker = "[ ]"
            if i < plan.current_step:
                status_marker = "[✓]"
            elif i == plan.current_step:
                status_marker = "[>]"
            
            lines.append(f"  {status_marker} {action.action_type}: {action.description}")
        
        return "\n".join(lines)
