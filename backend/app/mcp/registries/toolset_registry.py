class ToolsetRegistry:
    def __init__(self):
        self._toolsets = {}

    def register_toolset(self, name: str, tools: list[dict]):
        self._toolsets[name] = tools

    def get_toolset(self, name: str) -> list[dict]:
        return self._toolsets.get(name, [])

toolset_registry = ToolsetRegistry()
