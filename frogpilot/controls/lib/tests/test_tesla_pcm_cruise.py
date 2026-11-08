#!/usr/bin/env python3
"""Tests for the Tesla PCM cruise logic in tesla_pcm_cruise.py: firmware
sign-reading drop detection, SLC stalk re-arm, and the PCM-drop floor as it
feeds FrogPilotVCruise's min(targets) arbitration."""
import unittest

from openpilot.common.constants import CV
from openpilot.frogpilot.controls.lib.tesla_pcm_cruise import (PCM_DROP_HOLD_TIME, PcmDropDetector,
                                                               pcm_drop_floor, slc_stalk_rearm)

DT = 0.05  # DT_MDL
CRUISING_SPEED = 5.0

KPH = CV.KPH_TO_MS
STALK_STEP = 5 * KPH      # driver stalk press
FIRMWARE_DROP = 10 * KPH  # Tesla sign-reading drop


class TestPcmDropDetector(unittest.TestCase):
  def setUp(self):
    self.det = PcmDropDetector()

  def prime(self, v_cruise, slc_target=0.0):
    # settle prev_v_cruise
    self.det.update(v_cruise, True, False, slc_target, DT)

  def test_firmware_drop_arms(self):
    self.prime(30.0, slc_target=30.0)
    self.assertTrue(self.det.update(30.0 - FIRMWARE_DROP, True, False, 30.0, DT))

  def test_stalk_step_does_not_arm(self):
    self.prime(30.0, slc_target=30.0)
    self.assertFalse(self.det.update(30.0 - STALK_STEP, True, False, 30.0, DT))

  def test_no_arm_when_gas_pressed(self):
    self.prime(30.0, slc_target=30.0)
    self.assertFalse(self.det.update(30.0 - FIRMWARE_DROP, True, True, 30.0, DT))

  def test_no_arm_when_slc_below_new_cruise(self):
    # drop landed above the SLC target: nothing to restore
    self.prime(30.0, slc_target=20.0)
    self.assertFalse(self.det.update(30.0 - FIRMWARE_DROP, True, False, 20.0, DT))

  def test_no_arm_when_long_control_inactive(self):
    self.prime(30.0, slc_target=30.0)
    self.assertFalse(self.det.update(30.0 - FIRMWARE_DROP, False, False, 30.0, DT))

  def test_hold_expires_after_timeout(self):
    self.prime(30.0, slc_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    self.assertTrue(self.det.update(v, True, False, 30.0, DT))
    steps = int(PCM_DROP_HOLD_TIME / DT)
    for _ in range(steps - 1):
      self.det.update(v, True, False, 30.0, DT)
    self.assertFalse(self.det.update(v, True, False, 30.0, DT))

  def test_gas_clears_immediately(self):
    self.prime(30.0, slc_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    self.assertTrue(self.det.update(v, True, False, 30.0, DT))
    self.assertFalse(self.det.update(v, True, True, 30.0, DT))

  def test_cruise_increase_clears_immediately(self):
    self.prime(30.0, slc_target=30.0)
    v = 30.0 - FIRMWARE_DROP
    self.assertTrue(self.det.update(v, True, False, 30.0, DT))
    self.assertFalse(self.det.update(v + STALK_STEP, True, False, 30.0, DT))


class TestSlcStalkRearm(unittest.TestCase):
  def test_rearms_above_ceiling(self):
    # driver stalks to 33 m/s while the SLC ceiling is 30: intentional override
    self.assertEqual(slc_stalk_rearm(0.0, 33.0, 0.5, 28.0, 2.0), 33.5)

  def test_no_rearm_when_already_overridden(self):
    self.assertEqual(slc_stalk_rearm(31.0, 33.0, 0.0, 28.0, 2.0), 31.0)

  def test_no_rearm_below_ceiling(self):
    self.assertEqual(slc_stalk_rearm(0.0, 25.0, 0.0, 28.0, 2.0), 0.0)

  def test_no_rearm_without_slc_target(self):
    # ceiling of 0 means SLC has no limit to override
    self.assertEqual(slc_stalk_rearm(0.0, 33.0, 0.0, 0.0, 0.0), 0.0)


def arbitrate(v_cruise=30.0, csc_target=None, slc_active=False, slc_target=0.0, slc_offset=0.0,
              overridden=0.0, v_ego_diff=0.0, pcm_drop=False):
  """Mirror of FrogPilotVCruise.update(): the PCM-drop floor is applied to v_cruise first,
  CSC computes its target from that (never above it), then min(targets)."""
  v_cruise = pcm_drop_floor(v_cruise, pcm_drop, slc_target, slc_offset, overridden, v_ego_diff)
  targets = [v_cruise]
  if csc_target is not None:
    targets.append(min(csc_target, v_cruise))
  if slc_active and slc_target > 0:
    targets.append(max(max(overridden, slc_target + slc_offset) - v_ego_diff, CRUISING_SPEED))
  return min(targets)


class TestPcmDropFloor(unittest.TestCase):
  def test_inactive_passes_through(self):
    self.assertEqual(pcm_drop_floor(20.0, False, 28.0, 0.0, 0.0, 0.0), 20.0)

  def test_no_slc_target_passes_through(self):
    self.assertEqual(pcm_drop_floor(20.0, True, 0.0, 0.0, 0.0, 0.0), 20.0)

  def test_restores_slc_target_plus_offset(self):
    self.assertEqual(pcm_drop_floor(20.0, True, 25.0, 3.0, 0.0, 0.0), 28.0)

  def test_override_wins_over_limit(self):
    self.assertEqual(pcm_drop_floor(20.0, True, 25.0, 0.0, 29.0, 0.0), 29.0)

  def test_never_lowers_v_cruise(self):
    self.assertEqual(pcm_drop_floor(30.0, True, 25.0, 0.0, 0.0, 0.0), 30.0)

  def test_v_ego_cluster_offset_applied(self):
    self.assertEqual(pcm_drop_floor(20.0, True, 25.0, 0.0, 0.0, 1.0), 24.0)


class TestArbitrationScenarios(unittest.TestCase):
  def test_csc_slows_for_curve(self):
    self.assertEqual(arbitrate(v_cruise=30.0, csc_target=20.0), 20.0)

  def test_csc_never_accelerates_above_v_cruise(self):
    self.assertEqual(arbitrate(v_cruise=30.0, csc_target=35.0), 30.0)

  def test_pcm_drop_restores_slc_floor(self):
    # firmware dropped v_cruise to 20 via a sign misread; SLC floor is 28
    self.assertEqual(arbitrate(v_cruise=20.0, slc_active=True, slc_target=28.0, pcm_drop=True), 28.0)

  def test_pcm_drop_floor_restored_without_slc_active(self):
    # show-speed-limits-only mode: slc_target set but SLC not enforcing
    self.assertEqual(arbitrate(v_cruise=20.0, slc_target=28.0, pcm_drop=True), 28.0)

  def test_pcm_drop_defers_to_csc_in_curve(self):
    self.assertEqual(arbitrate(v_cruise=20.0, csc_target=15.0, slc_active=True, slc_target=28.0, pcm_drop=True), 15.0)

  def test_pcm_drop_csc_caps_at_slc_floor_not_misread(self):
    # 2026-09-14 08:14 EDT drive: firmware misread dropped cruise 99->40 kph at
    # ~85 kph, SLC held 90 + 10 offset. A curve then activated CSC with an
    # 84 kph target. The car must ease toward 84, not brake for the 40 misread.
    got = arbitrate(v_cruise=40 * KPH, csc_target=84 * KPH, slc_active=True,
                    slc_target=90 * KPH, slc_offset=10 * KPH, pcm_drop=True)
    self.assertAlmostEqual(got, 84 * KPH)

  def test_pcm_drop_csc_still_capped_at_slc_floor(self):
    got = arbitrate(v_cruise=40 * KPH, csc_target=110 * KPH, slc_active=True,
                    slc_target=90 * KPH, slc_offset=10 * KPH, pcm_drop=True)
    self.assertAlmostEqual(got, 100 * KPH)

  def test_without_drop_misread_is_obeyed(self):
    # no drop detected (e.g. a stalk press): the lower cruise speed wins
    self.assertEqual(arbitrate(v_cruise=20.0, slc_active=True, slc_target=28.0), 20.0)


if __name__ == "__main__":
  unittest.main()
