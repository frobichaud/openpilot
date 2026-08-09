"""Pure logic for FrogPilot's Tesla PCM cruise interactions, extracted from
frogpilot_vcruise.py so it can be unit tested without the openpilot runtime.

Three behaviors, all specific to Tesla pcmCruise where v_cruise is owned by
the car's firmware rather than openpilot:

1. PcmDropDetector — Tesla firmware autonomously drops cruise speed when it
   misreads a speed sign. Stalk presses arrive as +/-5 kph steps; firmware
   drops are >=10 kph. A 7.5 kph threshold separates the two, and a countdown
   timer (rather than a sticky flag) lets stalk presses resume working after
   the hold expires. Gas or a cruise increase clears it immediately.

2. slc_stalk_rearm — on pcmCruise, v_cruise only changes via stalk or
   firmware, so an increase above the SLC ceiling is always an intentional
   driver action and re-arms the SLC override. Without this, stalking down
   below the ceiling kills the override and stalking back up gets stuck at
   the ceiling until gas is pressed.

3. resolve_cruise_target — final target arbitration: CSC capped at v_cruise
   (never accelerate for a "curve"), SLC floor/override application with the
   cluster-speed offset, sub-cruising-speed fallback, and the PCM-drop floor
   restore (hold the map-validated SLC speed instead of the sign misread,
   unless CSC is actively slowing for a curve).
"""
from openpilot.common.constants import CV

PCM_DROP_THRESHOLD = 7.5 * CV.KPH_TO_MS  # exceeds the 5 kph stalk step; catches >=10 kph firmware drops
PCM_DROP_HOLD_TIME = 15.0  # seconds to hold the SLC floor after a firmware drop


class PcmDropDetector:
  def __init__(self):
    self.timer = 0.0
    self.prev_v_cruise = 0.0

  @property
  def active(self) -> bool:
    return self.timer > 0

  def update(self, v_cruise: float, long_control_active: bool, gas_pressed: bool,
             slc_target: float, dt: float) -> bool:
    dropped = self.prev_v_cruise - v_cruise
    if long_control_active and dropped > PCM_DROP_THRESHOLD and not gas_pressed and slc_target > v_cruise:
      self.timer = PCM_DROP_HOLD_TIME
    elif gas_pressed or v_cruise > self.prev_v_cruise:
      self.timer = 0.0
    elif self.timer > 0:
      self.timer -= dt
    self.prev_v_cruise = v_cruise
    return self.active


def slc_stalk_rearm(overridden_speed: float, v_cruise: float, v_cruise_diff: float,
                    slc_target: float, slc_offset: float) -> float:
  """Return the (possibly re-armed) SLC overridden speed."""
  if overridden_speed == 0 and v_cruise > slc_target + slc_offset > 0:
    return v_cruise + v_cruise_diff
  return overridden_speed


def resolve_cruise_target(v_cruise: float, csc_target: float, slc_active: bool,
                          slc_target: float, slc_offset: float, overridden_speed: float,
                          v_ego_diff: float, pcm_drop_active: bool, csc_controlling: bool,
                          cruising_speed: float) -> float:
  """Arbitrate the final cruise target from CSC, SLC, and the PCM-drop floor."""
  targets = [min(csc_target, v_cruise)]
  if slc_active and slc_target > 0:
    targets.append(max(overridden_speed, slc_target + slc_offset) - v_ego_diff)
  else:
    targets.append(v_cruise)
  v_cruise = min([target if target >= cruising_speed else v_cruise for target in targets])

  if pcm_drop_active and slc_target > 0 and not csc_controlling:
    slc_floor = max(overridden_speed, slc_target + slc_offset) - v_ego_diff
    v_cruise = max(v_cruise, slc_floor)

  return v_cruise
