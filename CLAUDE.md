# frobichaud/openpilot — fork notes for Claude Code

This is `frobichaud/openpilot` (`origin`), a fork of FrogAi/FrogPilot (`frogpilot` remote),
running on a comma C3 + xnor kit in a legacy Tesla Model S (HW2.5, fingerprints as HW3).
Other remotes: `comma` (commaai/openpilot), `xnor` (xnor-tech/openpilot).

FrogAi force-pushes squashed, themed commits and regularly nukes upstream history, so this
fork never rebases onto upstream — it re-applies a portable cherry-pick train each release.

## The Tesla commit train

All custom work is a contiguous block of commits authored by Francis Robichaud, always
beginning with the subject:

    Add Tesla Model S/X legacy (HW1/HW2/HW3) support for C3 with xnor kit

The tip of the current train is tagged `train/<monYY>` (e.g. `train/aug26`).

## Monthly release sequence ("create a new FrogPilot branch with my Tesla changes")

1. `git fetch frogpilot --prune`
2. Snapshot upstream before it gets nuked (push tags at the end):
   `git tag upstream/frogpilot-dev-$(date +%Y%m%d) frogpilot/FrogPilot-Development`
3. `git checkout -b tesla-xnor-c3-dev-<monYY> frogpilot/FrogPilot-Development`
4. Locate the train start on the previous release (PREV = previous train tag):
   `FIRST=$(git log --format="%H %s" train/<PREV> | grep -m1 "Add Tesla Model S/X legacy" | cut -d" " -f1)`
5. `git cherry-pick --empty=drop $FIRST^..train/<PREV>`
6. Resolve conflicts in favor of our values when upstream renames/moves things.
   Known invariant: the SpeedLimits dataset cap in `frogpilot/system/speed_limit_filler.py`
   must stay `50_000` (a 1M cap blew out the 150MB /tmp tmpfs and spiked RAM to 91% on the C3).
7. Sanity checks:
   - `git diff --stat train/<PREV> HEAD -- opendbc_repo/opendbc/car/tesla opendbc_repo/opendbc/safety panda/`
     should be near-empty (only legitimate upstream drift).
   - `python3 -m py_compile` the touched Python files.
   - Verify no unique commit subjects were dropped:
     `comm -23 <(git log --format=%s $FIRST^..train/<PREV> | sort -u) <(git log --format=%s frogpilot/FrogPilot-Development..HEAD | sort -u)`
   - Run the Tesla test suites locally (same as CI):
     `uv run scons -j8 common/params_pyx.so` (needs zeromq: `brew install zeromq`, CPATH=/opt/homebrew/include)
     `cd opendbc_repo && uv run --project .. scons -j8 opendbc/safety/tests/libsafety/`
     `uv run --project .. python -m unittest opendbc.car.tesla.tests.test_coopsteering opendbc.car.tesla.tests.test_longcontrol opendbc.safety.tests.test_tesla opendbc.safety.tests.test_tesla_hw23 opendbc.safety.tests.test_tesla_hw1 opendbc.safety.tests.test_mg`
     `uv run python -m unittest openpilot.frogpilot.controls.lib.tests.test_tesla_pcm_cruise` (from repo root)
   - CI: pushing any `tesla-xnor-*` branch runs `.github/workflows/tesla_xnor_tests.yaml`
     (coop steering tests + the four panda safety suites). Check with
     `gh run list --repo frobichaud/openpilot --workflow "tesla-xnor tests"`.
8. Tag the new tip `train/<monYY>`, then push branch and tags to `origin`.
9. Optionally update the fork's default branch:
   `gh api -X PATCH repos/frobichaud/openpilot -f default_branch=tesla-xnor-c3-dev-<monYY>`
10. Keep the previous release branch until the new one is validated on the car, then
    archive-tag it (`archive/<branch>`) and delete it.

## Branch map

- `tesla-xnor-c3-dev-<monYY>` — monthly releases; the device installs from origin
- `tesla-xnor-vtb-dev` — unmerged extras (HW2.5 DAS_settings guards, Autosteer-profile
  auto-pause, summon rename); cherry-pick candidates for a future train
- `feature/slc-auto-adopt-on-merge` — unmerged SLC highway-merge auto-adopt feature
- `tesla-xnor-sunny` — sunnypilot base experiment (panda/opendbc submodules point at
  frobichaud forks); requires newer AGNOS, effectively one-way from FrogPilot
- `archive/*` tags — tips of deleted branches; `upstream/*` tags — upstream snapshots
