"""State judge plugins.

Public exports:
    Judgment: Stage 7 decision for one resource.
    StateJudge: Stage 7 plugin protocol.
    get_state_judge: Construct a registered plugin by name.
"""

from judge.base import Judgment, StateJudge, get_state_judge

__all__ = ["Judgment", "StateJudge", "get_state_judge"]
