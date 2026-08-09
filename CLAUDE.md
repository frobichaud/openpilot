# frobichaud/openpilot — tesla-xnor-sunny (sunnypilot base)

This branch is `frobichaud/openpilot:tesla-xnor-sunny`, based on
**sunnypilot/sunnypilot master**, for a comma C3 + xnor kit in a legacy Tesla
Model S (HW2.5, fingerprints as HW3, external F4 panda over USB).

Unlike the FrogPilot-lineage branches (`tesla-xnor-c3-dev-<monYY>`, which need a
monthly cherry-pick train because FrogAi force-push-nukes history), sunnypilot
keeps real history. **Syncing here is a normal rebase — no cherry-pick train.**

## Submodule fork layout

| Submodule     | Fork                 | Branch             | Local clone                       |
|---------------|----------------------|--------------------|-----------------------------------|
| `opendbc_repo`| frobichaud/opendbc   | `tesla-sunny-xnor` | /Users/francis/code/opendbc-sunny |
| `panda`       | frobichaud/panda     | `tesla-sunny-xnor` | /Users/francis/code/panda-sunny   |

Remote map used in each clone: `origin` -> frobichaud fork,
`sunnypilot`/`sunny` -> sunnypilot upstream, `xnor` -> xnor-tech, `comma` -> commaai.

## IMPORTANT: check the xnor-tech community fork on EVERY sync

The Tesla legacy (HW1/HW2/HW3) port and external-panda support are maintained by
**lukasloetkolben** on the xnor-tech forks. Before/during every sync, fetch and
inspect ALL THREE for new Tesla-compatibility / API-matching commits:

1. **xnor-tech/opendbc, branch `master-xnor`** — car port, safety, fw query
   (comma-based, NOT sunnypilot-based: cherry-pick and adapt, don't merge).
2. **xnor-tech/openpilot** — openpilot-side glue. Their work lives on branch
   **`xnor-dev`** (their `master` is just a mirror of commaai master — diff
   `comma/master..xnor/xnor-dev` to find the unique commits).
3. **xnor-tech/panda, branch `master-xnor`** — F4 panda device types, ignition.

Their commits target commaai upstream, so adapt to sunnypilot (paths under the
nested `openpilot/` dir, CarParamsSP/CarStateSP, MADS) rather than importing
wholesale.

## Sync routine

openpilot (this repo):
1. `git fetch sunnypilot` (https://github.com/sunnypilot/sunnypilot.git) + `git fetch xnor`
2. Check xnor-dev for new commits (see above).
3. `git rebase sunnypilot/master tesla-xnor-sunny` — our commits are few and real:
   the xnor pandad USB/multi-panda re-add, ubsan flag, system libusb, .gitmodules
   fork URLs, Darwin Homebrew SConstruct fix, num_pandas in card.py, the SLA
   PCM-drop guard, and submodule bumps. Drop any commit upstream has absorbed
   (e.g. the MADS-heartbeat fix and the pandad compile fixes died in the 2026-08 rebase
   because sunnypilot upstreamed equivalents).
   Watch for upstream refactors that moved code we patch:
   - comma removed pandad USB/multi-panda support (we re-add it; conflicts land in
     `openpilot/selfdrive/pandad/`) — keep multi-panda but fold in sunnypilot's
     MADS heartbeat (`process_mads_heartbeat`), `always_offroad`, CarParamsSP safety.
   - CAN ignition hooks moved from panda `board/drivers/can_common.h` to
     **opendbc** `opendbc/safety/ignition.h` (Tesla legacy GTW_status 0x348 hook
     lives in our opendbc fork now).
4. Rebase opendbc and panda forks onto their sunnypilot masters (normal rebases,
   `--force-with-lease` push), then bump both submodule pointers here in one commit.
5. Pushing this repo to origin: `.lfsconfig` points LFS at sunnypilot's GitLab,
   which we cannot push to (and don't need to — all LFS objects are upstream's;
   never add new LFS-tracked files here). Push with:
   `GIT_LFS_SKIP_PUSH=1 git push --force-with-lease origin tesla-xnor-sunny`

## Tests

opendbc (run in /Users/francis/code/opendbc-sunny):

    uv run python -m unittest \
      opendbc.car.tesla.tests.test_coopsteering \
      opendbc.car.tesla.tests.test_longcontrol \
      opendbc.safety.tests.test_tesla \
      opendbc.safety.tests.test_tesla_hw23 \
      opendbc.safety.tests.test_tesla_hw1 \
      opendbc.safety.tests.test_mg

(libsafety self-builds via cffi on import; no scons step needed.)

openpilot (this repo): build first on macOS —
`CPATH=/opt/homebrew/include uv run scons -j$(nproc)` (zmq lives in Homebrew;
the Darwin SConstruct commit adds the brew prefix for libusb) — then:

    uv run pytest openpilot/sunnypilot/selfdrive/controls/lib/speed_limit/tests/test_pcm_drop.py

## Tesla-specific behavior carried on these branches

- **Coop steering / jerk ramp / MAX_ANGLE_RATE=3** — opendbc fork
  (`opendbc/car/tesla/`, `coopsteering.py`, `longcontrol.py`, safety in
  `opendbc/safety/modes/tesla_legacy.h`). Behavior pinned by test_coopsteering /
  test_longcontrol; change the extracted modules, not inline logic.
- **Dashboard speed limit → SLA** — opendbc fork feeds AutopilotStatus (msg 921)
  `DAS_fusedSpeedLimit` into `CarStateSP.speedLimit` (legacy path in
  `opendbc/car/tesla/carstate.py`); sunnypilot's SpeedLimitResolver mixes it as
  the `car` source with OSM/mapd per the `SpeedLimitPolicy` param.
- **PCM firmware-drop guard** (prevents 110→40 km/h sign-misread slowdowns) —
  `openpilot/sunnypilot/selfdrive/controls/lib/speed_limit/pcm_drop.py`, wired in
  `openpilot/sunnypilot/selfdrive/controls/lib/longitudinal_planner.py`
  (ported from FrogPilot train/aug26 `tesla_pcm_cruise.py`).
- **Tesla legacy ignition** — GTW_status (0x348) hook in opendbc
  `opendbc/safety/ignition.h` (tested by TestTeslaLegacyIgnition in test_tesla_hw23).
- **Deliberately NOT ported from FrogPilot**: force stops, traffic mode, accel
  personality profiles, themes, screen recorder / shutdown timer / low-voltage /
  delete-data device extras.

## Relationship to the FrogPilot branches

The FrogPilot-lineage runbook (cherry-pick train, `train/<monYY>` tags) lives in
CLAUDE.md on the `tesla-xnor-c3-dev-<monYY>` branches. Migrating the car to this
branch requires newer AGNOS and is effectively one-way.
