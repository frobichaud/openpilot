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

3. pcm_drop_floor — while a firmware drop is held, substitute the
   map-validated SLC speed (SLC target + offset, or the driver's SLC override)
   for the misread v_cruise. FrogPilotVCruise applies it *before* the Curve
   Speed Controller computes its target, so CSC caps at the restored speed and
   upstream's min(targets) arbitration does the rest.

   Ordering matters: on 2026-09-14 08:14 EDT the firmware misread a sign and
   dropped cruise 99->40 kph at ~85 kph while SLC held 90+10. The floor held
   for 10 s, then a curve activated CSC and the old min(csc_target, v_cruise)
   picked the 40 kph misread over the 84 kph curve target, braking at
   -2.3 m/s^2 instead of easing to ~72 kph.
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


def pcm_drop_floor(v_cruise: float, pcm_drop_active: bool, slc_target: float, slc_offset: float,
                   overridden_speed: float, v_ego_diff: float) -> float:
  """v_cruise with the SLC floor restored while a firmware sign-misread drop is held."""
  if pcm_drop_active and slc_target > 0:
    return max(v_cruise, max(overridden_speed, slc_target + slc_offset) - v_ego_diff)
  return v_cruise
