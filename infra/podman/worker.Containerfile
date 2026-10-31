FROM python:3.12-slim-bookworm

# Install security updates and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create isolated non-root user
RUN groupadd -g 10001 sandboxgroup && \
    useradd -u 10001 -g sandboxgroup -s /bin/bash -m sandboxuser

WORKDIR /workspace
RUN chown -R sandboxuser:sandboxgroup /workspace

# Runtime defaults for gVisor runsc / rootless execution
USER sandboxuser
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TMPDIR=/tmp

# Root filesystem is mounted read-only (--read-only); temporary writes go to tmpfs /tmp
CMD ["python3", "-c", "print('Sandbox Ready')"]
