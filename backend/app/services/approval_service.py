class ApprovalService:
    async def process_decision(self, approval_id: str, approved: bool, notes: str | None = None) -> dict:
        return {"approval_id": approval_id, "approved": approved}
