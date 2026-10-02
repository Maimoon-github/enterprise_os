"""Host-side specialist handle; all specialist computation lives in the VM."""
from app.integrations.sandbox.s_alloc_core import SAllocCore
from app.schemas.strategy import SandboxMandate, SandboxResult


class AllocationSpecialist:
    def __init__(self, core: SAllocCore):
        self._core = core

    async def execute(self, mandate: SandboxMandate) -> SandboxResult:
        return await self._core.run(mandate)
