#!/usr/bin/env python3
"""Tests for the Tesla PCM cruise logic extracted into tesla_pcm_cruise.py:
firmware sign-reading drop detection, SLC stalk re-arm, and final cruise
target arbitration (CSC cap, SLC floor, PCM-drop restore)."""
import unittest

from openpilot.common.constants import CV
from openpilot.frogpilot.controls.lib.tesla_pcm_cruise import (PCM_DROP_HOLD_TIME, PcmDropDetector,
                                                               resolve_cruise_target, slc_stalk_rearm)

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


class TestResolveCruiseTarget(unittest.TestCase):
  def resolve(self, v_cruise=30.0, csc_target=30.0, slc_active=False, slc_target=0.0,
              slc_offset=0.0, overridden=0.0, v_ego_diff=0.0, pcm_drop=False,
              csc_controlling=False):
    return resolve_cruise_target(v_cruise, csc_target, slc_active, slc_target, slc_offset,
                                 overridden, v_ego_diff, pcm_drop, csc_controlling,
                                 CRUISING_SPEED)

  def test_csc_slows_for_curve(self):
    self.assertEqual(self.resolve(v_cruise=30.0, csc_target=20.0, csc_controlling=True), 20.0)

  def test_csc_target_ignored_when_not_controlling(self):
    # planner passes v_cruise through csc_target when CSC is idle; a stale
    # lower value must not leak into the target
    self.assertEqual(self.resolve(v_cruise=30.0, csc_target=20.0, csc_controlling=False), 30.0)

  def test_csc_capped_at_v_cruise(self):
    # CSC must never accelerate above the driver's set speed
    self.assertEqual(self.resolve(v_cruise=30.0, csc_target=35.0), 30.0)

  def test_slc_lowers_target(self):
    self.assertEqual(self.resolve(v_cruise=30.0, slc_active=True, slc_target=25.0), 25.0)

  def test_slc_override_wins_over_limit(self):
    got = self.resolve(v_cruise=30.0, slc_active=True, slc_target=25.0, overridden=28.0)
    self.assertEqual(got, 28.0)

  def test_sub_cruising_speed_target_falls_back(self):
    # a bogus 1 m/s "limit" must not stall the car; fall back to v_cruise
    self.assertEqual(self.resolve(v_cruise=30.0, slc_active=True, slc_target=1.0), 30.0)

  def test_pcm_drop_restores_slc_floor(self):
    # firmware dropped v_cruise to 20 via a sign misread; SLC floor is 28
    got = self.resolve(v_cruise=20.0, csc_target=20.0, slc_active=True,
                       slc_target=28.0, pcm_drop=True)
    self.assertEqual(got, 28.0)

  def test_pcm_drop_defers_to_csc_in_curve(self):
    # CSC actively slowing for a curve outranks the drop restore
    got = self.resolve(v_cruise=20.0, csc_target=15.0, slc_active=True,
                       slc_target=28.0, pcm_drop=True, csc_controlling=True)
    self.assertEqual(got, 15.0)

  def test_pcm_drop_csc_caps_at_slc_floor_not_misread(self):
    # 2026-09-14 08:14 EDT drive: firmware misread dropped cruise 99->40 kph at
    # ~85 kph, SLC held 90 + 10 offset. A curve then activated CSC with an
    # 84 kph target. The car must ease toward 84, not brake for the 40 misread.
    got = self.resolve(v_cruise=40 * KPH, csc_target=84 * KPH, slc_active=True,
                       slc_target=90 * KPH, slc_offset=10 * KPH, pcm_drop=True,
                       csc_controlling=True)
    self.assertAlmostEqual(got, 84 * KPH)

  def test_pcm_drop_csc_still_capped_at_slc_floor(self):
    # CSC target above the held floor: never accelerate past the floor
    got = self.resolve(v_cruise=40 * KPH, csc_target=110 * KPH, slc_active=True,
                       slc_target=90 * KPH, slc_offset=10 * KPH, pcm_drop=True,
                       csc_controlling=True)
    self.assertAlmostEqual(got, 100 * KPH)

  def test_pcm_drop_floor_restored_without_slc_active(self):
    # show-speed-limits-only mode: slc_target set but SLC not enforcing
    got = self.resolve(v_cruise=20.0, csc_target=20.0, slc_active=False,
                       slc_target=28.0, pcm_drop=True)
    self.assertEqual(got, 28.0)

  def test_v_ego_cluster_offset_applied(self):
    got = self.resolve(v_cruise=30.0, slc_active=True, slc_target=25.0, v_ego_diff=1.0)
    self.assertEqual(got, 24.0)


if __name__ == "__main__":
  unittest.main()
