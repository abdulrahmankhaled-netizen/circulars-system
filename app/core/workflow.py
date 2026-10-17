"""
🔥 محرك سير العمل (Workflow Engine)
يدير كل الانتقالات بين الحالات بشكل موحّد + يسجّلها.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime

from app.core.constants import (
    REQUEST_STATES, REQUEST_TRANSITIONS,
    CONTRACT_STATES, CONTRACT_TRANSITIONS,
    MISSION_STATES, MISSION_TRANSITIONS,
)


# ============================================================
#  Data Classes
# ============================================================
@dataclass
class State:
    name: str
    label_ar: str
    color: str = "secondary"
    is_final: bool = False


@dataclass
class Transition:
    action: str
    label_ar: str
    from_states: List[str]
    to_state: str
    roles: List[str] = field(default_factory=list)
    requires_comment: bool = False
    notify_roles: List[str] = field(default_factory=list)
    condition: Optional[Callable] = None


@dataclass
class WorkflowDefinition:
    name: str
    initial: str
    states: List[State]
    transitions: List[Transition]

    def state_map(self) -> Dict[str, State]:
        return {s.name: s for s in self.states}

    def find_transition(self, from_state: str, action: str) -> Optional[Transition]:
        for t in self.transitions:
            if t.action == action and from_state in t.from_states:
                return t
        return None

    def available_transitions(self, from_state: str) -> List[Transition]:
        return [t for t in self.transitions if from_state in t.from_states]


# ============================================================
#  Workflow Registry
# ============================================================
def _states_from(raw):
    return [State(name=n, label_ar=lbl, color=c, is_final=fin)
            for n, lbl, c, fin in raw]


def _transitions_from(raw):
    return [Transition(
        action=t["action"],
        label_ar=t["label_ar"],
        from_states=t["from_states"],
        to_state=t["to_state"],
        roles=t.get("roles", []),
        requires_comment=t.get("requires_comment", False),
        notify_roles=t.get("notify_roles", []),
        condition=t.get("condition"),
    ) for t in raw]


WORKFLOWS: Dict[str, WorkflowDefinition] = {
    "equipment_request": WorkflowDefinition(
        name="equipment_request",
        initial="draft",
        states=_states_from(REQUEST_STATES),
        transitions=_transitions_from(REQUEST_TRANSITIONS),
    ),
    "contract": WorkflowDefinition(
        name="contract",
        initial="draft",
        states=_states_from(CONTRACT_STATES),
        transitions=_transitions_from(CONTRACT_TRANSITIONS),
    ),
    "mission": WorkflowDefinition(
        name="mission",
        initial="draft",
        states=_states_from(MISSION_STATES),
        transitions=_transitions_from(MISSION_TRANSITIONS),
    ),
}


def get_workflow(name: str) -> WorkflowDefinition:
    if name not in WORKFLOWS:
        raise ValueError(f"Workflow '{name}' غير معرّف")
    return WORKFLOWS[name]


def get_state_meta(workflow_name: str, state_name: str) -> Dict[str, str]:
    wf = WORKFLOWS.get(workflow_name)
    if not wf:
        return {"label_ar": state_name, "color": "secondary"}
    st = wf.state_map().get(state_name)
    if not st:
        return {"label_ar": state_name, "color": "secondary"}
    return {"label_ar": st.label_ar, "color": st.color, "is_final": st.is_final}


# ============================================================
#  WorkflowEngine
# ============================================================
class WorkflowError(Exception):
    """يُرفع عند فشل عملية في سير العمل."""


class WorkflowEngine:
    """
    ينفّذ انتقالات سير العمل ويُسجّلها.
    
    الاستخدام:
        engine = WorkflowEngine("equipment_request")
        ok, msg = engine.execute(request_obj, "approve", user=current_user)
    """

    def __init__(self, workflow_name: str):
        self.workflow = get_workflow(workflow_name)
        self.name = workflow_name

    # ---------- Checks ----------
    def can(self, entity, action: str, user=None) -> tuple:
        """يعيد (يمكن؟, سبب الفشل)."""
        from flask_login import current_user as _cu
        user = user or _cu

        if not user or not user.is_authenticated:
            return False, "يجب تسجيل الدخول"

        current_state = getattr(entity, "status", None)
        if not current_state:
            return False, "الكائن ليس له حالة (status)"

        t = self.workflow.find_transition(current_state, action)
        if not t:
            return False, f"لا يمكن تنفيذ '{action}' من الحالة الحالية"

        if not self._has_role(user, t.roles):
            return False, "ليست لديك صلاحية لهذا الإجراء"

        if t.condition and callable(t.condition):
            try:
                if not t.condition(entity, user):
                    return False, "الشروط اللازمة للانتقال غير متوفرة"
            except Exception as e:
                return False, f"فشل التحقق من الشروط: {e}"

        return True, ""

    @staticmethod
    def _has_role(user, roles: List[str]) -> bool:
        if not roles:
            return True
        if getattr(user, "is_admin", False):
            return True
        role_name = getattr(getattr(user, "role", None), "name", None)
        return role_name in roles

    # ---------- Execute ----------
    def execute(
        self,
        entity,
        action: str,
        user=None,
        comment: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """ينفّذ الانتقال + يسجّله. يعيد (نجح؟, رسالة الخطأ)."""
        ok, msg = self.can(entity, action, user)
        if not ok:
            return False, msg

        t = self.workflow.find_transition(entity.status, action)
        if t.requires_comment and not comment.strip():
            return False, "هذا الإجراء يتطلب تعليقاً/سبباً"

        old_state = entity.status
        new_state = t.to_state

        entity.status = new_state
        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.utcnow()

        # خطاف اختياري
        if hasattr(entity, "on_workflow_transition"):
            try:
                entity.on_workflow_transition(
                    from_state=old_state, to_state=new_state,
                    action=action, user=user, extra=extra or {},
                )
            except Exception as e:
                print(f"⚠ on_workflow_transition failed: {e}")

        # تسجيل
        self._log(entity, old_state, new_state, action, user, comment, extra)

        # إشعارات
        self._queue_notifications(entity, t, user, old_state, new_state)

        return True, ""

    # ---------- Logging ----------
    def _log(self, entity, from_state, to_state, action, user, comment, extra):
        try:
            from app.extensions import db
            from app.modules.workflow.models import WorkflowLog
            log = WorkflowLog(
                entity_type=self.name,
                entity_id=getattr(entity, "id", None),
                from_state=from_state,
                to_state=to_state,
                action=action,
                performed_by_id=getattr(user, "id", None) if user else None,
                comment=comment or None,
                extra_data=str(extra) if extra else None,
            )
            db.session.add(log)
        except Exception as e:
            print(f"⚠ WorkflowLog failed: {e}")

    # ---------- Notifications ----------
    def _queue_notifications(self, entity, transition, user, from_state, to_state):
        if not transition.notify_roles:
            return
        try:
            from app.extensions import db
            from app.modules.workflow.models import NotificationQueue
            n = NotificationQueue(
                entity_type=self.name,
                entity_id=getattr(entity, "id", None),
                title=f"تغيير حالة: {transition.label_ar}",
                message=f"تم تنفيذ '{transition.label_ar}' بواسطة "
                        f"{getattr(user, 'full_name', 'النظام') if user else 'النظام'}",
                target_roles=",".join(transition.notify_roles),
                from_state=from_state,
                to_state=to_state,
                status="pending",
            )
            db.session.add(n)
        except Exception as e:
            print(f"⚠ NotificationQueue failed: {e}")


# ============================================================
#  Helpers
# ============================================================
def available_actions(workflow_name: str, state: str, user=None) -> List[Transition]:
    """يعيد كل الانتقالات الممكنة للمستخدم من الحالة الحالية."""
    from flask_login import current_user as _cu
    user = user or _cu
    wf = get_workflow(workflow_name)
    engine = WorkflowEngine(workflow_name)
    return [
        t for t in wf.available_transitions(state)
        if engine._has_role(user, t.roles)
    ]