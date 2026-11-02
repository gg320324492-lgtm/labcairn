"""LC-P2-18's dry run: how far paper-qa goes offline, per corpus fixture.

**What this script is, and what it refuses to be.** It drives the eleven
corpus fixtures through paper-qa's real ingestion and retrieval paths and
stops at the first place a provider would be called. The stop is a stub
that raises ``STUB-PROVIDER-BOUNDARY``: no model API is contacted, no
credential is read, and nothing is spent. What the run produces is a
record of *where each fixture stopped and why*, which is what the
preparation phase can honestly measure before the owner approves a real
run.

**It runs in the isolated paper-qa environment, not the repository's.**
See ``docs/acceptance/LC-P2-18-preparation.md`` for the environment and
the pinned clone. The repository's own tests never import this script, so
CI does not need paper-qa installed.

The output is JSON on stdout or at ``--output``. It is a measurement
artifact: the record in ``docs/acceptance/`` is the summary, and re-running
this script reproduces it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "COHERE_API_KEY"):
    os.environ.pop(variable, None)

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tests"))
sys.path.insert(0, str(REPOSITORY / "tests" / "evaluation"))

from analysis_fixtures import load_expected  # noqa: E402
from evaluation.corpus import CORPUS_FIXTURES  # noqa: E402
from evaluation.paperqa_adapter import question_for, render_fixture  # noqa: E402

STUB_MARKER = "STUB-PROVIDER-BOUNDARY"


def _stub_model_class() -> type:
    """A LiteLLMModel subclass whose every completion raises the marker.

    It records what it was asked so the record can say the retrieval
    produced the fixture's own text, not something else.
    """
    from lmi import LiteLLMModel
    from paperqa.settings import make_default_litellm_model_list_settings
    from pydantic import PrivateAttr

    class StubModel(LiteLLMModel):
        _calls: list[str] = PrivateAttr(default_factory=list)

        def __init__(self) -> None:
            super().__init__(
                name="lc-p2-18-stub",
                config=make_default_litellm_model_list_settings("lc-p2-18-stub", 0.0),
            )

        async def acompletion(self, messages: Any, **kwargs: Any) -> Any:
            rendered = json.dumps(messages, default=str)
            self._calls.append(rendered)
            raise NotImplementedError(f"{STUB_MARKER} (call {len(self._calls)})")

        @property
        def calls(self) -> list[str]:
            return self._calls

    return StubModel


async def _run_fixture(fixture: str) -> dict[str, Any]:
    from paperqa import Docs, Settings
    from paperqa.llms import SparseEmbeddingModel
    from paperqa.readers import parse_text
    from paperqa.types import Doc, Text

    record: dict[str, Any] = {"fixture": fixture, "steps": {}}

    try:
        rendered = render_fixture(fixture)
        record["steps"]["render"] = {"ok": True, "characters": len(rendered)}
    except Exception as error:
        record["steps"]["render"] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        record["stage_reached"] = "render"
        return record

    with tempfile.TemporaryDirectory(prefix="lc-p2-18-dry-") as scratch:
        path = Path(scratch) / f"{fixture}.txt"
        path.write_text(rendered, encoding="utf-8")
        try:
            parsed = parse_text(path)
            record["steps"]["parse"] = {
                "ok": True,
                "characters": len(parsed.content),
            }
        except Exception as error:
            record["steps"]["parse"] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            record["stage_reached"] = "parse"
            return record

    settings = Settings()
    settings.embedding = "sparse"
    embedding = SparseEmbeddingModel()
    docs = Docs()
    doc = Doc(docname=fixture, dockey=fixture, citation=f"corpus fixture {fixture}")
    text = Text(text=rendered, name=fixture, doc=doc)

    try:
        added = await docs.aadd_texts([text], doc, settings=settings, embedding_model=embedding)
        record["steps"]["ingest"] = {"ok": bool(added), "docs": len(docs.docs)}
        if not added:
            record["stage_reached"] = "ingest"
            return record
    except Exception as error:
        record["steps"]["ingest"] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        record["stage_reached"] = "ingest"
        return record

    question = question_for(load_expected(fixture))
    try:
        retrieved = await docs.retrieve_texts(
            question, k=3, settings=settings, embedding_model=embedding
        )
        record["steps"]["retrieve"] = {
            "ok": True,
            "texts": len(retrieved),
            "first_text_starts_with": retrieved[0].text[:60] if retrieved else None,
        }
        if not retrieved:
            record["stage_reached"] = "retrieve"
            return record
    except Exception as error:
        record["steps"]["retrieve"] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        record["stage_reached"] = "retrieve"
        return record

    stub_model_class = _stub_model_class()
    stub = stub_model_class()
    try:
        session = await docs.aquery(
            question,
            settings=settings,
            llm_model=stub,
            summary_llm_model=stub,
            embedding_model=embedding,
        )
        record["steps"]["answer"] = {"ok": True, "answer": session.answer}
        record["stage_reached"] = "answer"
    except NotImplementedError as error:
        first = stub.calls[0] if stub.calls else ""
        record["steps"]["answer"] = {
            "ok": False,
            "stopped_at": "provider boundary",
            "marker": str(error),
            "stub_calls": len(stub.calls),
            "prompt_carries_fixture_text": rendered.splitlines()[0] in first,
        }
        record["stage_reached"] = "answer-boundary"
    except Exception as error:
        record["steps"]["answer"] = {"ok": False, "error": f"{type(error).__name__}: {error}"}
        record["stage_reached"] = "answer"
    return record


async def _main(output: Path | None) -> int:
    import paperqa
    from paperqa.version import __version__ as paperqa_version

    records = [await _run_fixture(fixture) for fixture in CORPUS_FIXTURES]
    document = {
        "paperqa_version": paperqa_version,
        "paperqa_module": str(Path(paperqa.__file__).resolve()),
        "provider_calls": 0,
        "fixtures": records,
    }
    text = json.dumps(document, indent=2)
    if output is None:
        print(text)
    else:
        output.write_text(text, encoding="utf-8")
        print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(_main(arguments.output)))
