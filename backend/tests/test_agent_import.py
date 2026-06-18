from __future__ import annotations


class _SlugColumn:
    def __eq__(self, other):
        return other


class _AgentModel:
    slug = _SlugColumn()


class _Query:
    def __init__(self, existing: set[str]):
        self.existing = existing
        self.candidate = ""

    def filter(self, expression):
        self.candidate = expression
        return self

    def first(self):
        return object() if self.candidate in self.existing else None


class _Db:
    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()

    def query(self, model):
        return _Query(self.existing)


def test_make_unique_agent_slug_falls_back_when_name_has_no_ascii_slug():
    from app.routers.studio.agents import _make_unique_agent_slug

    slug = _make_unique_agent_slug(_Db(), _AgentModel, "管理员", "12345678-abcd")

    assert slug == "12345678"


def test_make_unique_agent_slug_avoids_collision():
    from app.routers.studio.agents import _make_unique_agent_slug

    slug = _make_unique_agent_slug(_Db({"mcp-admin"}), _AgentModel, "MCP Admin", "12345678-abcd")

    assert slug == "mcp-admin-12345678"
