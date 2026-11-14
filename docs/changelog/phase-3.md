# Changelog archive — Phase 3 — in flight, recorded newest first

Archived verbatim from the root [`CHANGELOG.md`](../../CHANGELOG.md) on
2026-11-11. The body is byte-identical to the sections as they stood there,
except that each relative link gained the depth of `docs/changelog/`.
The root file keeps [`[Unreleased]`](../../CHANGELOG.md#unreleased) as the
container and [the archives index](../../CHANGELOG.md#archives).

### The second blind-rating round closes (2026-11-14)

- **LC-P2-14's rating half ran a second round, both raters agents again.**
  Two fresh agent sessions rated each unseen paper's blind sheet
  independently; a third session arbitrated every disagreement. Agreement
  rose over the first round on both papers — paper 1 **395/420 (0.9405)**,
  paper 2 **451/455 (0.9912)** — and every disagreement in the round fell
  in the `advisor_comprehension` dimension. All 15 contrasts per paper
  (three contrasts × five dimensions) are **NOT SIGNIFICANT**. The record
  states the two rounds' figures and draws no quality conclusion from them;
  no capability claim is made, and Phase 2's closed gate stays closed.
  Evidence lives outside the repository, under
  `E:\labcairn-local\blind-rating-agent-run\`; the record is
  [`LC-P2-14-second-blind-round-2026-11-14.md`](../acceptance/LC-P2-14-second-blind-round-2026-11-14.md).
  No product source, test or workflow file changed.

### The owner's T09/O3 decisions land, and the frozen backend rides in the package (2026-11-14)

- **O3 decided: a frozen service; T09's supply decided: mixed.** The owner
  picked the mixed supply — the package's `resources/shell-env.json` carries
  `workspace` in its installation-relative form, and since the frozen
  backend ships it now carries `cliPath` in its installation-relative form
  too — and the frozen backend: `labcairn.cli:main` frozen with PyInstaller
  into a onedir `labcairn.exe` carried in `extraResources`. The decision
  material is the T09/O3 decision brief (outside the repository); the record
  is
  [`LC-P3-05-input-update-supply-2026-11-14.md`](../acceptance/LC-P3-05-input-update-supply-2026-11-14.md)
  §3.1–§3.3.
- **What landed.** `shell/shell-env.template.json` ships
  `{"cliPath": "backend/labcairn/labcairn.exe", "workspace":
  "LabCairn-workspace"}` — the installation-relative forms, anchored to the
  package's own resources directory (the `_comment` field had already been
  removed; the parser refuses unknown fields). `shell/scripts/build-backend-freeze.mjs`
  is the freeze tool; `electron-builder.yml` carries the whole onedir freeze
  at `resources/backend/labcairn`; `shell/scripts/require-package-inputs.mjs`
  (the guard formerly named `require-web-dist.mjs`) refuses a build whose
  web bundle or frozen backend is absent, hollow, or missing its entry
  binary or migrations; `ServiceSupervisor` sets `PYDANTIC_DISABLE_PLUGINS=1`
  on every child's environment at its one spawn path.
  `shell/scripts/rehearse-packaged-shell-env.mjs` runs eight scenarios
  including the installation-relative supply and a live frozen-service leg.
- **Measured.** Freeze 226,476,027 B in 131.7 s; the installer with the
  backend is 234,325,233 B (sha256 `9805be54…55c4`; the 2026-11-11
  backend-less installer was 124,568,971 B). The packaged-run drill against
  the real unpacked package — the template renamed live, the environment
  naming nothing — passed **connected → loaded → granted** with the
  package's own backend. Two refusals were measured on the way and fixed:
  the frozen exe dying at import without the plugin flag, and the file
  naming the bundle directory instead of the exe (`ENOENT` at spawn). Full
  numbers in the record's §3.2–§3.3. Still open: the NSIS
  install/upgrade/uninstall arms and AC-6's clean-Windows drill (owner's
  human run), and whether the `logfire` extra should leave the dependency
  graph.

### The four delivery pull requests merge (2026-11-14)

- **PRs #161–#164 merged into `main`; `origin/main` stands at
  `6ba6fa82caffd8a9ba78ab9ae9b7ea1b45c1f1e3`.** #161 (`ef30823`) converted the
  live documents' pointers to wording anchors and gave the job-count witness
  its record list; #162 (`6186fff`) brought the pinned browser driver and the
  LGPL truth-arm archives into `python.yml`'s shard jobs, closed §17's
  version-selection gap at the wire and in jsdom (record
  [`LC-P3-01-version-select-2026-11-14.md`](../acceptance/LC-P3-01-version-select-2026-11-14.md)),
  and corrected the records a 2026-11-14 sweep measured as misleading; #163
  (`7ccc5c0`) closed the shell's T08 input policy, T06 update path and T09 two
  supply ways (record
  [`LC-P3-05-input-update-supply-2026-11-14.md`](../acceptance/LC-P3-05-input-update-supply-2026-11-14.md))
  and gave the installer's licence census its three-sided witness; #164
  (`6ba6fa8`) recorded the real-browser witnesses' measured standing and fixed
  the Windows leg's path.
- **What this follow-up sweep measured and did.** The anchor-completeness
  witness passes (463 cases); every live document's declared anchor count
  matches its reader; the three new dated records carry the dated-reading
  note and name no `file:line` pointer; GitHub's required-check set re-read
  2026-11-14 is still the fifteen CI.md records. §17's version-switching and
  environment-supply rows were still saying what the tree had stopped saying,
  so they were corrected to the landed state; `docs/handoff/CURRENT.md`,
  `docs/README.md`'s current-phase row and this archive gained the four merges.
  The repository map gained the `6ba6fa8` file-count reading (870 tracked
  files). No historical dated record was rewritten; no push started a CI run.
- **Still open, unchanged in kind.** The version panel's real-browser
  assertion is written in the version-select record's §5 and awaits the
  `tests/test_workbench_real_browser.py` window; O3's backend arrangement,
  AC-6's clean-Windows drill and the human dual-host reopen rows stay owner
  work; `LC-P3-07`/`LC-P3-08` stay blocked on `LC-P3-05`'s installed build; no
  gate row has moved.

### The push's job count, counted again (2026-11-12)

- **The defect.** `CLAUDE.md` and `CONTRIBUTING.md` both said "the suite is
  five shards per platform, so a push starts ten python jobs". That was the
  count before `lint` was a job of its own: `python.yml` had no `lint` job on
  2026-10-31 (`4f8bb29`), and it has had one since 2026-11-02 (`e5472f8`), so
  a push starts **eleven** python jobs — the ten shard legs and `lint`. The
  project's own count already said so: `.github/CI.md` records "**Eleven,
  counted from the workflow:** ... and `lint` as the eleventh", and the comment
  on `python.yml`'s `lint` job counts the same eleven.
- **Why it stood.** Nothing read those two sentences. The job-count witness
  watches three records — `.github/CI.md`, `python.yml` and
  `docs/plans/LC-P1-13-evaluation-ci.md` — and the two rule files are not
  among them; the instrument also cannot see a count written as "a push starts
  ten python jobs", because that is not one of the shapes it reads. A wrong
  number in a live pointer, unwatched, is the same defect family this phase
  has been closing.
- **The correction.** Both files now count eleven and say why. The handoff's
  2026-10-31 entry keeps its ten, because it was true when it was written, and
  carries a **dated snapshot** marker naming the later reading.


### NOTICE's scope is widened to the four surfaces a distribution carries (2026-11-12)

> **The title first read "three surfaces".** `NOTICE` §0.1 says four, and said
> four in the same commit that widened the scope (`df18d46`); the count in the
> title came from that commit's subject line rather than from `NOTICE`. The
> title is corrected here because a table of contents that names the wrong
> count misleads a reader who never opens the entry, and the bullet it heads
> carries a dated note of its own.

- **The defect.** `NOTICE` §2.4.2 said **"Nothing in either tree is copyleft."**
  For the shell's 268 npm packages the claim holds — an independent re-review
  working from the lockfile, the registry and the published tarballs confirmed
  that no copyleft identifier appears, no package is `UNLICENSED`, none says
  `SEE LICENSE IN`, and none offers a choice in which one option is copyleft.
  What was wrong was the **scope**: a LabCairn installer distributes two more
  surfaces, and the file named neither.
- **The installer binaries.** `NOTICE` §2.5 records eight binaries, each traced
  by sha256 to the electron-builder cache that supplied it. Four come from
  `nsis-3.0.4.1` and are zlib/libpng per that distribution's own `COPYING`:
  `System.dll` 12,288, `nsDialogs.dll` 9,728, `nsExec.dll` 6,656, `elevate.exe`
  107,520. Four come from `nsis-resources-3.4.1`, which carries **no licence
  file**: `StdUtils.dll` 102,400 is **LGPL-2.1-or-later** (LoRd_MuldeR, a
  verbatim copy of the upstream 1.14 Unicode release build, sha256
  `b72e9013…` identical across installer, cache and upstream), `nsis7z.dll`
  434,176 carries 7-Zip's **LGPL-2.1** terms, and `UAC.dll` 14,848 and
  `WinShell.dll` 3,072 have **no findable terms** — the bundle that ships them
  states none.
- **The web tree.** `NOTICE` §2.6 records 266 lock keys, and the three
  denominators that are easy to confuse: 266 keys in `packages:` (and 266 in
  `snapshots:`, 299 in their union), 241 distinct `name@version` installed, 624
  installed `package.json` records. The lock carries **0** licence fields, so
  the terms come from the installed tree (241 keys) or the registry (the other
  25). Over all 266: **12 MPL-2.0** — `lightningcss@1.33.0` and eleven platform
  variants — and **1 CC-BY-4.0**, `caniuse-lite@1.0.30001816`.
- **What is not yet discharged.** §2.5.1 states the LGPL-2.1 obligations and
  where each stands for the 2026-11-11 build: the licence text and notice (§1,
  §6) are **not done** — the artefact contains zero licence text for either
  LGPL binary, and the NSIS archive lists ten members of which none is a
  licence document (the seven plug-in DLLs, `modern-wizard.bmp` and
  `app-64.7z` under `$PLUGINSDIR`, plus the uninstaller at `$R0`); the
  corresponding source (§4, §6(c)) is
  **identified but not pointed at** — upstream's release archive contains
  `StdUtils.2018-10-27.Sources.tar`, 23 files in 11 folders, and no offer
  travels with the installer; §6(b) replaceability has a **recorded route and no
  measured result**. The author's `LGPL_CLARIFICATION.txt` is quoted, including
  the inconsistency inside it (its Limitations paragraph says *General* Public
  License where the rest of the document says *Lesser*).
- **The owner's decision.** Keep the plug-in and discharge the obligations
  rather than remove or replace it; widen the notice's scope; restore React's
  MIT attribution through the web build's `THIRD-PARTY-NOTICES`, which lands at
  `resources/web-dist/THIRD-PARTY-NOTICES`. The installer's per-binary licence
  census and the Chromium component review are deferred and were not attempted.
- **The new machinery.** `.github/web-lockfile-keys.mjs` is the reader §5.4
  names for the web tree; it imports the lockfile grammar from
  `.github/shell-lockfile-keys.mjs` rather than carrying a second copy.
  `shell/test/notice-scope.test.mjs` (8 cases) watches the scope: a table
  narrower than what the sections record, a drifted surface count, a class table
  that no longer adds up to the lock, a binary with no licence line, a flagged
  package adopted as a direct dependency, and a sentence asserting the absence of
  copyleft without naming a surface all redden it. Six mutations were applied to
  the file itself; each reddened the witness and the restore was byte-identical.
  `tests/test_shell_ci.py` records the new file's floor, and the shell's Node
  cases stand at 52 across nine files.

### The declaration batch is delivered, and the licence surface turns out wider than NOTICE said (2026-11-12)

- **PR #157 merged as `720275afbc6eb51ed8fff53271f5217dc930de73`** — nine
  commits: the CI declaration layer's six defects, the owner's two
  branch-protection decisions, and the drain witness's repair below. Twenty
  checks passed and the schedule-only `evaluation` job skipped by design;
  the ledger across the merge reports `LOST -- none` and `ADDED -- 15`.

> **Denominators, re-measured 2026-11-12 and left in the dated entry.** The
> merge carries **ten** commits, not nine: `git rev-list --count
> 720275af^1..720275af^2` → 10, and `gh pr view 157 --json commits` → 10. The
> check runs on the merge commit are **17 `success` and 1 `skipped`
> (`evaluation`)** — 18 reported checks, not twenty
> (`gh api …/commits/720275af…/check-runs`, exit 0). A `gh pr view 157
> --json statusCheckRollup` read gives 21 rows because it also includes the
> pull-request-side entries; that is a third denominator. The countable claim
> is: ten commits landed, seventeen checks passed, one was skipped by design.
> The bullet above is left as written because it is a dated record; this note
> says which of its numbers a reader can reproduce.

- **An independent re-review of NOTICE's own classification.** The 268
  packages' identifiers were taken independently, from the registry and from
  each published tarball: **228 confirmed permissive, 40 need the owner's
  judgement, 0 undeterminable**. The forty are not copyleft, but the basis
  behind them is thinner than a count: **16 carry their licence only as a
  manifest field**, with no licence document in the published tarball; some
  embed third-party terms (`node-gyp`'s vendored `packaging`, `undici`'s
  second `LICENSE`); four are deprecated upstream; `argparse@2.0.1` is the
  PSF licence with its venue clause; and four offer a choice of licences.
  **The entry above says the identifiers were read from "registry metadata and
  each package's own licence file"** — the review measured that for sixteen of
  them the second half does not hold, so their identifier rests on the
  registry field alone. The measurement wins over the record, and the record
  is corrected here; the older entry is left as it was written.

> **The count of packages that offer a choice, re-measured 2026-11-12.** Three
> of the 268 declare an SPDX `OR` expression — `sanitize-filename@1.6.5`
> (`WTFPL OR ISC`), `type-fest@0.13.1` (`MIT OR CC0-1.0`) and
> `utf8-byte-length@1.0.5` (`WTFPL OR MIT`). The fourth package `NOTICE` §2.5
> names in the same sentence, `truncate-utf8-bytes@1.0.2`, declares a plain
> `WTFPL`, so the bullet's "four offer a choice of licences" counts a package
> that declares no choice. Measured from the npm registry's own `license`
> field for all 268 packages — the source the re-review read — three values
> contain ` OR `, and `truncate-utf8-bytes@1.0.2`'s is `WTFPL`. The bullet's
> other counts still hold: four packages are deprecated upstream (`boolean`,
> `glob`, `inflight`, `rimraf`), and the shell lockfile carries four
> `deprecated:` fields. `NOTICE` §2.5's prose still reads "Four packages offer
> a choice", beside a class table that lists three `(… OR …)` rows and one
> `WTFPL` row; `NOTICE` carries the licence record and is not this entry's to
> change.

- **A distribution carries three surfaces, and NOTICE named one.** (a) The
  shell's 268 packages, no copyleft among them, measured. (b) The binaries
  the installer redistributes — seven `$PLUGINSDIR` NSIS plug-in DLLs plus
  `elevate.exe` — of which **`StdUtils.dll` is LGPL-2.1-or-later** and
  **`nsis7z.dll` carries 7-Zip's LGPL-2.1**; neither binary holds a licence
  string, and the NSIS archive holds no licence file. (c) The `web/` tree:
  **266 lock keys**, of which **twelve are `lightningcss` platform variants
  under MPL-2.0** and **`caniuse-lite` is CC-BY-4.0** — and the lock records
  no licence field at all, so that surface has no record anywhere in the tree.

> **Two numbers in this bullet, re-measured 2026-11-12.** (1) *The surface
> count.* A LabCairn distribution carries **four** surfaces, not three:
> `NOTICE` §0.1 names the python dependency closure (171 items), the shell npm
> tree (268), the installer-distributed binaries (8) and the web npm tree
> (266). The bullet's three are the three outside the python closure, and
> "NOTICE named one" counts within those three — the shell tree. `NOTICE` §0.1
> read "Four surfaces carry third-party material" in the same commit that
> widened the scope (`df18d46`), so the three here came from that commit's
> subject line rather than from `NOTICE`. (2) *The MPL-2.0 keys.* The twelve
> MPL-2.0 keys are the `lightningcss@1.33.0` family: the base package
> `lightningcss@1.33.0` itself **plus eleven** platform variants, so "twelve
> are `lightningcss` platform variants" is off by one in the base package's
> favour. `NOTICE` §2.6 enumerates the same twelve as "MPL-2.0 — 12 of the
> 266 keys", and `caniuse-lite` is the one CC-BY-4.0 key. The bullet's other
> half — "the lock records no licence field at all" — still holds: the web
> lockfile carries no `licence:` field. What no longer holds is "that surface
> has no record anywhere in the tree": `NOTICE` §2.6 records the web tree, and
> `web/src/thirdPartyNotices.test.ts` and `shell/test/notice-scope.test.mjs`
> witness it. The bullet is left as written; this note names what changed.

- **Four decisions, taken 2026-11-12.** (1) **Keep the LGPL-2.1 plug-ins and
  discharge the obligations** — the licence text, the notice and the source
  access go into the record and the deliverable. (2) **Widen NOTICE's scope**
  to the toolchain binaries and the web tree. (3) **Restore React's MIT
  attribution** through a `THIRD-PARTY-NOTICES` file shipped beside
  `web-dist`; the production bundle carries no `MIT`, `Copyright` or
  `license` string at all. (4) **Defer** both the per-binary licence-table
  witness and the Chromium payload survey.

### The drain witness's dose stops resting on a measurement (2026-11-11)

- **The CI failure.** `shell-test (ubuntu-latest)` failed on the first run of
  the declarations batch with *"the dose request answered on the undrained
  arm, so the dose did not fill the pipe and the drained arm measured
  nothing"*. **The same job passed on the previous run of the same tree**, and
  `shell/` had not changed between them — the property was in the
  measurement, not in the code the batch touched.
- **What the two runs measured.** The threshold is a measurement taken with a
  deadline: a probe that has not reported within `PROBE_TIMEOUT_MS` is read
  as parked. A loaded runner makes a **slow** write look like a **parked**
  one, so the threshold came out smaller than the pipe really was — 131,072
  against 262,144 on the passing run — and the dose, sized from that
  measurement alone (`threshold + 8 KiB`), no longer filled the pipe. The
  undrained arm, the one that is supposed to prove a stall, could not prove
  one.
- **The fix.** The dose is now the larger of `threshold + margin` **and twice
  the ladder's largest step**: the ladder's top bounds what this machine's
  pipes can hold, so a dose above it fills the pipe whatever the threshold
  said. `PROBE_TIMEOUT_MS` went from 4 s to 10 s, so a slow probe is less
  likely to be read as parked. The measurement stays — it is the number the
  record cites — and a new assertion holds the dose above the ladder's
  largest step. The dose is 2,097,152 bytes, under the drain log's 4 MiB
  ceiling, so the drained arm's `sink.writtenBytes >= dose` still holds.
- **Its mutation check.** The failure was reproduced deliberately: with the
  dose restored to `threshold + margin` and the threshold under-measured to
  8,192, the witness went red on `undrained arm: the same child and the
  same dose reproduce the stall` — the assertion the runner failed on. With
  the same under-measured threshold and the fix in place, it stayed green.
  `node --test shell/test/*.test.mjs` measured **44 pass / 0 fail**.

### The batch is delivered: PR #156 merges (2026-11-11)

- **The accumulated batch was delivered and merged.** 108 commits went up as
  `delivery/phase-3-batch-2026-11-11` and merged as
  `777bb63192af4cb5aef51cd561d5031353d1f230` through
  [PR #156](https://github.com/gg320324492-lgtm/labcairn/pull/156): 18
  checks passed, and the schedule-only `evaluation` job skipped by design.
  The delivery branch is deleted on both sides. The merge changed no
  witness: the ledger across `486d6c0..777bb63` reports `LOST -- none` and
  `ADDED -- 15`.
- **The whole suite was measured locally as well.** 5,192 passed, 24
  skipped, 0 failed in 41m06s on this Windows machine; all 24 skips are
  environmental by construction — POSIX permission bits, 8.3 short names on
  a volume that has none, `playwright` not installed, and the real-provider
  smoke that needs the owner's authorisation to spend money.
- **The live pointers now say what is true.** The three of them carried "99
  commits ahead" and "no push, pull request or CI run is authorised"; both
  statements were true when written and false after the merge, so they name
  the merge commit instead.

### The installer is built, a silent gap is found, and the first fix is wrong (2026-11-11)

- **T08's packaging was run, not only configured.** In an isolated worktree,
  electron-builder 26.18.0 produced the per-user NSIS installer
  `LabCairn Setup 0.0.0.exe` (124,536,512 bytes, SHA-256
  `da483fd949efba5e603bd8b47d0f57dfedd26f61b6469c69a59dac3e6e1241ea`); the
  signature was measured `NotSigned` on both the installer and the unpacked
  executable; the app.asar carried eight entries outside `node_modules`
  (`package.json` and the seven files under `src/`), and
  `resources/web-dist` carried the three bundle files byte for byte. The
  build printed `default Electron icon is used`, so the artifact wears
  Electron's icon. The products and the raw logs stay outside the tree, in
  `E:\labcairn-local\phase3-g1-evidence\installer-build-2026-11-11`.
- **The run found a defect that no earlier audit had named: an installer
  shipped without its frontend.** A build with no `web/dist` exited 0 and
  produced an installer whose `resources/` carried no `web-dist` at all —
  electron-builder prints one line for a missing source and keeps going.
  Nothing in the build said the packaged window would not render.
- **The first attempt at closing it was wrong, and another window's build
  caught it.** The guard was committed as `806e3dd` with its check running
  at module load and no default export. electron-builder resolves
  `beforeBuild` with `resolveFunction`, which takes `m[name]` or
  `m.default || m`; with neither, the module object is called as if it were
  a function and the packaging dies with `beforeBuild is not a function` —
  with the bundle present. The seven cases stayed green throughout, because
  they exercised the script's own command line rather than the shape the
  packaging command uses. That is this project's own rule caught in the act:
  a witness that asks a different question stays green while the property
  is broken.
- **The guard was reshaped, and both sides were measured on the real
  command.** The hook is now a default export with no top-level side
  effect, and it returns `true`, because a falsy return would make
  electron-builder treat the dependencies as handled elsewhere and skip its
  own rebuild. With the bundle present the build exited 0, produced the
  installer, carried `@electron/rebuild` in its log and put the three bundle
  files in `resources/web-dist`; with the bundle moved away it exited 1,
  said `the packaging guard refuses this build`, and left its output
  directory empty — no installer, so no half-built shell can ship. Five
  cases in `shell/test/packaging-config.test.mjs` watch the hook in the
  shape electron-builder calls it, and their mutation check reddens when
  the default export is removed, when the hook lets a missing bundle
  through, or when it returns a falsy value. The shell's Node floors move
  from 38 to 43 cases.
- **The packaged bundle had no reader, and now has one.** A packaged build
  carries the web bundle at `resources/web-dist`, and nothing read it: the
  run configuration asked for `LABCAIRN_SHELL_STATIC_DIR`, and nothing in
  the package supplies it. The bundle's place in the package is not a guess
  about the working directory, so the shell now derives it from Electron's
  resources directory, and one more case in `shell/test/config.test.mjs`
  watches that a packaged run finds it, that an explicit setting still wins
  and that a dev run still has none. Its mutation check reddens when the
  derivation is dropped or names another directory. The shell's Node floors
  move from 43 to 44 cases.
- **Two gaps stay named.** The package carries no Python backend, so
  `LABCAIRN_SHELL_CLI` names an entry point the installer does not contain,
  and the three environment variables the run needs are supplied by nothing
  in the package. T08 therefore delivers a package that can be built and
  inspected and not one that is known to run; the backend's own arrangement
  is O3's unmeasured decision, and the drill that would prove the whole
  thing runs is T09's. The owner decided on 2026-11-11 to close the reader
  and leave these two named.
- **What is still open.** The signed installer (`W28`), T09's clean-Windows
  drill and AC-6 remain unperformed, and the artifact wears Electron's
  default icon. The acceptance record's §10.4 carries all of it.

### The three answers are carried out, and a cost anchor drifts (2026-11-11)

- **The three dialog answers of the section below are now on the tree**, in
  commit `27d7306f4ad220a9e7ef5620010659734ee371f8`: the six NOTICE hunks
  from `90d08c2` are applied, the three live pointers carry a dated
  measurement anchored to a printed SHA instead of a live ahead count, and
  the four reports' conclusions are in this archive. Measured on that tree:
  38/38 Node shell tests, 615 passed and 2 deselected targeted Python
  tests, `ruff check` and `ruff format --check` clean, `mypy --strict`
  clean over 430 source files, and the witness ledger reporting
  `LOST -- none` across both `bf2f6f4^..bf2f6f4` and `bf2f6f4..HEAD`.
- **A fresh measurement found the evaluation job's cost anchor stale in
  four places.** `.github/ci-shards.json` carries
  `measured_at = 46e2c21918286a723f9d07d5409d0e52e7551a85`, and summing
  its per-file costs over the files `evaluation/manifest.py` assigns to the
  five offline classes gives **1622.3 s (about 27.0 min)** on
  `ubuntu-latest` and **4478.4 s (about 74.6 min)** on `windows-latest`.
  `.github/CI.md`, `.github/workflows/python.yml` and
  `docs/plans/LC-P1-13-evaluation-ci.md` still printed the earlier anchor
  `49e81f2` and the total that anchor gave — 1450.0 s, about 24 minutes —
  and the previous batch's record named this as one of the risks the owner
  chose to record rather than change.
- **The owner ruled that the three comments are corrected and watched.** The
  figures and the anchor are now the measured ones, in all three documents
  and in the workflow's own comments; the job names, the triggers and the
  commands are untouched. The `325.8 s` figures in `.github/CI.md`'s
  slow-file section and in `docs/handoff/CURRENT.md` are left as they are:
  that section is dated 2026-11-02 and says so, and the handoff paragraph
  anchors its figures at `cf081e4`.
- **A witness now holds them.**
  `tests/test_ci_shard_coverage.py` gains
  `test_the_cost_figures_the_documents_print_are_the_costs_the_table_measures`,
  which recomputes the five-class total from the shard table and the
  manifest and asserts that each document prints that total and that
  anchor. Its mutation check: moving one file's cost in the table turns it
  red (the table's 1730.5 s against the documents' 1622.3 s), moving the
  figure in `.github/CI.md` turns it red too, and restoring both bytes
  turns it green. The file is one the cost witness excludes by name, so
  adding the witness costs no runner measurement.

### The NOTICE full surface lands, and four audits report (2026-11-11)

- **The full shell dependency surface lands in `NOTICE`** (merge
  `bf2f6f450c93104b34fac38d4f853880dca53872`): 268 packages from the T08
  lockfile are recorded as 13 runtime and 255 build-only packages, with
  licence identifiers and holder lines read from registry metadata and each
  package's own licence file. `shell/test/notice-licences.test.mjs` watches
  the coverage; `tests/test_shell_ci.py` records eight Node files with a
  38-case floor. The merged tree measures 38/38 Node tests and 595 targeted
  Python tests (two command witnesses excluded because stale local services
  hold the console script).
- **Four independent read-only reports followed the merge.** A post-merge
  consistency review found 12 findings (three high-priority stale
  projections and acceptance pointers, six medium record drifts, and three
  owner-side or residual boundaries); the conductor corrected the
  current-tense records and left dated historical measurements intact. A
  second runner red-item dry run measured eight workflows and 22 unique
  rendered job names and found no shard-cost re-measurement owed under the
  slack rule. A work-order-draft critique found all four nominally issuable
  drafts unsafe at the current tree. An archive byte-conservation
  reproduction measured 84,954 bytes, 19/19 checks and a matching SHA-256;
  the earlier 84,630 figure was a UTF-8 character count mislabelled as
  bytes.
- **Three owner decisions were answered by dialog on 2026-11-11.** A
  stray-commit review compared the three post-merge commits on the old
  NOTICE branch
  (`c884f254ca7fff2f3dd60e188a1a3dd1b9280f8c`,
  `90d08c26423cba70471b2e57389810ca0785cd18`,
  `da0bbc3e11f55c38a86f62505cadc4eaffad5cd2`) and recommended absorbing
  only the NOTICE anchor fixes; the owner chose that, so the six NOTICE
  hunks from `90d08c2` were extracted, checked with `git apply --check`
  and applied, while `c884f25` and `da0bbc3` stay unmerged on that
  branch. One consequence of that choice is recorded here rather than
  repaired: `NOTICE` §1 is anchored at `c884f25`, which is not an
  ancestor of `main`, so a reader on `main` cannot `git show` it, while
  the tracked-file count it names (833) is the count `main` HEAD also
  measures (833). The anchor is printed and the figure is right; the
  revision it names is reachable only from the old branch. The owner also chose to replace the live ahead count in the
  three live pointers with a dated measurement anchored to a printed SHA
  (`3a62b9d4cfd440ab0f2b0c3c32c34fe2431511d9`, measured 99 commits ahead
  of `origin/main`), because a count that changes carries forward stale
  claims; a live count is re-measured at delivery instead. The third
  decision put these four reports' conclusions and the three decisions
  into this archive. The accumulated local batch stays unpushed for a
  later owner-authorised delivery: no push, no pull request and no CI run
  is authorised.

### Shell CI and T08 land, with the re-measured pointers (2026-11-11)

- **The shell's Node witnesses now have a runner job.** A new
  `.github/workflows/shell.yml` runs a single `shell-test` job on both
  platforms; `release.yml` no longer prints the literal `matrix.os` in a
  job name; the job-name uniqueness witness now reads every workflow;
  `tests/test_shell_ci.py` watches the shell WITNESS command, per-file case
  floors, and cross-workflow name collisions. Twelve Python WITNESS
  functions were added, and the three registrations were updated.
- **T08's minimal unsigned Windows packaging configuration landed.**
  `electron-builder` 26.18.0, a minimal NSIS configuration, a `dist`
  script, and `shell/test/packaging-config.test.mjs` now exist. The local
  build produced a 124,536,513-byte installer outside the repository; the
  signed installer, clean-Windows drill and AC-6 remain named gaps.
- **A merge-only defect was caught and repaired.** The shell CI floor
  table did not know T08's new test file after the two branches merged;
  the conductor re-measured `packaging-config.test.mjs` at 4 cases and
  raised the total floor from 27 to 31. The combined tree measures 31/31
  Node tests and 611 targeted Python tests (two command witnesses excluded
  because stale local services hold the console script). The witness
  ledger reports `LOST -- none` and `ADDED -- 12`.
- The live pointers were re-measured at
  `04a896e7d0b2e3e52530a50bb6cdf48507c48a43`: that tree was 93 commits ahead
  and carried 831 tracked files with 195 Markdown files. The archived
  79 / 87 / 823 / 826 figures are earlier dated measurements; such counts are
  re-measured at each merge rather than carried as current totals.

### Three readiness designs report, and the phase archives land (2026-11-11)

- **The shell's 27 Node tests have no CI coverage; a design recommends a
  new workflow.** The design window mapped all six `.test.mjs` files and
  the `pnpm test` command; no `.github/workflows/*.yml` references
  `shell/`. The recommended path is a new `.github/workflows/shell.yml`
  with a single `shell-test` job on both platforms, plus extending the
  job-name uniqueness witness to all workflow files. The report is
  outside the repository.
- **A Phase 3 work-order gap scan finds no uncovered §4 row** but names
  14 gaps (6 load-bearing), all owner decisions or inside LC-P3-05's
  not-yet-dispatched implementation stage. The report is outside the
  repository.
- **A shell named-gaps deep dive details T08, T09 and AC-6's minimal
  viable products**, tool lists and unsigned-executable boundaries. The
  report is outside the repository.
- The phase archives themselves landed in the same batch (merge
  `6251771`); the root `CHANGELOG.md` is now a 48-line container.

### The changelog splits into phase archives (2026-11-11)

- **Every dated section that had accumulated under `[Unreleased]` moves to a
  phase archive**: Phase 3's batch record, Phase 2's closeout and its
  category block, and the Phase 1 G5 close together with gates G0 to G4. The
  three archives are `docs/changelog/phase-1.md`, `phase-2.md` and
  `phase-3.md`; the root [`CHANGELOG.md`](../../CHANGELOG.md) keeps the
  container, the archives index and the reading rule.
- **The moved text is verbatim.** Measured by reconstruction: stripping the
  archives' added headers, undoing the link depth, and concatenating the
  three bodies reproduces `git show 79ced582c880749a9988d16133aaccbd16b90bd1:CHANGELOG.md`
  lines 19–1366 — 84,630 bytes — byte for byte. The root file's own body is
  the only part that is new.
- **A new dated section joins the archive of its phase**; an entry no phase
  claims yet joins the root container. The rule is stated in the root file.
- **What the split leaves unwatched is named.** The archives are `docs/`
  files, so `test_relative_links_in_docs_resolve` and the superiority watch
  read them. The root file's own outbound links were checked by no witness
  before the split and are checked by none after — the asymmetry the
  2026-11-10 real-half record documented when the root file carried
  sixty-eight such links; it now carries seven, all resolving.
- **Dated records elsewhere keep their wording.** `docs/acceptance/g5-review-product.md`
  quotes `CHANGELOG.md` calling G5 *"in flight"*; that sentence records the
  file's state at its date, and a frozen verdict is not rewritten to look
  current (the map's own rule).

### The live pointers refresh, NOTICE lands, and the G4 path is drafted (2026-11-11)

- **The three live pointers refresh to the 2026-11-11 state** (merge
  `354f387`): `docs/ROADMAP.md`, `docs/handoff/CURRENT.md` and
  `docs/README.md` now carry the 79-commit accumulated batch, certifi
  `2026.10.23`, the G4 checklist's 31 `PENDING` rows, and the NOTICE npm
  draft. Targeted witnesses measured **575 passed**; the ledger reports
  `LOST -- none`.
- **The desktop shell's npm dependency surface lands in `NOTICE`**
  (merge `9101597`): 13 packages documented from registry metadata and
  each package's own licence file — 10 MIT, 2 ISC, 1 Apache-2.0.
- Two further read-only windows reported outside the repository: a G4
  implementation path draft (all six installer tools absent from PATH,
  five unsigned-executable drill steps for T09, the version-switching
  gap is distinct from AC-6) and a CHANGELOG structural review (1359
  lines, 35 `h3` sections, ~835 lines added in six days; recommends
  splitting by phase into `docs/` archive files with zero witness-test
  changes). Neither is a deliverable; both are decision inputs.

### The certifi CRITICAL fix lands, and the readiness audits report (2026-11-11)

- **`certifi` upgraded `2026.7.22` → `2026.10.23`**, clearing the CRITICAL
  emSign intermediate-CA advisory. The worktree branch also removed the
  duplicate `python-docx` and `reportlab` declarations from
  `pyproject.toml` (24 lines of edit-accident debris). Targeted witnesses
  measured **546 passed**; `ruff check` and `ruff format --check` exit 0;
  the ledger reports `LOST -- none`. The exploitability assessment
  confirms certifi was the **only immediate** advisory of the 25 found;
  one is deferred (`pytest`), and 23 are not applicable to this project's
  usage patterns. The branch was deleted after merge.
- Four further read-only windows reported: a live-pointer freshness scan,
  an advisory exploitability assessment, a NOTICE npm coverage draft, and
  a residual cleanup inventory. The freshness scan found all three live
  pointers (`ROADMAP`, `CURRENT`, `docs/README`) stopped at the
  2026-11-10 refresh; the five CHANGELOG-only commits since are absent
  from all three. The NOTICE draft documents 13 npm packages (10 MIT,
  2 ISC, 1 Apache-2.0) from registry metadata and each package's own
  licence file. The cleanup inventory measured ~129.71 GiB logical length
  in the old worktree directories and ~12.69 GiB in the new temp tree.
  No process was killed and no file was deleted.
- The live pointers will be refreshed in the next record commit. The
  NOTICE patch is a draft awaiting owner authorisation to land in the
  tree. No runner or CI run was started, and no push, pull request or
  commit was authorised by the reports themselves.

### Dependency surface audit and the gate-readiness scans (2026-11-11)

Four further read-only windows reported: a dependency surface audit, an
execution-plan §4 row coverage scan, a half-loop 16-row reopen SOP, and a
residual cleanup inventory (stopped before finishing). Their reports stay
outside the repository.

The dependency audit found **one CRITICAL advisory** on
`certifi==2026.7.22` (compromised emSign intermediate CA keys bundled in
the root store; fixed in `2026.10.18`) and 24 further advisories on six
Python packages (`pyasn1` 4 HIGH, `filelock` 17, `fastmcp`/`fastmcp-slim`
1 MODERATE, `joserfc` 1 MODERATE, `pytest` 1 MODERATE). The shell side is
clean: `pnpm audit` 0 findings, electron 45.2.3 as approved, the approved
set equals the lockfile set exactly, and all 34 direct dependencies are
MIT-compatible. The audit also found `pyproject.toml` declaring
`python-docx` and `reportlab` twice each, and `NOTICE` not covering the
shell's npm dependency surface. The certifi upgrade is an owner decision;
no package was installed, upgraded or removed.

The §4 coverage scan maps all 31 G4 findings to the eight
execution-plan §4 rows; every finding lands on `Distribution and review`
(121), confirming that the other seven rows are unshown pending the
installed build. The 16-row reopen SOP is ready for owner observation
with the two-stage confirmation flow. No process was killed, no file was
deleted, no package was upgraded, no runner or CI run was started, and no
push, pull request or commit was authorised by the reports themselves.

### Gate-readiness reports and the owner's disposition (2026-11-10/11)

Four further read-only windows reported on gate readiness: a runner
red-item dry run, an independent critique of the G4 classification
checklists, a WPS screenshot observation SOP, and a human-checklist
boundary review. Their reports and tools stay outside the repository.
The conductor re-measured the stable facts: shard-cost freshness needs no
new runner measurement at this tree (the recorded slack covers the two
changed test files), 174 Python test files are registered in all three
places, `ruff check`, `ruff format --check` and `mypy` exit 0 locally,
the 44-row checklist is 4 PASS / 40 `PENDING-HUMAN`, and the separate
16-row real-sample reopen ledger is 16/16 `PENDING-HUMAN` with 208 empty
human-observation cells. The screenshot SOP's existing validator returns
PASS and direct exit status 0 without opening a DOCX or writing a CSV.

The runner report's `uv` network errors did not reproduce in the
conductor's later targeted run (548 passed); they are recorded as a
transient machine condition, not a stable red item. Two historical
workflow declarations remain owner decision items: `release.yml` prints
the literal `matrix.os` in a job name instead of interpolating it, and
three comments still cite `49e81f2` although `ci-shards.json` carries
`measured_at = 46e2c21918286a723f9d07d5409d0e52e7551a85`. The owner chose
to record these risks without changing `.github/workflows/` in this
batch. Stale shell rehearsal services still hold the compiled console
script and nine loopback ports; the owner chose not to terminate them, so
the two README `uv` command witnesses remain a machine-local condition
rather than a claimed green.

The independent critique found four critical defects and four measured
gaps in the two unsigned G4 preparatory checklists. The owner chose to
send those findings back to the original windows, and both revisions
passed the conductor's re-review. The G4 checklist revision 2 carries 31
classifiable rows (15 blocker / 10 measured gap with the sole
owner-authorised carve-out / 6 routed defect), deletes the unauthorised
pre-gate `G` override, separates the trial and signature rows, names the
exact 44-row composition, keeps the 44-row and 16-row ledgers distinct,
and gives H-01/H-03/H-06 their own evidence-addressed findings. The ten
08 drafts revision 2 keeps one owner-signature surface at the G4 table,
carries only draft labels, and re-anchors every repository pointer to the
current head. All 31 signatures stay `PENDING`; these remain external
drafts, not an owner classification or gate verdict. No process was
killed, no workflow was changed, no runner or CI run was started, and no
push, pull request or commit was authorised by the reports themselves.

Three further decisions were answered by the owner on 2026-11-11: the G4
31-row checklist stays `PENDING` until the gate's implementation (the
installed build and the trial) is complete, at which point the named human
reviewer, independent agent second reader and third reader are designated;
the 74-commit accumulated batch stays unpushed for a later owner-authorised
delivery; and the remaining 40 dual-host checklist rows continue through
owner-supplied WPS screenshots with the conductor's two-stage confirmation
flow.

### Delivery preparation reports, still local only (2026-11-10)

Four further read-only windows prepared delivery material outside the
repository: a 13-group commit inventory and 11-row risk card, ten
`LC-P3-08` observation drafts (`FO-03` through `FO-12`, every owner
signature `PENDING`), a hardened half-loop boundary checker, and a
stale-process cleanup plan. The conductor re-measured the inventory's
71-commit / 13-group arithmetic, the checker's **16 PASS / 0 FAIL** clean
run, three red counter-mutations plus one green control, and the plan's
27 stale service processes across nine listening ports. No process was
killed, no runner or CI run was started, and no tree or ledger input was
changed by those windows.

The risk card is an inventory of what a future runner and the owner must
decide, not a pass claim. Its R-10 finding corrected the attribution count
above: a number measured at a 70-commit range cannot be carried as a
current total after another commit lands. The 08 drafts do not classify
findings on the owner's behalf, the hardened checker does not re-run the
42 arms, and the cleanup plan is a decision item rather than permission to
terminate services. All four reports stay outside the repository.

### Pre-delivery audits and the pointer refresh (2026-11-10)

Four independent read-only windows reported on the accumulated local batch:
a full-range static audit, a G4 owner classification checklist, a WPS
screenshot checklist validator, and a second reader for the 42-arm machine
half. Their reports stay outside the repository. The conductor re-measured the
witness ledger (`LOST -- none`, 3579 → 3579), 174 registered Python test files
across five shards per platform, and the 42/42 machine half's counts, three
ledger digests and report digest. At the named 70-commit range
`origin/main..e3aed01`, `git log --format` measured 20 harness-injected
`Claude Sonnet 5.5` attribution lines and 50 `Claude Code` lines; the current
71-commit range adds one `Claude Code` line and is re-measured at delivery
time rather than carried forward. The full-range audit separately measured
966 relative links and anchors with none broken; its targeted link and anchor
witnesses were re-run here. No raw material, material filename, reply or
credential entered the range diff.

The audits named record-layer lags rather than product failures. This
refresh moves the 42-arm machine loop out of `ROADMAP.md`'s open list, updates
the English and Chinese README banners and `docs/README.md`'s current-phase
row, replaces stale "expected red" shard-cost sentences with the runner
re-measurement, re-anchors the support matrix, §5.10 and 08's evidence map
to the re-targeted witness and landed record, re-measures the repository
map's file count, and records that the owner will install Word 2010 later
for the same screenshot observation mode. The G4 checklist's 31
classifiable items and the 44-row checklist's 40 pending rows remain owner
work; no owner signature, gate verdict, host result, whole-suite pytest
run, runner run, push, pull request or CI run is claimed here.

The pointer refresh's targeted witnesses measured **703 passed** with two
README command witnesses deselected. Those two call `uv run labcairn --help`;
on this machine `uv` could not replace `.venv/Scripts/labcairn.exe` because
older local shell-rehearsal services still hold the console script
(`os error 32`). The stale process command lines were printed, no process was
killed without the owner's decision, and the two failures are not claimed as
green. They remain an environment cleanup condition for a later whole-suite
run, not a defect in the edited records.

### The real-sample machine half lands, with the human half held open (2026-11-10)

- `LC-P3-02`'s owner-picked advisor sample ran its 42-arm machine loop:
  42/42 arms, 14 produced, 28 refused, 0 errors, 0 expectation mismatches,
  8 artifacts, and report digest
  `a003a12ca9603a112e5ad962278238a978eea377a6cc1b05bed1667c947fb638`.
  The dated record is
  [`LC-P3-02-real-sample-2026-11-10.md`](../acceptance/LC-P3-02-real-sample-2026-11-10.md),
  with a JSON summary and three append-only ledger digests. A read-only
  independent critique found that partial records printed a false zero
  artifact count, used final/completion wording too early, lacked a ledger
  digest and attributed batch exits without a measured status. The generator
  was repaired and the final record re-rendered; the append-only ledger was
  not rewritten.
- The substitute-run record, its `test_docx_edit_records.py` witness, the
  board's `LC-P3-02` row and §17, and `LC-P3-08`'s evidence map were
  re-targeted in one batch to the measured machine-half state. That state
  closes no human half: the dual-host reopen remains `NOT RUN` and no
  ticket verdict is transferred from the machine loop to the gate.

### Owner decisions on the in-flight G3/G4 batch (2026-11-10)

Two rounds of decisions were answered by the owner through the session's
dialogs while the implementation windows and their background measurements
were in flight. The first round covered the shell attribution lines, the
42-arm loop and named gaps. The second round ruled that the shell's 17
independent-critique findings are listed as gaps at the gate rather than
repaired in this batch; that stale records and `pyproject.toml`'s
`norecursedirs` are corrected now; that the accumulated local commits stay
unpushed until a later owner-authorised delivery; and that the remaining
40 dual-host checklist rows are collected through dialogs from the owner's
own observations. None changes a measured result or authorises a push, pull
request or CI run.

A later dialog narrowed the 44-row checklist's personal verification to the
WPS host only. That ruling applies to the 44-row checklist and not to the
real-sample half-loop's separate 16 human-reopen rows. Word 2010 rows stay
`PENDING-HUMAN`; the owner will install that host later and observe its
remaining rows with the same screenshot mode, so they are deferred, not cut.
A WPS observation is never copied into them or treated as a Word result. If
the owner supplies a WPS screenshot, the conductor reads only the visible
structure's presence and waits for a separate confirmation before filling any
form value. Screenshots and material words do not enter the repository.

- The four Electron shell follow-up commits already made at the time of the
  decision keep the
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` line injected
  by the harness. The static audit of `main` at `1670e73` measured fifteen
  such commits there: eleven earlier Electron shell commits and four
  `LC-P3-07` design commits. Since that audit, the four shell follow-up
  commits and one `LC-P3-02` real-sample re-render commit entered the
  accumulated range with the same harness-injected line: **twenty commits in
  the current range**, none amended. New commits use the current
  `Co-Authored-By: Claude Code <noreply@anthropic.com>` line. The count was
  re-measured after the later merges rather than carried forward.
- `LC-P3-02`'s real-sample half-loop continues to all 42 arms. A 33/42
  append-only ledger is a partial measurement, not a completed loop; the
  substitute-run record and its witness are re-targeted together only after
  the final acceptance record lands.
- The Electron shell batch may be reviewed and merged locally with its
  measured `T08`, `T09` and Windows graceful-shutdown gaps named as gaps.
  Those gaps are not converted into passing rows; their classification is
  signed by the owner at the gate's exit decision.

### The Electron shell skeleton runs, and the drain rule is witnessed (2026-11-10)

- A new top-level `shell/` (beside `web/`, nothing under `src/labcairn/`
  touched) carries the main process the plan describes: a service supervisor
  that attaches `data` readers to both child pipes at spawn and drains them
  into a bounded log file outside the repository, readiness as the
  `ServiceStarting` line **and** a `GET /health` 200, a window built with
  `nodeIntegration: false` / `contextIsolation: true` / `sandbox: true`, a
  CommonJS preload exposing one status getter and no token, and a config module
  that refuses a dev page URL in a packaged configuration.
- The drain witness (`shell/test/drain-witness.test.mjs`) is O6's control pair
  — the same injected writer child and the same dose run drained and undrained,
  the undrained arm reproducing the stall — plus a real-`labcairn serve` arm and
  a foreign-listener refusal arm. **The dose is measured, and the measurement
  corrected an assumption:** the witness's first run carried the record's
  4,096-byte anonymous-pipe number and the undrained arm answered the dose,
  because `spawn`'s own pipe measures 114,688 fits / 131,072 stalls here; the
  file now runs its own ladder (`8192…131072:stalls`) and asserts
  `dose > threshold` before either arm executes. Two counter-mutations were run
  and both reddened what they should: removing the production reader, and
  swapping a `file://` page load into the packaged path.
- Two rehearsals close the loop on a real window: the packaged-shaped run
  (service carries `web/dist`, page asserts its own origin over CDP, service
  force-killed from outside, the same window shows `disconnected`, no respawn;
  closing the window exits 0 with no orphan and a free port) and the dev-mode
  run against the repository's **own** Vite arrangement — Vite started with a
  config that imports `web/vite.config.ts` and overrides only the proxy target,
  because port 8000 belongs to Docker Desktop on this machine and the rehearsal
  neither displaces a foreign listener nor edits another window's file. The
  dev page reaches the API through the inherited proxy; a packaged-shaped run
  loads no dev origin, asserted from inside the page.
- A measured finding that changes what a later step must build: on Windows,
  Node's `child.kill('SIGBREAK' | 'SIGTERM' | 'SIGINT')` reaches none of a
  Python child's handlers in any of four spawn arrangements (twelve runs, all
  `handler=no handler ran`), so the G1 helper's graceful-ask assertion
  (`outcome.forced is False`) has no Node equivalent by that route. The witness
  asserts what is measured — the child ends, the port releases, no pid survives
  — and prints the outcome rather than claiming the ask worked. Record:
  [`LC-P3-05-shell-skeleton-2026-11-10.md`](../acceptance/LC-P3-05-shell-skeleton-2026-11-10.md).
- `electron` **45.2.3** (MIT) is added to `shell/package.json` with a committed
  lockfile, matching the selection record's measured version. **Correction,
  2026-11-10**: the owner approved Electron 45.2.3 / MIT /
  `shell/pnpm-lock.yaml` by dialog that day — the approval is no longer
  outstanding. `pyproject.toml`, `uv.lock` and the `web/` manifests remain
  untouched. The skeleton-batch wording below this line is left as written;
  the follow-up batch's dated section (§10 of the acceptance record) names
  which of the gaps it closed. No board row moves.

### The shell skeleton's named gaps, closed where they could be (2026-11-10)

- **T05's live 401 half**: a real Electron window sends one fixed tokenless
  `POST /task/select` from its sandboxed preload; the real service's
  `SessionGuard` refuses **401 `session_required`**; the main process validates
  the IPC sender's **origin** before printing or echoing the verdict, and the
  status strip shows it. The diagnostic page (`about:blank`, origin `null`) is a
  refused sender. `shell/test/live-guard.test.mjs` (5 tests) reads the request
  back out of the file that builds it and drives both IPC decisions;
  `shell/scripts/rehearse-live-guard.mjs` reads strip, bridge and the main
  process's line back over CDP.
- **T06's three unwitnessed arms**: `shell/scripts/rehearse-lifecycle.mjs`
  witnesses startup refusal (visible diagnostic on `about:blank`, no foreign
  page), a main-process crash injected over the real `--inspect` (no service
  orphan, port released), and the single-instance lock (second launch exits 0,
  starts no service, first shell and child stay alive). Each run gets its own
  `--user-data-dir`, except the second-instance arm where a shared directory
  is the property under test.
- **AC-7 / AC-8 static halves**: `shell/test/dependency-surface.test.mjs`
  (3 tests) watches the runtime surface and the approved dependency set, with
  an introduced remote host as positive control;
  `shell/test/native-surface.test.mjs` (6 tests) watches the enumerable
  preload surface, `webPreferences`, the two spawn call sites and
  COM/ProgID/UI-automation routes, with a real `shell.openExternal` plus a
  `'Word.Application'` ProgID as positive control. Both record what they do
  **not** cover: Electron's install-time binary channel and §0 rule 2's
  human review.
- `node --test "shell/test/*.test.mjs"` → **27 pass / 0 fail**. Thirteen
  counter-mutations, run singly with a clean-tree baseline and a parse gate,
  were all effective (12 red, one comment-only control green). Three defects
  in the measurement harness itself — two concurrent runs, an off-by-one
  splice, and a shared Electron `SingletonLock` — were found, repaired and
  recorded in §10.3 of the acceptance record.
- **Still named gaps, by the owner's 2026-11-10 decision**: T08 (packaging /
  O3 runtime arrangement), T09 and AC-6 (clean-Windows drill, signing behind
  `W28`, support limits, §0 rule 2 review), and AC-2's Windows graceful-ask
  arm (§6.2's measured gap, not attacked). No installer tooling, WiX/NSIS/
  Inno or `signtool` exists on this machine; no green is claimed for them.
  Evidence: [`LC-P3-05-shell-skeleton-2026-11-10.md`](../acceptance/LC-P3-05-shell-skeleton-2026-11-10.md)
  §10. Nothing pushed, no PR opened, no CI run started.

### Phase 3 G4 owner decisions and the Electron shell choice (2026-11-10)

- The G4 drafting round found that the board's `LC-P3-07`/`LC-P3-08` row
  was stale: §§12–13 were already issued work orders (2026-11-09), not
  missing ones. The owner answered eight decisions the same day through
  the session's dialogs, and the answers are published in place at the end
  of §12 and §13, with the board row corrected in the same commit: this
  is a ground-truth revision of the issued orders against the 2026-11-10
  G2/G3 landings, not a first issuance and not a re-decision of §14's
  answered items. 07/08 stay `NOT STARTED`, blocked on `LC-P3-05`'s
  installed build; design work is labelled design, not deliverable until
  run; one real sample supplies both 02 and 08; the `root_kinds` seam is
  named, not widened; the named reviewer is a human plus an independent
  agent second reader with a third-reader arbiter; publication joins the
  next owner-authorised batch, with no push, PR or CI run of its own.
- [ADR-0023](../adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md)
  is **Accepted** on the owner's Electron choice (the only candidate
  buildable on this machine in the selection measurement), and
  [`LC-P3-05-shell-implementation-plan.md`](../plans/LC-P3-05-shell-implementation-plan.md)
  carries nine implementation steps. O6's measured lesson — a traceback
  written into a pipe nobody drains stops the event loop — is a hard rule
  of the main process with a witness design attached. The O6
  precondition in the selection record is discharged.
- The real-model half of `LC-P3-06` ran bounded on synthetic samples:
  5 requests, 0 refused, 0 failed, 5,136 of 50,000 authorised tokens,
  stop-loss never fired, dry reconciliation MATCHED before the spend;
  record [`LC-P3-06-real-half-2026-11-10.md`](../acceptance/LC-P3-06-real-half-2026-11-10.md).
  The record names seven measured gaps, including that the ladder's
  four-request layout produced no locatable suggestion, that no timeout
  was actually drilled, and that its audits are operator self-review.
  No key, response prose or advisor material entered the tree.
- **The owner closed the follow-up question the same day:** on the five
  decisions surfaced by the bounded follow-up design (kept outside the
  repository), the owner chose no real-call follow-up now (D1). The
  remaining 15 requests / 44,864 tokens stay unspent; G4's structural
  question is routed to `LC-P3-08`'s suggestion path and G5 stays witnessed
  by the landed substitute rehearsal. D2 (G5 first) is recorded as the
  conditional answer only; D3–D5 (arm caps, G4's allowed change, consent and
  review) were not triggered, and no credential was read.
- The Electron shell skeleton (plan steps 1–3) landed with 13 Node
  witnesses, the drain rule wired before the child can write, and a record
  that names the whole Python suite as not run: see
  [`LC-P3-05-shell-skeleton-2026-11-10.md`](../acceptance/LC-P3-05-shell-skeleton-2026-11-10.md).
  The synthetic dry run of `LC-P3-08`'s reviewer form (report outside the
  repository) found 12 observations; the two that made the form
  mechanically unusable were repaired in the tree — a classification
  precedence carve-out for owner-authorised named gaps, and F-11's dead
  `F-20` reference — while the other ten stay for the gate's form review.
- The batch delivery's first CI run failed five shard jobs on the
  shard-cost freshness witness, as designed: six test files had joined
  the suite since the previous measurement. The costs were re-measured
  from that run's own `--durations=0` log (run `42733499009`, Windows
  balance 1.000 / Ubuntu 1.274). That run's clean-room evidence also
  caught a dead `LC-P3-03` record link, fixed in the board and here.

### Phase 3 G2/G3 batch: four windows land locally (2026-11-10)

Four windows reviewed and merged into `main` by the conductor session, each
on its own branch, one ledger run per merge (`LOST -- none` in all four):

- **`LC-P3-03` — the project revision loop lands** (merge `4855ea6`).
  `src/labcairn/application/revision_loop.py` carries the loop from import
  receipt through read-only original, independent copy and publication
  receipt to the recovery path; four refusal classes
  (`cross_project_access`, path escape, stale approval,
  `loop_already_published`) are witnessed, and all four counter-mutation
  families were caught. 17 new witnesses registered in three places; the
  acceptance record is
  [`LC-P3-03-revision-loop-2026-11-10.md`](../acceptance/LC-P3-03-revision-loop-2026-11-10.md).
- **`LC-P3-06` substitute-first half lands** (merge `7d5be74`).
  `src/labcairn/providers/deidentify.py` (8-word n-gram pipeline, outbound
  CJK ceiling, named-secret scrub; three sample classes) and
  `src/labcairn/providers/bounded_run.py` (the refusal ladder harness,
  per-excerpt digest binding, the Q7 two-arm stop-loss, the
  digests-and-counts run record). 33 witnesses, 12/12 counter-mutations;
  every ladder tier fails to zero calls on budget or consent. The
  acceptance record is
  [`LC-P3-06-substitute-first-2026-11-10.md`](../acceptance/LC-P3-06-substitute-first-2026-11-10.md).
  The real half was still waiting on `LC-P3-04` and the sample when this
  entry was written; it ran the same day and is recorded in the
  2026-11-10 G4 entry above.
- **O6 — the event-stream stall is fixed** (merge `9cdb19a`). The mechanism
  is measured, no longer open: a refusal raised after the `200` and
  `text/event-stream` headers were sent became a traceback written into the
  service's own output, and a caller holding it in an undrained pipe
  blocked the event loop (pipe capacity 4,096 bytes, measured; one short
  stream wrote 6,205 bytes). The fix refuses an unwired stream at the route
  entry, before the headers; `events.py` holds the refusal sentence as the
  single source for both paths. The record is
  [`o6-event-stream-stall-2026-11-10.md`](../acceptance/o6-event-stream-stall-2026-11-10.md).
  The browser-gap row it replaced was re-measured, not deleted: the old
  witness asserted a contradiction that the fix removes, and the new one
  keeps the service-side half of the old assertion.
- **`LC-P3-04` — the binding loop lands** (merge `2dce121`).
  `src/labcairn/papers/binding.py` carries the loop's five rings — opinion →
  locate → suggest → apply → dossier — with the model's suggestion and the
  human's judgement held as separate records and the unresolved-opinion
  state an explicit three-way task; `reports/response_table.py` and
  `quality_report.py` render it inside ADR-0013's boundary, and the
  workbench gains a per-item review panel (`web/src/views/ReviewView.tsx`)
  consuming the existing artifacts/content endpoints. 17 Python witnesses
  (12 integration, 5 negative) and 5 web witnesses; 6 counter-mutations
  caught. The acceptance record is
  [`LC-P3-04-binding-loop-2026-11-10.md`](../acceptance/LC-P3-04-binding-loop-2026-11-10.md).
  The real-model half of `LC-P3-06` is what this unlocks; the shard costs
  of the day's four new test files wait on the batch runner run.
- The selection stage's O6 row was cross-referenced to the fix record, and
  `docs/THREAT-MODEL.md` gained the stall's own entry.

### Phase 3 G1 aftermath: work orders and platform rule (2026-11-09)

- [ADR-0022](../adr/ADR-0022-platform-conditional-code-keeps-one-reachable-body.md)
  accepted: platform-conditional code keeps one reachable body on both checker
  platforms — guards route through helper calls, Windows-only attribute reads
  carry scoped ignores, runtime semantics are preserved exactly. The five CI
  repair rounds it records were PR #153's own history.
- `docs/plans/PHASE_3-work-orders.md` carries the ratified work orders for
  `LC-P3-03` … `LC-P3-08` (§8–§14, drafted against main `571e4346` by an
  independent session and issued on the owner's selection). `LC-P3-06` stays
  `BLOCKED` on the provider's seven fields; every ticket whose §14 decision is
  unanswered stays `NOT STARTED`. The trailing sections renumbered to §15–§17.
- `PHASE_3-work-orders.md` §3 rule 3a names the ADR's shape as a standing rule.
- **The §14 owner decisions were answered the same day** (items 1–7, through
  the session's decision dialogs; answers recorded in place under each item):
  G2 runs `LC-P3-03` → `LC-P3-04` sequentially; the `LC-P3-05` selection
  stage may start; all seven provider fields are answered and tabled as the
  authorisation record at §11's §4.9 (MiniMax endpoint and model, 20-request
  / 50 000-token budget, per-excerpt digest-bound outbound scope,
  `credential_file` on the trial machine, the scheduled-smoke GitHub secret
  uncreated this phase, synthetic samples first, compound operator-watched
  stop-loss, dev build before the installed build); ADR-0021's provisional
  adoption suffices for `LC-P3-04`; `LC-P3-03`'s temporary-mechanism
  disposition leaves the ADR's text alone; `LC-P3-08` runs with the
  "One real model" row held open. The real advisor sample stays a named gap:
  the owner named batch A of the uploaded micro-nano-bubble corpus as the
  initial advisor material, and the whole corpus (111 `.docx` files) was
  fingerprinted into an operator-side registry outside the repository —
  structure-only, no prose in the tree, §5.9's label unchanged until the
  single sample file is picked.
- **The sample was picked the same day**: from batch A's fingerprint ranking
  the owner chose the green-algae inhibition paper's advisor-annotated
  version (sha256 `9154e56c…7652d`, 4 comments / 270 ins / 119 del / 10
  media parts; the project's structure survey carries eight classes, blocks
  none). Its digest and counts are recorded at §5.9 and §14 item 4; the file
  itself stays outside the repository, and the real-sample half's `NOT RUN`
  label stands until the full loop runs on it. The selection stage's ADR
  number was corrected the same day: ADR-0022 is taken, so `LC-P3-05`'s
  selection ADR names ADR-0023 as of this writing and re-checks at issuing.

### Phase 3 planning proposal (2026-11-06)

- The owner accepted a proposed Phase 3 exit gate: a Windows research-group
  internal trial with one complete DOCX revision loop, substitute-first
  validation and one bounded real-model check. Multi-platform public
  distribution moves to a later work package. This is a planning direction,
  not an approved work order.
- Two Chinese working drafts were found untracked and were not delivered.
  Byte-for-byte copies and the owner-supplied Word/PDF source stay outside
  the repository. They were replaced by an English
  [`PHASE_3-execution-plan.md`](../plans/PHASE_3-execution-plan.md) and
  [`PHASE_3-design-traceability.md`](../plans/PHASE_3-design-traceability.md),
  both marked `Proposal — not approved, not dispatched`.
- The execution proposal adds a code-facing gap register that names real
  entry points and missing capabilities. No product source, test, workflow
  or migration file is changed by this planning proposal.
- A dated [`PHASE_3-planning-decisions-2026-11-06.md`](../acceptance/PHASE_3-planning-decisions-2026-11-06.md)
  records the four owner decisions and the decisions that remain open.
  Q76, Q77, Q81, Q82, Q86, Q87 and Q96 stay unresolved.
- The owner authorised one planning-delivery PR and one runner run. No
  provider credential, real-model request, signing, tag, release or Phase 3
  implementation is authorised, and no runner result is claimed before the
  pull request reports one.

### Phase 3 gap-register correction (2026-11-07)

- Two independent read-only session audits checked the delivered Q1-Q96
  traceability and the code-facing gap register. The Q1-Q96 status table
  passed with all 96 rows and all seven unresolved source questions intact.
- The gap register now distinguishes a fidelity-preserving manuscript edit
  from the existing report-only DOCX writer, names the existing source-root
  read-only guard and `RetrievalTelemetry`, states that existing tests do not
  all carry `pytestmark`, and records that the web workflow is Ubuntu-only.
- No product source, test, workflow or migration file is changed by this
  correction. It remains a planning proposal, not a work order.

### Board answers and the multisource supplement (2026-11-07)

- The owner answered the board-opening decision dialogs. Confirmed: the
  `LC-P3-00`…`LC-P3-08` numbering, the Windows internal-trial exit gate with
  the §4 checklist as written, and the existing reviewer rules (agent
  stand-ins disclose literally; the arbiter is a third reader; the G4 row
  needs real advisor use). Deferred: the real-model provider fields stay
  unnamed, so `LC-P3-06` cannot start. Frozen from live measurement on the
  machine the owner named as the trial machine: Windows 11 Pro 26H2
  (build 26300) and Microsoft Office 2010 (14.0.7252.5000), verified via
  App Paths, the WOW6432Node InstallRoot and the ProgID. Reaffirmed: the
  desktop shell stays as scoped (`LC-P3-05`; signing deferred with W28) and
  the historical public-boundary entries stay untouched.
- The seven source gaps were ruled: Q76/Q81/Q86 recommendations adopted as
  owner decisions; Q86 and Q87 additionally received fresh owner segments;
  the project-workspace row closes by the owner's reverse-infer instruction
  (stem and options were preserved in the extraction with the selection
  recorded); Q77's per-layer rules and Q82's original remain open at their
  triggers. The in-tree traceability rows are unchanged until the drafted
  upgrade lands as its own batched commit on the owner's word.
- `docs/plans/MULTISOURCE-research-learning-plan.md` lands: the owner's
  research-event learning supplement (meeting audio, presentation,
  manuscript and paper as one project case; reviewed learning project-only
  by default; group publication behind advisor review and a separate
  sharing grant; a later phase for production ingestion). Its status
  sentences were aligned with this record before landing — the board is not
  open and nothing is dispatched.
- The §6 gap register gained a measured path-length row: the workspace
  atomic write names a 46-character temp file under a deep output layout;
  the 259/260-character Windows ceiling switch was reproduced with and
  without project code. The repair is an implementation-stage decision, not
  part of this proposal.
- The full-suite local recheck finished: 4964 passed, 1 failed, 14 skipped.
  The single failure was measured to the recheck run's own long
  `--basetemp` prefix — three green reruns at a short one, two red at a
  long one — not to these commits, and the witness ledger reported
  `LOST -- none`. These changes land as a third local documentation commit
  of the batch; no push, PR or CI run is authorised by them.

### LC-P3-00 board record and the WPS-primary baseline (2026-11-07)

- The board-opening decision record lands at
  [`docs/acceptance/LC-P3-00-board-opening-decisions.md`](../acceptance/LC-P3-00-board-opening-decisions.md)
  with the traceability status upgrades in the same commit: five of the
  seven recorded source gaps close by the owner's rulings of the day
  (recommendations adopted for Q76/Q81/Q86, fresh owner segments for Q86
  and Q87, the project-workspace row closed under the owner's
  reverse-infer instruction from preserved stems and options), while Q77
  and Q82 — for which nothing survived to reconstruct — stay unresolved
  at their triggers. The ticket numbering is adopted; adoption is not
  dispatch.
- The DOCX host baseline is corrected the same day, after the owner asked
  whether WPS was present: this machine carries WPS Office 12.1.0.29690
  (App Paths for wps/et/wpp, ProgIDs `KWPS.Document` and
  `KWPS.Application`) alongside Microsoft Office 2010. The owner ruled
  WPS the primary acceptance host, Word 2010 the compatibility
  reference; the §4 reopen rows and `LC-P3-02` are judged accordingly.
  The entry above naming Word 2010 alone stands as the dated text of its
  moment; this entry is the correction.
- The write-seam path-length row remains registered in §6 for the
  implementation batch, reaffirmed by the owner. No dispatch, no push,
  no PR, no CI run.

### Repository map re-anchored (2026-11-07)

- The current index is re-measured from the tracked tree: 733 files against
  the 727 of the 2026-11-06 scan. The six files since are the map itself and
  five Phase 3 planning and decision records; Markdown is the only class
  that moved, from 163 to 169. The 199 Python test files, 3,419 declared
  test functions, 38 fixtures and zero exact-byte duplicate groups were
  re-measured and are unchanged.
- `docs/plans/` now names the execution plan and the multisource supplement;
  `docs/acceptance/` now names dated owner decision records as a class.
  This is a current-pointer correction, not a rewrite of a dated snapshot.
  No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Current pointers re-anchored (2026-11-08)

- A read-only freshness scan of the current pointers found seven live claims
  that lagged the tree, and all seven are corrected here. The handoff and the
  roadmap no longer say `main` and `origin/main` are aligned at the tidy
  delivery's merge, and no longer describe the Phase 3 planning proposal as a
  later, separate delivery: that proposal has been delivered, and `main` now
  sits ahead of `origin/main` by the batched local documentation commits,
  unpushed and un-pull-requested by the owner's choice. The pointer labels
  above the corrected paragraphs are re-read to 2026-11-08.
- The roadmap's status line no longer says no board is open. `LC-P3-00`
  opened the board record; it authorises no implementation and dispatches
  nothing, which is what the rest of that line continues to say.
- `CONTRIBUTING.md` said six shards per platform, and that a push therefore
  starts twelve Python jobs. The workflow's matrix is the authority —
  `shard: [0, 1, 2, 3, 4]` — so the rule now says five shards and ten
  python jobs, matching `CLAUDE.md`, `.github/CI.md` and the repository
  map, all of which already said five.
- A further lag surfaced after the scan, from measuring the two things it
  had to leave open: the roadmap's live position stated
  `tests/test_no_reference_leakage.py` as `99 tests`, where `--collect-only`
  on this tree reports 110. The count is dropped rather than updated, because
  a collected number moves with every witness added and a live position is
  not where a run's number belongs; the figure stays in the dated records
  that measured it, where it is true of that commit. The other open item
  resolved the same way: `tests/test_ci_shard_coverage.py` passes 16 nodes
  here, since a change only forces a re-measurement when it could unbalance
  the partition.
- A post-repair re-scan found two further live lags, both corrected in the
  same batch. The changelog's own account of the shard rule used the test
  runner's name where `CONTRIBUTING.md` and `CLAUDE.md` say "ten python
  jobs"; the quotation — not the arithmetic — is corrected. The LC-P1-11
  and LC-P1-12 task breakdown's status line said four decisions in §1.4
  where the same file's §1.4 names five and the two other live pointers
  already say five; it now says five. The re-scan's third claim, that the
  A1/A6 labels have no in-tree definition, was refuted by `LC-P3-00` §7,
  which defines them, and nothing was changed for it.
- No merge identifier and no runner tally is written into these pointers: the
  A1/A6 ruling of 2026-11-07 keeps post-merge CI evidence operator-side. No
  dated snapshot is rewritten — one pre-existing malformed table row in the
  roadmap's 2026-11-05 historical section is left as landed and recorded
  outside the repository instead. No product source, test, workflow or
  migration file is changed; no push, PR or CI run is authorised.

### C4–C8 wording corrections (2026-11-08)

- The five wording and coverage judgements the freshness scan left to the
  owner are applied. `docs/README.md`'s current-phase row is dated
  (2026-11-07; re-read 2026-11-08) and no longer carries the batch ordinal;
  the same ordinal is removed from `docs/ROADMAP.md` and
  `docs/handoff/CURRENT.md`.
- The English and Chinese README banners now say the Phase 3 board is open
  (`LC-P3-00`, decisions of 2026-11-07), that implementation has not started,
  that no ticket is dispatched and no delivery is authorised, and point at
  the roadmap's current position.
- `docs/handoff/CURRENT.md` says "at the local commit of that date" instead
  of "at this local commit", so the 2026-11-06 WSL measurement no longer
  reads as a claim about the current tip.
- `CONTRIBUTING.md` no longer calls eleven commands "the README's command
  table": it names the ten fenced commands together with the
  `uv run labcairn --help` line as the eleven `VERIFIED_COMMANDS` entries.
- The upstream clone count paragraph now says five cloned projects, six
  clone directories (`paper-qa` is cloned twice), 139 files re-walked on
  2026-11-08, and three of the five projects ship 21, 22 and 26 `SKILL.md`
  files. The same correction is carried in `docs/UPSTREAM_REFERENCES.md`
  and `docs/REVIEW-DOSSIER.md`; the "22–26" range was wrong at 21.
- No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Eleventh-commit audit follow-ups (2026-11-08)

- The independent audit of `8aaea7b` found one live lag and two wording
  tails, all corrected here. `docs/UPSTREAM_REFERENCES.md` now says
  `Updated: 2026-11-08` and dates the 139-file walk in the sentence that
  carries it; `CONTRIBUTING.md` drops a redundant "each"; and the upstream
  checklist now says five cloned projects rather than five clones. No
  product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### P2-AMD-01 §10.5 pointer annotated (2026-11-08)

- `docs/plans/P2-AMD-01-provider-and-data-options.md` now says, in both
  places where it cites "the adjustment's §10.5", that §10.5 is the
  owner-side P2-AMD-01 adjustment of 2026-10-30 and that its four decisions
  are transcribed in `P2-AMD-01-impact-matrix.md` §5. The reference was
  correct but unnamed; the annotation makes the external owner-side section
  and the in-tree transcription distinguishable. No product source, test,
  workflow or migration file is changed; no push, PR or CI run is
  authorised.

### Rescan and rendering fixes (2026-11-08)

- The 13-commit live-pointer re-scan found six live lags. The mechanical
  ones are corrected here: `CONTRIBUTING.md` names the in-repo
  `scripts/witness_ledger.py`; `docs/ROADMAP.md` uses "at the local commit
  of that date" and limits its Phase 3 authorisation sentence to the
  2026-11-05 snapshot; the roadmap's current-direction label is dated
  2026-11-07; the LC-P1-11/12 task breakdown says "was then six shards".
- `README.md` and `README.zh-CN.md` no longer claim the two Chinese texts
  are identical; the standalone Chinese document is still the independent
  translation.
- `.github/CI.md`'s Ubuntu slow-file section is dated 2026-11-02 and its
  old anchor is described as "then the commit recorded" rather than as the
  current one.
- The merge-authority rule is made consistent: the producer-never-merges
  sentence in `docs/README.md` and `CONTRIBUTING.md` is marked historical
  (through 2026-10-24), and the executing-agent rule in `docs/README.md`
  remains current.
- `docs/ROADMAP.md`'s 2026-11-05 historical row is rejoined onto one
  physical line (content unchanged), because the seven-line form rendered
  as a broken table row.
- No product source, test, workflow or migration file is changed; no push,
  PR or CI run is authorised.

### Phase 3 G1 work orders issued (2026-11-08)

- [`docs/plans/PHASE_3-work-orders.md`](../plans/PHASE_3-work-orders.md) is the
  Phase 3 board's first work-order file: the official G1 work orders for
  **`LC-P3-01`** (real-browser baseline) and **`LC-P3-02`** (dual-host DOCX
  fidelity), written from the owner-approved preparation package. Both board
  rows read **`NOT STARTED`**. No implementation has begun, no window was
  opened, no witness ran, no real browser and no desktop host was started, and
  no Phase 3 gate is claimed closed.
- The owner's decisions of 2026-11-08 are recorded with them, each with where it
  binds: **Playwright** with the system-browser channel where one exists; **COM
  and ProgID automation not allowed**, so the WPS and Office reopen checks are
  human checklist steps with recorded evidence; the **real advisor sample after**
  the synthetic and substitute-first work, held as a named gap until it arrives;
  the **§4 checklist split** — `LC-P3-01` carries the real-browser baseline and
  the dual-host reopen checks, `LC-P3-02` the DOCX revision loop and the
  real-sample half; the **provider's seven fields after G1**, so `LC-P3-06` stays
  `BLOCKED`; the **write-seam path-length (MAX_PATH) repair rides this batch**;
  and **Q77 and Q82 stay at their triggers**.
- The file names the gate-label collision the tree needs: Phase 3's `G0` … `G4`
  are not Phase 1's five closed gates, and a row that says "G1" there means
  Phase 3 G1.
- Two items the preparation draft carried were corrected against this tree rather
  than copied. The "never `EventSource`" sentence belongs to
  `docs/THREAT-MODEL.md` **§6.2**, not §6.1; and the draft's raw-Windows
  long-path direction did not reproduce in its own freshness review, so the seam
  is stated through `src/labcairn/security/paths.py`'s deliberate refusal rather
  than as an errno.
- The current pointers move in the same commit: `docs/ROADMAP.md`,
  `docs/handoff/CURRENT.md`, `docs/README.md` and `docs/REPOSITORY-MAP.md`.
  `docs/README.md`'s status line no longer says that no work order exists, and
  the roadmap's `2026-11-07` direction row is now an earlier dated row.
- No product source, test, workflow or migration file is changed; no push, PR or
  CI run is authorised.

### G1 work-order audit corrections (2026-11-08)

- The independent audit of the G1 work orders found three structural gaps and
  two environment-fact errors. The work orders now name the commander as the
  owner of `.github/ci-shards.json` and `tests/evaluation/manifest.py` at merge
  (windows report their entries instead of editing those files), state at that
  date that the shard-balance witness is expected red until a runner supplies
  the costs (subsequently re-measured from runner run `42733499009`), require a
  browser witness to skip with a named reason when Playwright or a system
  browser is absent, and name the project owner as the human-checklist
  performer.
- The Chinese README status line now matches the English one: the two G1 work
  orders are issued and both read `NOT STARTED`.
- The operator-side environment preparation report records the corrected facts:
  `PLAYWRIGHT_BROWSERS_PATH` is User-scope only, the WPS App Paths read uses
  `HKCU`, and the project's uv cache is `E:\LabCairn\.local\uv-cache`.
- No product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### G1 work-order NOTE fixes (2026-11-08)

- The remaining G1 work-order audit NOTEs were triaged. The §4 checklist split
  is now labelled a re-decision, not a confirmation; a new product dependency
  is an owner decision (a window reports package, version, licence and
  lockfile change and does not edit the lockfiles); and the §4.8
  version-switch claim is recorded as a named gap — the workbench has no
  version-control surface, so task selection is what is witnessed. The
  baseline record and the §8 gap table carry the same statement.
- The operator-side environment preparation report reconciles the uv cache
  path with the project cache (`E:\LabCairn\.local\uv-cache`).
- The merge-time items (#6/#9/#11) and the dated notes (#1/#8) remain as the
  triage lists them.
- No product source, test, workflow or migration file is changed; no push, PR
  or CI run is authorised.

### Phase 3 G1 batch: LC-P3-01, the write seam and LC-P3-02 land locally (2026-11-08)

- `LC-P3-01`'s real-browser baseline merged locally; its row moved to
  `IN PROGRESS` in the merge commit and its record is
  [`docs/acceptance/LC-P3-01-browser-baseline.md`](../acceptance/LC-P3-01-browser-baseline.md).
- The write seam's path-length repair (the MAX_PATH batch item, §2 decision 6)
  merged locally, with its witness reading the product's own naming function.
- `LC-P3-02`'s DOCX editing seam merged locally: `src/labcairn/editing/`, the
  substitute corpus, the four test files and the helper
  `tests/evaluation_docx_edit_fidelity.py`; the editing ADR is
  [`docs/adr/ADR-0021-manuscript-editing-rewrite.md`](../adr/ADR-0021-manuscript-editing-rewrite.md)
  (`proposed`, adoption provisional), and the two dated records are
  [`docs/acceptance/LC-P3-02-support-matrix.md`](../acceptance/LC-P3-02-support-matrix.md)
  and [`docs/acceptance/LC-P3-02-substitute-run-2026-11-08.md`](../acceptance/LC-P3-02-substitute-run-2026-11-08.md).
  Both G1 rows read `IN PROGRESS`, and the live pointers moved in the same commit.
- What remained open at that date: the §4.9 human dual-host reopen checklist (`NOT RUN`
  in both records), the real advisor sample (§5.9), the ADR's final adoption, and the
  runner-measured shard costs — at that date locally `test_the_shards_are_balanced` and
  `test_the_recorded_costs_cover_every_test_file` were red by expectation (subsequently
  re-measured from runner run `42733499009`).
- No `PASS`, no gate closed, no ADR adopted, no push, pull request or CI run.

