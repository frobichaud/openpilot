# frobichaud/openpilot — fork notes for Claude Code

This is `frobichaud/openpilot` (`origin`), a fork of FrogAi/FrogPilot (`frogpilot` remote),
running on a **comma 3** (internal `dos` panda, STM32F4) + xnor kit (external black panda, F4)
in a legacy Tesla Model S (HW2.5, fingerprints as `TESLA_MODEL_S_HW3`). AGNOS 12.8.
Other remotes: `comma` (commaai/openpilot), `xnor` (xnor-tech/openpilot).

Hardware constraint: comma dropped comma 3 support upstream (commaai/openpilot #36078) and panda
master dropped F4. sunnypilot `master` (AGNOS 19.x) cannot run on this device; only its frozen
`master-tici` (v0.10.1) could. FrogPilot keeps comma 3 on AGNOS 12.8 (`launch_env.sh` checks the
device model). Never move this device to a newer AGNOS.

FrogAi force-pushes squashed, themed commits and regularly rewrites history, so this fork never
rebases onto upstream — it rebuilds a curated train of feature commits each release.

## Upstream branches (FrogAi/FrogPilot)

- `MAKE-PRS-HERE` — 0.10.3 development line, daily "Month Nth Update" commits. **Our base.**
  (Replaced `FrogPilot-Development`, which no longer exists.)
- `FrogPilot` / `FrogPilot-Staging` — stable release, still openpilot 0.9.7.
- `FrogPilot-Testing` — prebuilt 0.10.3 test branch (per-feature commits, force-pushed).
- `FrogPilot-Old` / `-Previous` — rollback snapshots; `-Screen-Fix` / `-GM-CSLC` — hotfix variants.

## Branch and tag model

- `tesla-xnor-c3` — the only long-lived branch; the device installs from it. Each release rebuilds
  it on new upstream and force-pushes (FrogPilot's updater resets hard to the remote).
- `wip/YYYY.MM` — local/pushed candidate while building a release.
- Tags (immutable):
  - `upstream/frogpilot-mprs-YYYYMMDD` — upstream base of a release. The train is `upstream/...^{}..release/...`.
  - `release/YYYY.MM` — shipped tip. Rollback:
    `git push -f origin release/<prev>:refs/heads/tesla-xnor-c3`
  - `archive/*` — tips of deleted branches; `upstream/frogpilot-dev-*` — old Development snapshots.
  - `release/2026.08`, `release/2026.09` hold the old fix-by-fix history (47 commits).

## The curated train

One commit per feature, in this order (subjects are stable; see TESLA.md for details). Each message
ends with `Supersedes: <old shas>`.

1. Add Tesla Model S/X legacy (HW1/HW2/HW3) support for C3 with xnor kit
2. Tesla HW2.5-as-HW3: read dashboard speed limit (AutopilotStatus) from vehicle bus
3. Tesla legacy: enable Always On Lateral
4. Tesla legacy panda safety: broader stock-steering detection; hands_on_level no longer disengages
5. Tesla legacy: cooperative steering
6. Tesla: MAX_ANGLE_RATE = 3 deg/frame for smoother low-speed steering
7. Tesla legacy: gas-override jerk ramp
8. Tesla PCM cruise: hold the speed limit after firmware sign-misread drops
9. Tesla SLC: adopt a confirmed higher speed limit on highway merge
10. CI: tesla-xnor test workflow
11. Docs: Tesla legacy notes, fork badge, release runbook

Rules when resolving conflicts:
- Modern Model 3/Y code (`tesla.h`, `TeslaCAN`, `CarState.update()`) → take upstream. Our changes
  live in the legacy paths (`tesla_legacy.h`, `TeslaCANRaven`, `update_legacy()`, `LEGACY_CARS`).
- Legacy CarState fills the shared `self.fp_ret` and returns `ret` only; `CarController.update(CC, CS, now_nanos)`.
- Tesla planner logic is gated on `frogpilot_toggles.car_make == "tesla"` in `frogpilot_vcruise.py`
  and must run *before* the Curve Speed Controller (see `tesla_pcm_cruise.py` docstring).
- Invariant: the SpeedLimits filler dataset must stay ≤ 50_000 entries (a 1M cap blew out the 150MB
  /tmp tmpfs and spiked RAM to 91% on the C3). Upstream's `frogpilot/controls/lib/speed_limit_filler.py`
  now caps at `MAX_SHARED_SPEED_LIMITS = 25000` — check it on every release.

Set aside (not in the train): Autosteer-profile auto-pause + HW2.5 DAS_settings guard (HW2.5 does
not broadcast DAS_settings, so it never triggers; would add a capnp field) — on `archive/tesla-xnor-vtb-dev`.
Dropped: summon rename, Model 3/Y-only carstate tweaks, periodic debug cloudlog lines, the 50K
filler cap commit (upstream rewrote the filler).

## Release sequence ("create a new FrogPilot release with my Tesla changes")

1. `git fetch frogpilot --prune && git fetch origin`
2. `D=$(date +%Y%m%d); git tag upstream/frogpilot-mprs-$D frogpilot/MAKE-PRS-HERE`
3. `git checkout -b wip/YYYY.MM upstream/frogpilot-mprs-$D`
4. Rebuild the train: for each commit of the previous release
   (`git log --reverse --format=%H upstream/<prev-base>..release/<prev>`), `git cherry-pick` it and
   resolve per the rules above. Keep one commit per feature; fold fixes into their feature commit.
5. Sanity checks:
   - `python3 -m py_compile` the touched Python files; `uvx ruff check --select F <files>`.
   - Tests (zeromq: `brew install zeromq`, CPATH=/opt/homebrew/include):
     `uv run scons -j8 common/params_pyx.so`
     `cd opendbc_repo && uv run --project .. scons -j8 opendbc/safety/tests/libsafety/`
     `uv run --project .. --with parameterized python -m unittest opendbc.car.tesla.tests.test_coopsteering opendbc.car.tesla.tests.test_longcontrol opendbc.safety.tests.test_tesla opendbc.safety.tests.test_tesla_hw23 opendbc.safety.tests.test_tesla_hw1 opendbc.safety.tests.test_mg`
     `uv run python -m unittest openpilot.frogpilot.controls.lib.tests.test_tesla_pcm_cruise` (repo root)
   - `git diff release/<prev> HEAD -- opendbc_repo/opendbc/car/tesla/coopsteering.py opendbc_repo/opendbc/car/tesla/longcontrol.py opendbc_repo/opendbc/safety/modes/tesla_legacy.h frogpilot/controls/lib/tesla_pcm_cruise.py`
     should be empty or intentional.
6. Push the candidate: `git push origin wip/YYYY.MM` (CI runs on `wip/*`). Check with
   `gh run list --repo frobichaud/openpilot --workflow "tesla-xnor tests"`.
7. Ship: `git push -f origin wip/YYYY.MM:refs/heads/tesla-xnor-c3`, test-drive, then
   `git tag release/YYYY.MM && git push origin release/YYYY.MM upstream/frogpilot-mprs-$D`.

Drive checklist: cooperative steering override + resume blend; PCM sign-misread drop held at the
SLC limit; ramp → highway auto-adopt and stalk cancel; curve during a held drop; AOL through cruise
flicker; dashboard speed limit source shows "Dashboard".
