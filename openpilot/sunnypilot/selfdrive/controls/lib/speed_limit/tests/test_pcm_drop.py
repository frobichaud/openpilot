"""Tests for the Tesla PCM firmware speed-limit-drop guard (pcm_drop.py).

Ported from FrogPilot frogpilot/controls/lib/tests/test_tesla_pcm_cruise.py
(train/aug26), TestPcmDropDetector.
"""
from openpilot.common.constants import CV
from openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.pcm_drop import PCM_DROP_HOLD_TIME, PcmDropDetector

DT = 0.05  # DT_MDL

KPH = CV.KPH_TO_MS
STALK_STEP = 5 * KPH      # driver stalk press
FIRMWARE_DROP = 10 * KPH  # Tesla sign-reading drop


class TestPcmDropDetector:
  def setup_method(self):
    self.det = PcmDropDetector()

  def prime(self, v_cruise, sla_target=0.0):
    # settle prev_v_cruise
    self.det.update(v_cruise, True, False, sla_target, DT)

  def test_firmware_drop_arms(self):
    self.prime(30.0, sla_target=30.0)
    assert self.det.update(30.0 - FIRMWARE_DROP, True, False, 30.0, DT)

  def test_stalk_step_does_not_arm(self):
    self.prime(30.0, sla_target=30.0)
    assert not self.det.update(30.0 - STALK_STEP, True, False, 30.0, DT)

  def test_no_arm_when_gas_pressed(self):
    self.prime(30.0, sla_target=30.0)
    assert not self.det.update(30.0 - FIRMWARE_DROP, True, True, 30.0, DT)

  def test_no_arm_when_sla_below_new_cruise(self):
    # drop landed above the SLA target: nothing to restore
    self.prime(30.0, sla_target=20.0)
    assert not self.det.update(30.0 - FIRMWARE_DROP, True, False, 20.0, DT)

  def test_no_arm_when_long_control_inactive(self):
    self.prime(30.0, sla_target=30.0)
    assert not self.det.update(30.0 - FIRMWARE_DROP, False, False, 30.0, DT)

  def test_hold_expires_after_timeout(self):
    self.prime(30.0, sla_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    assert self.det.update(v, True, False, 30.0, DT)
    steps = int(PCM_DROP_HOLD_TIME / DT)
    for _ in range(steps - 1):
      self.det.update(v, True, False, 30.0, DT)
    assert not self.det.update(v, True, False, 30.0, DT)

  def test_gas_clears_immediately(self):
    self.prime(30.0, sla_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    assert self.det.update(v, True, False, 30.0, DT)
    assert not self.det.update(v, True, True, 30.0, DT)

  def test_cruise_increase_clears_immediately(self):
    self.prime(30.0, sla_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    assert self.det.update(v, True, False, 30.0, DT)
    assert not self.det.update(v + STALK_STEP, True, False, 30.0, DT)
