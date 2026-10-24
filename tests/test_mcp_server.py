"""The MCP tools, called in-process through the SDK client, over the small index and records."""
import asyncio

import pytest
from mcp import Client

from parlimen import mcp_server
from parlimen.mcp_server import server, set_searcher, unload_if_idle

from tests.test_records import recs  # noqa: F401
from tests.test_search import build


def run_tool(name: str, args: dict) -> str:
    async def go() -> str:
        async with Client(server) as client:
            result = await client.call_tool(name, args)
        return result.content[0].text

    return asyncio.run(go())


class Recorder:
    def __init__(self):
        self.unloads = 0

    def unload(self):
        self.unloads += 1


@pytest.fixture
def tools(recs, tmp_path):  # noqa: F811
    s = build(tmp_path / "index")
    search = type(s).search
    s.search = lambda q, f=None, **kw: search(s, q, f, mode="hybrid", **kw)
    set_searcher(s, recs)
    return s


def test_five_tools_are_listed():
    async def go():
        async with Client(server) as client:
            return sorted(t.name for t in (await client.list_tools()).tools)

    assert asyncio.run(go()) == ["list_commitments", "read_section", "read_sitting", "search_debates", "search_law"]


def test_search_law_keeps_to_the_law_and_cites_sections(tools):
    out = run_tool("search_law", {"question": "hours of employment", "act": "265"})
    assert out.startswith("[1] Act 265, s. 60A (BI, as at 2023-01-01)")
    assert "Dewan Rakyat" not in out
    assert run_tool("search_law", {"question": "x", "lang": "EN"}).startswith("Error")


def test_search_debates_filters_by_party(tools):
    out = run_tool("search_debates", {"question": "rice subsidy flood", "party": "DAP"})
    assert "DR-2024-05-02-003" in out and "Act 265" not in out
    assert run_tool("search_debates", {"question": "rice", "party": "MCA"}) == "No passages found."


def test_read_section_returns_the_whole_section(tools):
    out = run_tool("read_section", {"act": "265", "section": "60A"})
    assert "EMPLOYMENT ACT 1955 (Act 265), section 60A: Hours of work (BI, as at 2023-01-01)" in out
    assert "forty-five hours" in out and "not legal advice" in out
    assert "Sections: 60A, 60C" in run_tool("read_section", {"act": "265", "section": "99"})
    assert run_tool("read_section", {"act": "1", "section": "1"}) == "No Act 1 in the record."


def test_read_sitting_lists_items_then_reads_one(tools):
    out = run_tool("read_sitting", {"chamber": "DR", "date": "2024-05-02"})
    assert "DR-2024-05-02-001: PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN (2 speeches)" in out
    assert "Summary (AI): A question on the rice subsidy." in out
    one = run_tool("read_sitting", {"chamber": "DR", "date": "2024-05-02", "extract": "DR-2024-05-02-001"})
    assert "Puan Hannah Yeoh [Segambut] (DAP), page 5, 1010:" in one
    assert "Question (AI) by Puan Hannah Yeoh [Segambut]" in one
    assert 'Commitment by Dato’ Sri Mohamad Sabu: "menyalurkan RM50 juta sebelum Disember 2024"' in one
    assert "No DR sitting" in run_tool("read_sitting", {"chamber": "DR", "date": "2019-01-01"})


def test_list_commitments_filters(tools):
    out = run_tool("list_commitments", {"ministry": "Pertanian dan Keterjaminan Makanan"})
    assert out.startswith("1 commitments match") and "Promise (AI): Pay RM50 million of rice subsidy" in out
    assert "by Disember 2024" in out
    assert run_tool("list_commitments", {"year": "2019"}) == "No commitments match."
    assert run_tool("list_commitments", {"topic": "Sabah and Sarawak"}).startswith("1 commitments match")


def test_the_embedder_unloads_once_idle(tools, monkeypatch):
    rec = Recorder()
    tools.embedder = rec
    assert not unload_if_idle(mcp_server._last_used + 1)
    assert unload_if_idle(mcp_server._last_used + mcp_server.IDLE_SECONDS + 1)
    assert not unload_if_idle(mcp_server._last_used + mcp_server.IDLE_SECONDS + 2)
    assert rec.unloads == 1
