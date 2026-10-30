class RetryPolicy:
    # 3 retries for read/RAG operations; 1 retry for mutating platform publish calls
    READ_TOOLS_MAX_RETRIES = 3
    MUTATING_PUBLISH_MAX_RETRIES = 1
    RETRY_BACKOFF_FACTOR = 2.0
