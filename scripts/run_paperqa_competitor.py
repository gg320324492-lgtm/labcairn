"""LC-P2-18's paper-qa side runner: plan offline, run only on approval.

**Dry mode** reads a task package, validates it, and prints the call plan
— what a live run would call, for which cases, at least how many times.
Zero network, zero credentials, zero spend.

**Live mode** actually drives the pinned paper-qa against a provider. It
is gated: without the owner's approval file (``--approval``) it refuses
before paper-qa is even imported, because a real run spends money and
that is the owner's call (brief §6). The approval file declares the
budget string, the approving owner, and the model both sides must declare
identically; it lives outside the repository, with the credentials.

**This script runs in the isolated paper-qa environment** —
``E:/labcairn-local/paperqa-venv-19b47f/venv`` — not the repository's;
see ``docs/acceptance/LC-P2-18-preparation.md`` for the environment, the
pinned clone, and the license boundary (never install the ``pymupdf`` or
``zotero`` extra). The repository's tests never import this script.

The execution core (call plan, authorization gate, artifact shapes) lives
in ``tests/evaluation/competitor_paperqa_run.py`` and is witnessed there;
this file holds only the seam that needs the competitor installed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tests"))
sys.path.insert(0, str(REPOSITORY / "tests" / "evaluation"))

from evaluation.competitor_package import (  # noqa: E402
    PackageInvalidError,
    package_manifest_sha256,
    validate_package,
)
from evaluation.competitor_paperqa_run import (  # noqa: E402
    DRY_MODE,
    MODES,
    ArtifactLayout,
    LiveRunNotAuthorizedError,
    build_call_plan,
    require_live_authorization,
    run_planned_cases,
    write_surface_declaration,
)

#: The recovered XLSX rendering comes from the adapter, rendering the
#: package's own bytes rather than the tree's copy — the side runs on the
#: package it was handed.
from evaluation.paperqa_adapter import render_fixture  # noqa: E402


def _material_text(case: str, inputs: dict[str, bytes]) -> str:
    """The document text one case's material becomes, and nothing more.

    A CSV is its own bytes decoded; a spreadsheet is rendered cell by cell
    by the adapter (the same rendering the dry run witnessed byte-for-byte
    against its source CSV). The no-evidence material's two files join in
    name order. The question text is not material: the question is asked,
    not ingested. Nothing is added — the competitor sees the task files,
    not an adapter-authored document about them.
    """
    if case.endswith((".xlsx", ".csv")):
        data = inputs[case]
        if case.endswith(".xlsx"):
            return render_fixture(case, spreadsheets={case: data})
        return data.decode("utf-8")
    parts = [
        inputs[name].decode("utf-8")
        for name in sorted(inputs)
        if not name.endswith(".question.txt")
    ]
    return "\n\n".join(parts)


async def _live_answer(model_name: str, question: str, material: str) -> str:
    """Drive the pinned paper-qa to one answer, spending for real.

    The pipeline is the one the preparation's dry run measured to the
    provider boundary: ``parse_text`` into a temporary file (local), the
    sparse embedder over it (local), then one ``aquery`` — the call that
    reaches the provider through the declared model. The model is the
    approval file's declaration, so the run and the basis cannot disagree
    about what was called.

    The declared model reaches litellm under the ``openai/`` prefix — the
    declared model is served behind an OpenAI-compatible endpoint, whose
    address and the credential arrive through ``PAPERQA_LLM_API_BASE`` and
    ``PAPERQA_LLM_API_KEY``, set by the operator's shell from the provider
    layer's own configuration and the secrets directory. Either missing is a
    refusal before paper-qa is even asked a question: an unset endpoint is
    not a default to guess at.
    """
    api_key = os.environ.get("PAPERQA_LLM_API_KEY", "").strip()
    api_base = os.environ.get("PAPERQA_LLM_API_BASE", "").strip()
    if not api_key or not api_base:
        raise RuntimeError(
            "live mode needs PAPERQA_LLM_API_BASE and PAPERQA_LLM_API_KEY in the "
            "environment — the endpoint and credential the operator's provider "
            "configuration names. Nothing was called and nothing was spent."
        )
    from lmi import LiteLLMModel
    from paperqa import Docs, Settings
    from paperqa.llms import SparseEmbeddingModel
    from paperqa.readers import parse_text
    from paperqa.settings import make_default_litellm_model_list_settings
    from paperqa.types import Doc, Text

    litellm_name = f"openai/{model_name}"
    config = make_default_litellm_model_list_settings(litellm_name, 0.0)
    config["model_list"][0]["litellm_params"]["api_key"] = api_key
    config["model_list"][0]["litellm_params"]["api_base"] = api_base
    model = LiteLLMModel(name=litellm_name, config=config)
    settings = Settings()
    settings.embedding = "sparse"
    embedding = SparseEmbeddingModel()
    docs = Docs()
    with tempfile.TemporaryDirectory(prefix="lc-p2-18-live-") as scratch:
        path = Path(scratch) / "material.txt"
        path.write_text(material, encoding="utf-8")
        parsed = parse_text(path)
    doc = Doc(docname="material", dockey="material", citation="LC-P2-18 task material")
    text = Text(text=parsed.content, name="material", doc=doc)
    await docs.aadd_texts([text], doc, settings=settings, embedding_model=embedding)
    session = await docs.aquery(
        question,
        settings=settings,
        llm_model=model,
        summary_llm_model=model,
        embedding_model=embedding,
    )
    return str(session.answer)


def _live_execute(model_name: str):
    """The seam ``run_planned_cases`` executes cases through, for real."""

    def execute_case(case: Any, inputs: dict[str, bytes]) -> str:
        question = inputs["question"].decode("utf-8").strip()
        material = _material_text(case.case, inputs)
        return asyncio.run(_live_answer(model_name, question, material))

    return execute_case


def _write_side_documents(
    artifacts_dir: Path,
    package_dir: Path,
    model: str,
    budget: str,
    label: str,
) -> None:
    """Write the side's run record, basis declaration, and key pins.

    The basis is the side's own honest declaration: it ran the pinned
    pipeline once over the package (integration), and its limitations are
    the ones the machinery actually has — the absent recovery surface, the
    abstention rule's strictness, recall's generosity — not a boilerplate
    sentence.
    """
    layout = ArtifactLayout(root=artifacts_dir)
    manifest_sha = package_manifest_sha256(package_dir)
    key_versions = layout.write_key_versions(package_dir)
    case_names = _case_names(key_versions)
    (artifacts_dir / "run.json").write_text(
        json.dumps(
            {
                "label": label,
                "package_manifest_sha256": manifest_sha,
                "model": model,
                "budget": budget,
                "started_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (artifacts_dir / "basis.json").write_text(
        json.dumps(
            {
                "label": label,
                "fixtures": {"names": case_names, "versions": key_versions},
                "model": model,
                "budget": budget,
                "verified_capabilities": ["integration"],
                "limitations": (
                    "the competitor ran the pinned paper-qa pipeline once over the "
                    "package; its interface is documents-in, answers-out, so it has "
                    "no surface for the recovery face (scored as the brief's scope "
                    "fact); the abstention rule is mechanical and strict (any "
                    "forbidden value in the answer fails the case, even in passing); "
                    "the numeric rule is recall-only and cannot see refusals"
                ),
                "confidence_intervals": "",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _case_names(key_versions: dict[str, str]) -> list[str]:
    """The package's case names in the order the sides declare them.

    The six conditions compare ``fixtures.names`` as a tuple, so both sides
    must spell the same order: each face's cases sorted, the faces in the
    package's own order — numeric extraction, unsupported-claim detection,
    recovery correctness.
    """
    faces = ("numeric-extraction", "unsupported-claim-detection", "recovery-correctness")
    names: list[str] = []
    for face in faces:
        prefix = f"{face}/answer-keys/"
        names += sorted(
            Path(relpath).name.removesuffix(".expected.json").removesuffix(".json")
            for relpath in key_versions
            if relpath.startswith(prefix)
        )
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--package", type=Path, required=True, help="the task package directory")
    parser.add_argument(
        "--artifacts", type=Path, help="where this side's outputs are written (live mode)"
    )
    parser.add_argument(
        "--approval",
        type=Path,
        help="the owner's approval file (live mode; JSON with budget, approved_by, model)",
    )
    parser.add_argument(
        "--output", type=Path, help="where the dry plan is written (default: stdout)"
    )
    arguments = parser.parse_args()

    try:
        validate_package(arguments.package)
    except PackageInvalidError as error:
        print("package invalid; nothing planned or run:", file=sys.stderr)
        for reason in error.reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 2

    plan = build_call_plan(arguments.package)

    if arguments.mode == DRY_MODE:
        document = plan.as_document()
        rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
        if arguments.output is None:
            print(rendered, end="")
        else:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(rendered, encoding="utf-8")
            print(f"call plan written to {arguments.output}")
        print(
            f"plan: {plan.provider_calls_min} provider calls minimum "
            f"over {sum(len(face.cases) for face in plan.faces)} cases; "
            "recovery face declared absent (no calls, brief section 1's scope fact)"
        )
        return 0

    # -- live mode: gated before anything is imported or contacted ----------
    assert arguments.approval is not None, "live mode requires --approval"
    try:
        approval = require_live_authorization(arguments.approval)
    except LiveRunNotAuthorizedError as error:
        print(f"live run refused: {error}", file=sys.stderr)
        return 2
    model = str(approval["model"])
    budget = str(approval["budget"])
    label = str(approval.get("label", "paper-qa competitor"))

    write_surface_declaration(
        arguments.artifacts,
        plan,
        "the competitor's interface is documents-in, answers-out; it has no "
        "executor to inject a crash into (brief §1's scope fact)",
    )
    run_planned_cases(
        plan,
        arguments.package,
        arguments.artifacts,
        execute_case=_live_execute(model),
    )
    _write_side_documents(arguments.artifacts, arguments.package, model, budget, label)
    print(f"live run complete under {arguments.artifacts}; model {model!r}, budget {budget!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
