#!/usr/bin/env python3
"""Fetch, verify and unpack the upstream archives NOTICE §2.5.1 names.

**What this script is for.** `NOTICE` §2.5.1 records, for every binary §2.5
carries under an LGPL-2.1 term, a delivery entry: the file a release must
carry, where it was fetched from, its byte count and its sha256. The truth arms
of `tests/test_release_workflow.py` — the ones that compare those recorded
hashes against the upstream bytes — need three directories on disk:
`LABCAIRN_LGPL_SOURCE_DIR` (the archives themselves), `LABCAIRN_LGPL_EXTRACT_DIR`
(the unpacked trees the `--audit-extracts` closure audit re-counts), and
`LABCAIRN_REPLACEABILITY_DIR` (the modified plug-ins and observation files,
which are third-party binary derivatives built on this development machine and
are deliberately never committed here).

This script produces the first two on any machine with network access: it
downloads each archive from the URL §2.5.1 records, verifies its sha256
against the hash recorded there — an archive that does not match is reported
and nothing is unpacked from it — and unpacks the trees the audit reads. The
hashes it checks against are read out of NOTICE by
`scripts/lgpl_source_release.py`'s own reader, so a change to the record
changes what this script demands; this file carries no second copy of the
values.

**What it refuses to do.** It never writes inside the repository: the archives
and their extracts are third-party material that belongs outside the checkout
(the development machine keeps them under `E:/labcairn-local/`), and a cache
directory a workflow points at with `LABCAIRN_LGPL_SOURCE_DIR` must be a
directory of its own. It also never downloads a browser, touches
`PLAYWRIGHT_BROWSERS_PATH`, or does anything beyond fetch-verify-unpack: the
truth arms need exactly these bytes and nothing else.

**Extraction tooling.** Two of the three archives are 7-Zip containers, which
neither Python's standard library (`tarfile`, `zipfile`, `lzma`) nor any
already-installed dependency of this project opens. The script uses a `7z`
executable found on PATH (7-Zip on Windows, `p7zip`/`7zz` on Linux) and refuses
to run without one, naming what is missing; a workflow that runs this script
installs that tool first.

**StdUtils' tar inside the zip.** §2.5.1's first entry delivers
`StdUtils.2018-10-27.Sources.tar`, which is not published on its own: it is a
member of the release archive `StdUtils.2018-10-27.zip` (at
`Contrib/StdUtils/StdUtils.2018-10-27.Sources.tar`). The script verifies the
zip against the zip's own recorded hash, then extracts that member and
verifies the extracted tar against the tar's recorded hash — the same
cross-check §5.4's step 5 spells out — and only then does it place the tar in
the source directory the delivery test reads.

**Exit codes.** 0 when every archive matched its recorded hash and every
extract the audit needs is in place; 1 with one line per problem otherwise. A
verification failure is never a warning: the whole point of the runner arm is
that the bytes hashed in CI are the bytes NOTICE records.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lgpl_source_release as reader

#: The archive each delivery entry is fetched from, keyed by the entry's
#: artefact name. Two entries deliver the archive itself (`Nsis7z_19.00.7z`,
#: `7z1900-src.7z`); the StdUtils entry delivers a tar that is a member of the
#: zip named here. The URLs are the ones §2.5.1's `fetched` labels record.
UPSTREAM_ARCHIVES: tuple[dict[str, str], ...] = (
    {
        "artefact": "StdUtils.2018-10-27.Sources.tar",
        "url": (
            "https://github.com/lordmulder/stdutils/releases/download/1.14/StdUtils.2018-10-27.zip"
        ),
        "download": "StdUtils.2018-10-27.zip",
        # §2.5.1's `taken` label records the zip's own bytes and hash.
        "download_bytes": "391785",
        "download_sha256": ("3ffe893dc7477fdb1cac551a86ae017509e1f2d0ebdc7185fd0fbaf20870688c"),
        "member": "Contrib/StdUtils/StdUtils.2018-10-27.Sources.tar",
    },
    {
        "artefact": "Nsis7z_19.00.7z",
        "url": "https://nsis.sourceforge.io/mediawiki/images/6/69/Nsis7z_19.00.7z",
        "download": "Nsis7z_19.00.7z",
        "download_bytes": "",
        "download_sha256": "",
        "member": "",
    },
    {
        "artefact": "7z1900-src.7z",
        "url": "https://7-zip.org/a/7z1900-src.7z",
        "download": "7z1900-src.7z",
        "download_bytes": "",
        "download_sha256": "",
        "member": "",
    },
)

#: The LZMA SDK archive §2.5.1 records because the plug-in's build note names
#: it; the owner's decision of 2026-11-13 names `7z1900-src.7z` as the archive
#: a release carries, but `--audit-extracts` re-counts the SDK archive's Rar
#: files too, so the extract is needed for the audit to run its whole list.
LZMA_ARCHIVE: dict[str, str] = {
    "url": "https://7-zip.org/a/lzma1900.7z",
    "download": "lzma1900.7z",
    "download_bytes": "1082692",
    "download_sha256": ("00f569e624b3d9ed89cf8d40136662c4c5207eaceb92a70b1044c77f84234bad"),
}

#: Where each unpacked tree lands, under the extract root. The names are the
#: ones `tests/test_release_workflow.py`'s `EXTRACT_SUBDIRS` names.
EXTRACT_LAYOUT: dict[str, str] = {
    "Nsis7z_19.00.7z": "nsis7z",
    "7z1900-src.7z": "7z1900",
    "lzma1900.7z": "lzma1900",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _recorded_sha256s(notice_text: str) -> dict[str, tuple[int | None, str | None]]:
    """The recorded byte count and sha256 of each delivery entry, by artefact name."""
    recorded: dict[str, tuple[int | None, str | None]] = {}
    for entry in reader.delivery_entries(notice_text):
        name = entry.artefact_name()
        recorded[name] = (entry.recorded_bytes(), entry.recorded_sha256())
    return recorded


def _seven_zip() -> str:
    """A `7z` executable on PATH, or a refusal naming what is missing."""
    for candidate in ("7z", "7zz", "7za"):
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit(
        "no 7-Zip executable on PATH (looked for 7z, 7zz, 7za). Two of the three "
        "upstream archives are 7-Zip containers, which Python's standard library "
        "cannot open; install p7zip-full (Linux) or 7-Zip (Windows) first."
    )


def _extract(seven_zip: str, archive: Path, destination: Path) -> None:
    """Unpack one archive into its own directory, recreating it first."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    result = subprocess.run(
        [seven_zip, "x", "-y", f"-o{destination}", str(archive)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"{seven_zip} could not unpack {archive}: {(result.stderr or result.stdout)[-400:]}"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: lgpl_upstream_archives.py <source-dir> <extract-dir> <scratch-dir>",
            file=sys.stderr,
        )
        print(
            "  <source-dir>  receives the archives (and the StdUtils tar) — the "
            "directory LABCAIRN_LGPL_SOURCE_DIR names",
            file=sys.stderr,
        )
        print(
            "  <extract-dir> receives the unpacked trees — the directory "
            "LABCAIRN_LGPL_EXTRACT_DIR names",
            file=sys.stderr,
        )
        print(
            "  <scratch-dir> receives the downloads; it may be deleted afterwards",
            file=sys.stderr,
        )
        return 2
    source_dir = Path(argv[0]).resolve()
    extract_dir = Path(argv[1]).resolve()
    scratch_dir = Path(argv[2]).resolve()
    for directory in (source_dir, extract_dir, scratch_dir):
        if reader.REPO_ROOT in directory.parents or directory == reader.REPO_ROOT:
            print(
                f"refusing to write inside the repository: {directory} is under "
                f"{reader.REPO_ROOT}; these are third-party archives and belong "
                "outside the checkout",
                file=sys.stderr,
            )
            return 2
    for directory in (source_dir, extract_dir, scratch_dir):
        directory.mkdir(parents=True, exist_ok=True)

    notice_text = reader.NOTICE_PATH.read_text(encoding="utf-8")
    recorded = _recorded_sha256s(notice_text)
    seven_zip = _seven_zip()

    import urllib.request

    problems: list[str] = []
    for spec in UPSTREAM_ARCHIVES:
        artefact = spec["artefact"]
        download_name = spec["download"]
        downloaded = scratch_dir / download_name
        if not downloaded.is_file():
            print(f"fetching {download_name} from {spec['url']}")
            try:
                with urllib.request.urlopen(spec["url"], timeout=120) as response:
                    downloaded.write_bytes(response.read())
            except OSError as error:
                problems.append(f"{download_name}: the fetch failed: {error}")
                continue
        actual = _sha256(downloaded)
        expected = spec["download_sha256"] or (recorded.get(artefact, (None, None))[1])
        expected_bytes = spec["download_bytes"] or str(
            recorded.get(artefact, (None, None))[0] or ""
        )
        if expected_bytes and downloaded.stat().st_size != int(expected_bytes):
            problems.append(
                f"{download_name}: NOTICE records {expected_bytes} bytes; "
                f"the download is {downloaded.stat().st_size}"
            )
        if not expected:
            problems.append(f"{download_name}: no recorded sha256 to verify against")
        elif actual != expected:
            problems.append(
                f"{download_name}: NOTICE records sha256 {expected}; "
                f"the download is {actual} — it was not unpacked"
            )
            continue
        print(f"verified {download_name}: sha256 {actual[:16]}… matches the record")

        if spec["member"]:
            # The delivered tar rides inside this archive; extract the member
            # and verify it against the tar's own recorded hash before placing it.
            with zipfile.ZipFile(downloaded) as bundle:
                member_data = bundle.read(spec["member"])
            tar_path = source_dir / artefact
            tar_path.write_bytes(member_data)
            member_sha = hashlib.sha256(member_data).hexdigest()
            tar_expected = recorded.get(artefact, (None, None))[1]
            if tar_expected and member_sha != tar_expected:
                problems.append(
                    f"{artefact}: NOTICE records sha256 {tar_expected}; the member "
                    f"{spec['member']} inside {download_name} is {member_sha}"
                )
                continue
            print(f"verified {artefact}: sha256 {member_sha[:16]}… matches the record")
        else:
            # The delivered archive is the download itself; place it where the
            # delivery check reads it.
            shutil.copyfile(downloaded, source_dir / artefact)

        extract_name = EXTRACT_LAYOUT.get(download_name)
        if extract_name:
            _extract(seven_zip, downloaded, extract_dir / extract_name)
            print(f"unpacked {download_name} into {extract_dir / extract_name}")

    # The LZMA SDK archive: not a delivery artefact, but the closure audit
    # re-counts its Rar files, so its extract is part of the arms.
    lzma_downloaded = scratch_dir / LZMA_ARCHIVE["download"]
    if not lzma_downloaded.is_file():
        print(f"fetching {LZMA_ARCHIVE['download']} from {LZMA_ARCHIVE['url']}")
        try:
            with urllib.request.urlopen(LZMA_ARCHIVE["url"], timeout=120) as response:
                lzma_downloaded.write_bytes(response.read())
        except OSError as error:
            problems.append(f"{LZMA_ARCHIVE['download']}: the fetch failed: {error}")
    if lzma_downloaded.is_file():
        actual = _sha256(lzma_downloaded)
        if actual != LZMA_ARCHIVE["download_sha256"]:
            problems.append(
                f"{LZMA_ARCHIVE['download']}: NOTICE records sha256 "
                f"{LZMA_ARCHIVE['download_sha256']}; the download is {actual} — "
                "it was not unpacked"
            )
        else:
            print(f"verified {LZMA_ARCHIVE['download']}: sha256 {actual[:16]}… matches the record")
            _extract(
                seven_zip,
                lzma_downloaded,
                extract_dir / EXTRACT_LAYOUT[LZMA_ARCHIVE["download"]],
            )
            print(
                f"unpacked {LZMA_ARCHIVE['download']} into "
                f"{extract_dir / EXTRACT_LAYOUT[LZMA_ARCHIVE['download']]}"
            )

    # The audit reads the project file, the shipped DLL and the Rar handlers
    # out of the extracts; assert the shapes it needs before declaring success,
    # so a silently wrong unpack is a red here rather than a mystery in CI.
    for name in ("nsis7z", "7z1900", "lzma1900"):
        if not (extract_dir / name).is_dir():
            problems.append(f"the extract directory {extract_dir / name} was not created")
    nsis7z_dll = extract_dir / "nsis7z" / reader.PLUGIN_DLL
    if not nsis7z_dll.is_file():
        problems.append(
            f"the unpacked plug-in archive does not carry {reader.PLUGIN_DLL} "
            "at its root, which is the layout the closure audit reads"
        )

    if problems:
        print("the upstream archives do not match the record:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(
        f"source directory: {source_dir} (LABCAIRN_LGPL_SOURCE_DIR)\n"
        f"extract directory: {extract_dir} (LABCAIRN_LGPL_EXTRACT_DIR)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
