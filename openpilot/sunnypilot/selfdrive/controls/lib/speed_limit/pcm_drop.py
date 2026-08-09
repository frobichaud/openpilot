"""Tesla PCM firmware speed-limit-drop guard.

On Tesla pcmCruise cars, v_cruise is owned by the car's firmware rather
than openpilot. The firmware autonomously drops the cruise set speed when
it misreads a speed sign (e.g. 110 -> 40 km/h from a truck-limit or exit
sign). Left alone, that drop propagates straight into the longitudinal
plan as a hard slowdown.

PcmDropDetector separates firmware drops from driver stalk presses:
stalk presses arrive as +/-5 kph steps; firmware drops are >=10 kph. A
7.5 kph threshold splits the two, and a countdown timer (rather than a
sticky flag) lets stalk presses resume working after the hold expires.
Gas or a cruise increase clears it immediately.

While the detector is active, the planner holds the Speed Limit Assist
resolved limit as a floor for the cruise target instead of the misread
firmware value. Other plan sources (SCC vision/map curve slowdowns, SLA
adapting) still win through the planner's min() arbitration.

Ported from FrogPilot frogpilot/controls/lib/tesla_pcm_cruise.py
(train/aug26).
"""
from openpilot.common.constants import CV

PCM_DROP_THRESHOLD = 7.5 * CV.KPH_TO_MS  # exceeds the 5 kph stalk step; catches >=10 kph firmware drops
PCM_DROP_HOLD_TIME = 15.0  # seconds to hold the SLA floor after a firmware drop


class PcmDropDetector:
  def __init__(self):
    self.timer = 0.0
    self.prev_v_cruise = 0.0

  @property
  def active(self) -> bool:
    return self.timer > 0

  def update(self, v_cruise: float, long_control_active: bool, gas_pressed: bool,
             sla_target: float, dt: float) -> bool:
    dropped = self.prev_v_cruise - v_cruise
    if long_control_active and dropped > PCM_DROP_THRESHOLD and not gas_pressed and sla_target > v_cruise:
      self.timer = PCM_DROP_HOLD_TIME
    elif gas_pressed or v_cruise > self.prev_v_cruise:
      self.timer = 0.0
    elif self.timer > 0:
      self.timer -= dt
    self.prev_v_cruise = v_cruise
    return self.active
