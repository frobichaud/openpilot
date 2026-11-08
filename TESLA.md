# Tesla Legacy Support for FrogPilot on comma 3

**Branch:** `tesla-xnor-c3` (releases tagged `release/YYYY.MM`)
**Base:** FrogPilot `MAKE-PRS-HERE` (openpilot 0.10.3) + [xnor-tech/openpilot](https://github.com/xnor-tech/openpilot) Tesla legacy support
**Hardware:** comma 3 (internal `dos` panda) with the [xnor harness kit](https://github.com/xnor-tech/openpilot) (external black panda)
**Supported cars:** Tesla Model S and Model X (HW1, HW2, HW2.5, HW3)

---

## Overview

This branch adds Tesla Model S/X legacy support to FrogPilot on a comma 3. It builds on
[xnor-tech's](https://github.com/xnor-tech/openpilot) Tesla legacy CAN integration and adds
cooperative steering, Always On Lateral, and Tesla-aware Speed Limit Controller behavior aimed at
daily driving a pre-refresh Model S/X whose stock Autopilot (HW2/HW2.5) is aging.

Every custom change is one commit on top of upstream, listed below by subject. Commit messages end
with `Supersedes:` lines that map back to the original fix-by-fix history (kept under the
`release/2026.08` and `release/2026.09` tags).

---

## Feature commits

| # | Commit subject | What it does |
|---|----------------|--------------|
| 1 | Add Tesla Model S/X legacy (HW1/HW2/HW3) support for C3 with xnor kit | xnor platform: legacy carstate/controller, `tesla_legacy` safety mode, MG, black panda + Tesla CAN ignition in panda |
| 2 | Tesla HW2.5-as-HW3: read dashboard speed limit (AutopilotStatus) from vehicle bus | `DAS_fusedSpeedLimit` feeds SLC's "Dashboard" source |
| 3 | Tesla legacy: enable Always On Lateral | `acc_main_on` from `DI_cruiseState` in the legacy safety mode |
| 4 | Tesla legacy panda safety: broader stock-steering detection; hands_on_level no longer disengages | Block openpilot steering when the car steers; driver override handled in Python |
| 5 | Tesla legacy: cooperative steering | Driver steers through openpilot; release EPAS during override, blend back, ±20° clamp |
| 6 | Tesla: MAX_ANGLE_RATE = 3 deg/frame for smoother low-speed steering | Smoother angle rate limit |
| 7 | Tesla legacy: gas-override jerk ramp | No lurch when releasing the gas after an override |
| 8 | Tesla PCM cruise: hold the speed limit after firmware sign-misread drops | Prevents sudden braking when the car misreads a speed sign |
| 9 | Tesla SLC: adopt a confirmed higher speed limit on highway merge | Accelerates to the new limit after a ramp → highway merge |
| 10 | CI: tesla-xnor test workflow | Unit + panda safety tests on every push |
| 11 | Docs: Tesla legacy notes, fork badge, release runbook | This file, README badge, CLAUDE.md |

### Cooperative Steering
Tesla's EPAS faults (`EAC_INHIBITED`) when the driver fights a commanded angle. `CoopSteering`
(`opendbc/car/tesla/coopsteering.py`) detects driver override (2.0 Nm torque threshold plus
`hands_on_level`), releases EPAS (steer type NONE) and tracks the physical angle while the driver
steers, waits until desired and physical angles are within 15° to resume, then blends back over
~1.5 s. The commanded angle is never more than ±20° from the physical wheel angle. Upstream's
Always On Lateral `follow_driver` A/B test is bypassed on legacy cars. Tests:
`opendbc/car/tesla/tests/test_coopsteering.py`.

### Tesla PCM cruise (sudden speed drops)
On Tesla the car's firmware owns the cruise set speed and drops it on its own when it misreads a
speed sign (e.g. 110 → 40 km/h). `frogpilot/controls/lib/tesla_pcm_cruise.py`:
- `PcmDropDetector`: a >7.5 kph drop (stalk steps are 5 kph) while SLC is above the new speed holds
  the SLC speed for 15 s; gas or any cruise increase cancels.
- `pcm_drop_floor`: applied *before* the Curve Speed Controller so a curve slows toward the curve
  speed, not toward the misread (2026-09-14 regression).
- `slc_stalk_rearm`: stalking above the SLC ceiling re-arms the SLC override.
- `SlcAdopt`: after a confirmed higher limit (+>7.5 kph, e.g. ramp → highway), adopt it as a floor;
  cleared by gas, stalk, disengage or the limit dropping.

All gated on `car_make == "tesla"`. Tests: `frogpilot/controls/lib/tests/test_tesla_pcm_cruise.py`.

---

## CAN Bus Architecture (Tesla Legacy)

| Bus | Name | Description |
|-----|------|-------------|
| 0 | Party | Main bus — steering commands, vehicle controls |
| 1 | Vehicle | Vehicle status, DI_state, AutopilotStatus (msg 921) |
| 2 | Autopilot Party | Autopilot ECU messages (on some configurations) |
| 4 | Powertrain | Drive inverter, motor status |
| 5 | Chassis | DI_state, DI_torque2, gear, cruise state |
| 6 | Autopilot Powertrain | Autopilot powertrain messages |

**Note:** buses 4–7 come from the xnor kit's external black panda. HW1 cars remap powertrain (bus 4)
to party (bus 0). HW2.5 cars fingerprinting as HW3 broadcast `AutopilotStatus` on bus 1 instead of bus 2.

---

## Known Behaviors

- **Low-speed cooperative steering:** at very low speeds (parking lots, tight turns) the driver is
  constantly steering, so cooperative steering stays in override. This is expected.
- **AOL at standstill:** the brake + speed condition can flicker at the exact standstill boundary,
  briefly cycling AOL. Cosmetic.
- **HW2.5 fingerprinting:** HW2.5 cars may fingerprint as either `TESLA_MODEL_S_HW3` or
  `TESLA_MODEL_S_HW1` depending on firmware. The bus routing for `AutopilotStatus` adapts accordingly.
- **3-bit `DAS_steeringControlType` (firmware 2026.8.6+):** upstream notes Tesla widened this field on
  HW2.5/HW3 around 2026-04. The legacy safety mode still reads it as 2 bits (`>> 6`); stock
  ANGLE_CONTROL (Autopark/Summon) would read as NONE on the new layout. LKAS/FSD still detect.

---

## Credits

- **[BogGyver](https://github.com/BogGyver)** — Pioneer of openpilot on Tesla, early Tesla integration work that paved the way for community support
- **[xnor-tech](https://github.com/xnor-tech/openpilot)** ([lukasloetkolben](https://github.com/lukasloetkolben)) — Tesla Model S/X legacy platform support, harness kit design, safety mode implementation, and dedicated ongoing work to support Tesla in upstream openpilot branches
- **[dzfrog](https://github.com/dzfrog)** — Virtual Torque Blending (VTB) approach and steering override research
- **[FrogAi/FrogPilot](https://github.com/FrogAi/FrogPilot)** — Base fork with AOL, SLC, CEM, and extensive customization framework
- **[comma.ai](https://github.com/commaai/openpilot)** — openpilot core
