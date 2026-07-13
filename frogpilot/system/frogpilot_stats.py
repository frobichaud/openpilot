import requests

from cereal import car, custom

from openpilot.frogpilot.common import frogpilot_utilities, frogpilot_variables
from openpilot.frogpilot.system.location_lookup import LOCATION_UNAVAILABLE, get_city_center


STATS_PAYLOAD_SCHEMA_VERSION = 1


def get_car_params(params):
  msg_bytes = params.get("CarParamsPersistent")
  if not msg_bytes:
    return {}

  with car.CarParams.from_bytes(msg_bytes) as CP:
    car_params = CP.to_dict()

  car_params.pop("carFw", None)
  car_params.pop("carVin", None)
  return car_params


def get_frogpilot_car_params(params):
  msg_bytes = params.get("FrogPilotCarParamsPersistent")
  if not msg_bytes:
    return {}

  with custom.FrogPilotCarParams.from_bytes(msg_bytes) as FPCP:
    return FPCP.to_dict()


def get_model_scores(params):
  model_scores = []

  for model_name, model_data in sorted((params.get("ModelDrivesAndScores") or {}).items()):
    drives = int(model_data.get("Drives", 0) or 0)
    if drives <= 0:
      continue

    model_scores.append({
      "drives": drives,
      "model_name": frogpilot_utilities.clean_model_name(model_name),
      "score": int(model_data.get("Score", 0) or 0),
    })

  return model_scores


def send_stats(gps_position, params, frogpilot_toggles):
  if not frogpilot_toggles.frogpilot_telemetry:
    return

  if frogpilot_toggles.car_make == "mock":
    return

  api_info = frogpilot_utilities.get_frogpilot_api_info()
  if not api_info.api_token or not api_info.dongle_id:
    return

  city, state, country = LOCATION_UNAVAILABLE
  if isinstance(gps_position, dict):
    city, state, country = get_city_center(gps_position.get("latitude", 0.0), gps_position.get("longitude", 0.0))

  using_default_model = (params.get("DrivingModel") or "").endswith("_default")

  payload = {
    "api_token": api_info.api_token,
    "build_metadata": api_info.build_metadata,
    "device": api_info.device_type,
    "frogpilot_dongle_id": api_info.dongle_id,
    "model_scores": get_model_scores(params),
    "os_version": api_info.os_version,
    "stats_schema_version": STATS_PAYLOAD_SCHEMA_VERSION,
    "user_stats": {
      "calibrated_lateral_acceleration": params.get("CalibratedLateralAcceleration"),
      "car_params": get_car_params(params),
      "city": city,
      "country": country,
      "device": api_info.device_type,
      "frogpilot_car_params": get_frogpilot_car_params(params),
      "frogpilot_dongle_id": api_info.dongle_id,
      "frogpilot_stats": params.get("FrogPilotStats") or {},
      "state": state,
      "toggles": vars(frogpilot_toggles),
      "using_default_model": using_default_model,
    },
  }

  try:
    response = requests.post(
      f"{frogpilot_variables.FROGPILOT_API}/stats",
      json=payload,
      headers={"Content-Type": "application/json", "User-Agent": "frogpilot-api/1.0"},
      timeout=30,
    )
    response.raise_for_status()
    print("Successfully sent FrogPilot stats!")
  except requests.exceptions.RequestException as error:
    print(f"Failed to send stats: {error}")
