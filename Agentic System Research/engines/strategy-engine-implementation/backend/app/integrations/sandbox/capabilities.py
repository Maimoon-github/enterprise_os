"""S_ALLOC registration. Merge this entry into the existing registry."""
from typing import Literal
from app.schemas.strategy import SandboxPolicy

S_ALLOC_WORKER: Literal['W_STRAT'] = 'W_STRAT'
S_ALLOC_CAPABILITY: Literal['S_ALLOC'] = 'S_ALLOC'
S_ALLOC_ENTRYPOINT = '/opt/skills/s-alloc/scripts/run.py'


def s_alloc_policy(timeout_seconds: int) -> SandboxPolicy:
    return SandboxPolicy(timeout_seconds=timeout_seconds)
