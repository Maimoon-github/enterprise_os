"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Must run before anything imports app.enterprise (see app/core/edition.py).
from .core import edition as _edition

_edition.apply()

# Before any agno agent runs (see app/core/agno_telemetry.py).
from .core import agno_telemetry as _agno_telemetry  # noqa: E402

_agno_telemetry.apply()

from .main import app  # noqa: E402
