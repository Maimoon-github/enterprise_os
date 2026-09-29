# Build from the Enterprise OS root, not this directory.
# Set a vetted Python base pinned as registry/image@sha256:<digest>.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/contracts
WORKDIR /opt
RUN python -m pip install --no-cache-dir pydantic==2.13.5
COPY backend/app/__init__.py /opt/contracts/app/__init__.py
COPY backend/app/schemas/__init__.py /opt/contracts/app/schemas/__init__.py
COPY backend/app/schemas/strategy.py /opt/contracts/app/schemas/strategy.py
COPY sandbox/docker/hardened/skills/s-alloc/scripts/run.py /opt/skills/s-alloc/scripts/run.py
USER 65532:65532
ENTRYPOINT ["python", "-B", "/opt/skills/s-alloc/scripts/run.py"]
