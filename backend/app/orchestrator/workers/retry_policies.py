class RetryPolicy:
    """Side-effect retry policies: retries=3 for idempotent read/RAG operations,

    and retries=1 for mutating platform publish calls.
    """

    READ_TOOLS_MAX_RETRIES: int = 3
    MUTATING_PUBLISH_MAX_RETRIES: int = 1
    RETRY_BACKOFF_FACTOR: float = 2.0

    MUTATING_TOOL_NAMES: set[str] = {
        "publish_to_platform",
        "execute_platform_publish",
        "dispatch_platform_post",
        "submit_image_generation_job",
        "submit_video_render_job",
    }

    @classmethod
    def get_max_retries(cls, tool_name: str) -> int:
        """Return maximum allowable retries for a given tool name."""
        if tool_name in cls.MUTATING_TOOL_NAMES or "publish" in tool_name.lower():
            return cls.MUTATING_PUBLISH_MAX_RETRIES
        return cls.READ_TOOLS_MAX_RETRIES


READ_TOOLS_MAX_RETRIES: int = RetryPolicy.READ_TOOLS_MAX_RETRIES
MUTATING_PUBLISH_MAX_RETRIES: int = RetryPolicy.MUTATING_PUBLISH_MAX_RETRIES


def get_tool_retry_policy(tool_name: str) -> int:
    return RetryPolicy.get_max_retries(tool_name)

