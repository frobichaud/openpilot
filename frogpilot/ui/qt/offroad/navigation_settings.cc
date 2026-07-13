#include "frogpilot/ui/qt/offroad/navigation_settings.h"

FrogPilotNavigationPanel::FrogPilotNavigationPanel(FrogPilotSettingsWindow *parent, bool forceOpen) : FrogPilotListWidget(parent), parent(parent) {
  forceOpenDescriptions = forceOpen;

  networkManager = new QNetworkAccessManager(this);

  primelessLayout = new QStackedLayout();
  addItem(primelessLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);
  ipLabel = new LabelControl(tr("Manage Your Settings At"), tr("Offline..."), tr("<b>Open this address in a browser on the same Wi-Fi to reach \"The Pond\", where you search for destinations and send them to your car.</b>"));
  settingsList->addItem(ipLabel);

  publicMapboxKeyControl = new FrogPilotButtonsControl(tr("Public Mapbox Key"), tr("<b>Lets you search for a destination and preview the route without paying for comma's subscription.</b><br><br>You make this key yourself on Mapbox's website. Navigation stays locked until both this and the \"Secret Mapbox Key\" are set, so add both. \"Mapbox Setup Instructions\" walks you through it."), "", {tr("ADD"), tr("TEST")});
  QObject::connect(publicMapboxKeyControl, &FrogPilotButtonsControl::buttonClicked, [this](int id) {
    if (id == 0) {
      if (mapboxPublicKeySet) {
        if (FrogPilotConfirmationDialog::yesorno(tr("Remove your Public Mapbox Key?"), this)) {
          params.remove("MapboxPublicKey");

          updateButtons();
        }
      } else {
        int minKeyLength = 80;
        QString key = InputDialog::getText(tr("Enter your Public Mapbox Key"), this, "", false, minKeyLength).trimmed();
        if (!key.isEmpty()) {
          if (key.startsWith("sk.")) {
            ConfirmationDialog::alert(tr("That's your Secret Mapbox Key. Enter your Public Mapbox Key."), this);
            return;
          }
          if (!key.startsWith("pk.")) {
            key = "pk." + key;
          }
          params.put("MapboxPublicKey", key.toStdString());
          updateButtons();
        }
      }
    } else {
      publicMapboxKeyControl->setValue(tr("Testing..."));

      QString key = QString::fromStdString(params.get("MapboxPublicKey"));
      QString url = QString("https://api.mapbox.com/geocoding/v5/mapbox.places/mapbox.json?access_token=%1").arg(key);

      QNetworkRequest request(url);
      QNetworkReply *reply = networkManager->get(request);
      connect(reply, &QNetworkReply::finished, [=]() {
        publicMapboxKeyControl->setValue("");

        QString message;
        if (reply->error() == QNetworkReply::NoError) {
          message = tr("Key is valid!");
        } else if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 401) {
          message = tr("Key is invalid!");
        } else {
          message = tr("An error occurred: %1").arg(QString(reply->errorString()).replace(key, tr("[key hidden]")));
        }

        if (isVisible()) {
          ConfirmationDialog::alert(message, this);
        }
        reply->deleteLater();
      });
    }
  });
  settingsList->addItem(publicMapboxKeyControl);

  secretMapboxKeyControl = new FrogPilotButtonsControl(tr("Secret Mapbox Key"), tr("<b>Draws the map itself on your driving screen, alongside what the \"Public Mapbox Key\" does for searching.</b><br><br>Keep this one to yourself, since it can be used to run up charges on your Mapbox account. After you add it you are asked whether to reboot now or later, and it does not take effect until the device has actually rebooted."), "", {tr("ADD"), tr("TEST")});
  QObject::connect(secretMapboxKeyControl, &FrogPilotButtonsControl::buttonClicked, [this](int id) {
    if (id == 0) {
      if (mapboxSecretKeySet) {
        if (FrogPilotConfirmationDialog::yesorno(tr("Remove your Secret Mapbox Key?"), this)) {
          params.remove("MapboxSecretKey");

          updateButtons();
        }
      } else {
        int minKeyLength = 80;
        QString key = InputDialog::getText(tr("Enter your Secret Mapbox Key"), this, "", false, minKeyLength).trimmed();
        if (!key.isEmpty()) {
          if (key.startsWith("pk.")) {
            ConfirmationDialog::alert(tr("That's your Public Mapbox Key. Enter your Secret Mapbox Key."), this);
            return;
          }
          if (!key.startsWith("sk.")) {
            key = "sk." + key;
          }
          params.put("MapboxSecretKey", key.toStdString());
          updateButtons();

          if (FrogPilotConfirmationDialog::toggleReboot(this)) {
            Hardware::reboot();
          }
        }
      }
    } else {
      secretMapboxKeyControl->setValue(tr("Testing..."));

      QString key = QString::fromStdString(params.get("MapboxSecretKey"));
      QString url = QString("https://api.mapbox.com/directions/v5/mapbox/driving/-73.989,40.733;-74,40.733?access_token=%1").arg(key);

      QNetworkRequest request(url);
      QNetworkReply *reply = networkManager->get(request);
      connect(reply, &QNetworkReply::finished, [=]() {
        secretMapboxKeyControl->setValue("");

        QString message;
        if (reply->error() == QNetworkReply::NoError) {
          message = tr("Key is valid!");
        } else if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 401) {
          message = tr("Key is invalid!");
        } else {
          message = tr("An error occurred: %1").arg(QString(reply->errorString()).replace(key, tr("[key hidden]")));
        }

        if (isVisible()) {
          ConfirmationDialog::alert(message, this);
        }
        reply->deleteLater();
      });
    }
  });
  settingsList->addItem(secretMapboxKeyControl);

  setupButton = new ButtonControl(tr("Mapbox Setup Instructions"), tr("VIEW"), tr("<b>Walks you through getting your own free Mapbox keys so navigation works without comma's subscription.</b><br><br>The guide only shows the steps for where you are in setup, so it changes as you add each key. Tap the instructions to come back here."), this);
  QObject::connect(setupButton, &ButtonControl::clicked, [this]() {
    openSubPanel();

    updateStep();

    primelessLayout->setCurrentIndex(1);
  });
  settingsList->addItem(setupButton);

  std::vector<QString> filterButtonNames{tr("CANCEL"), tr("Manually Update Speed Limits")};
  updateSpeedLimitsToggle = new FrogPilotButtonControl("SpeedLimitFiller", tr("Speed Limit Filler"),
                                                    tr("<b>Collect missing or wrong speed limits automatically while you drive.</b><br><br>It compares what your dashboard reports, where supported, against Mapbox and \"Navigate on openpilot\".<br><br>When you're parked, FrogPilot will automatically process this data into a file to be used with the tool located at \"SpeedLimitFiller.frogpilot.com\".<br><br>Nothing gets collected until you download the map data for where you drive, since the road name is what tells FrogPilot which road each speed limit belongs to. Pick your areas under \"Map Sources\" and run \"Download Maps\" first.<br><br>You can download this file from \"The Pond\" in the \"Download Speed Limits\" menu.<br><br>Need a step-by-step guide? Visit <b>#speed-limit-filler</b> in the FrogPilot Discord."),
                                                       "", filterButtonNames);
  QObject::connect(updateSpeedLimitsToggle, &FrogPilotButtonControl::buttonClicked, [this](int id) {
    if (id == 0) {
      if (FrogPilotConfirmationDialog::yesorno(tr("Cancel the speed-limit update?"), this)) {
        updatingLimits = false;

        updateSpeedLimitsToggle->setEnabledButton(0, false);
        updateSpeedLimitsToggle->setValue(tr("Cancelled..."));

        params_memory.remove("UpdateSpeedLimits");

        QTimer::singleShot(2500, this, [this]() {
          updateSpeedLimitsToggle->clearCheckedButtons();
          updateSpeedLimitsToggle->setEnabledButton(0, true);
          updateSpeedLimitsToggle->setValue("");
          updateSpeedLimitsToggle->setVisibleButton(0, false);
          updateSpeedLimitsToggle->setVisibleButton(1, true);

          params_memory.remove("UpdateSpeedLimitsStatus");
        });
      }
    } else if (id == 1) {
      QJsonObject overpassRequests = QJsonDocument::fromJson(QString::fromStdString(params.get("OverpassRequests")).toUtf8()).object();

      int totalRequests = overpassRequests.value("total_requests").toInt(0);
      int maxRequests = overpassRequests.value("max_requests").toInt(10000);
      int savedDay = overpassRequests.value("day").toInt(QDate::currentDate().day());

      int currentDay = QDate::currentDate().day();

      if (savedDay != currentDay) {
        totalRequests = 0;
      }

      if (totalRequests >= maxRequests) {
        QTime now = QTime::currentTime();

        int secondsUntilMidnight = (24 * 3600) - (now.hour() * 3600 + now.minute() * 60 + now.second());
        int hours = secondsUntilMidnight / 3600;
        int minutes = (secondsUntilMidnight % 3600) / 60;

        ConfirmationDialog::alert(QString(tr("You've hit today's request limit.\n\nIt will reset in %1 hours and %2 minutes.")).arg(hours).arg(minutes), this);

        updateSpeedLimitsToggle->clearCheckedButtons();
        return;
      }

      updateSpeedLimitsToggle->setVisibleButton(0, true);
      updateSpeedLimitsToggle->setVisibleButton(1, false);

      if (FrogPilotConfirmationDialog::yesorno(tr("This process takes a while. It's recommended to start when you're done driving and connected to stable Wi-Fi. Continue?"), this)) {
        updatingLimits = true;

        updateSpeedLimitsToggle->setValue("Calculating...");

        params_memory.put("UpdateSpeedLimitsStatus", "Calculating...");
        params_memory.putBool("UpdateSpeedLimits", true);
      } else {
        updateSpeedLimitsToggle->setVisibleButton(0, false);
        updateSpeedLimitsToggle->setVisibleButton(1, true);

        updateSpeedLimitsToggle->clearCheckedButtons();
      }
    }
  });
  updateSpeedLimitsToggle->setVisibleButton(0, false);
  settingsList->addItem(updateSpeedLimitsToggle);

  ScrollView *settingsPanel = new ScrollView(settingsList, this);
  primelessLayout->addWidget(settingsPanel);

  imageLabel = new QLabel(this);

  ScrollView *instructionsPanel = new ScrollView(imageLabel, this);
  primelessLayout->addWidget(instructionsPanel);

  QObject::connect(parent, &FrogPilotSettingsWindow::closeSubPanel, [this]() {
    primelessLayout->setCurrentIndex(0);

    if (forceOpenDescriptions) {
      ipLabel->showDescription();
      publicMapboxKeyControl->showDescription();
      secretMapboxKeyControl->showDescription();
      setupButton->showDescription();
      updateSpeedLimitsToggle->showDescription();
    }
  });
  QObject::connect(uiState(), &UIState::uiUpdate, this, &FrogPilotNavigationPanel::updateState);
}

void FrogPilotNavigationPanel::showEvent(QShowEvent *event) {
  if (forceOpenDescriptions) {
    ipLabel->showDescription();
    publicMapboxKeyControl->showDescription();
    secretMapboxKeyControl->showDescription();
    setupButton->showDescription();
    updateSpeedLimitsToggle->showDescription();
  }

  UIState &s = *uiState();

  FrogPilotUIState &fs = *frogpilotUIState();
  FrogPilotUIScene &frogpilot_scene = fs.frogpilot_scene;

  updateButtons();

  updatingLimits = !params_memory.get("UpdateSpeedLimitsStatus").empty() && QString::fromStdString(params_memory.get("UpdateSpeedLimitsStatus")) != "Completed!";

  bool parked = !s.scene.started || frogpilot_scene.parked || parent->isFrogsGoMoo;

  updateSpeedLimitsToggle->setVisibleButton(0, updatingLimits);
  updateSpeedLimitsToggle->setVisibleButton(1, !updatingLimits);

  if (updatingLimits) {
    updateSpeedLimitsToggle->setValue(QString::fromStdString(params_memory.get("UpdateSpeedLimitsStatus")));
  } else {
    updateSpeedLimitsToggle->setEnabledButton(1, frogpilot_scene.online && util::system_time_valid() && parked);
    updateSpeedLimitsToggle->setValue(frogpilot_scene.online ? (parked ? "" : "Not parked") : tr("Offline..."));
    updateSpeedLimitsToggle->setVisible(parent->tuningLevel >= parent->frogpilotToggleLevels["SpeedLimitFiller"].toDouble());
  }
}

void FrogPilotNavigationPanel::hideEvent(QHideEvent *event) {
  primelessLayout->setCurrentIndex(0);
}

void FrogPilotNavigationPanel::mousePressEvent(QMouseEvent *event) {
  if (primelessLayout->currentIndex() == 1) {
    closeSubPanel();

    primelessLayout->setCurrentIndex(0);

    if (forceOpenDescriptions) {
      ipLabel->showDescription();
      publicMapboxKeyControl->showDescription();
      secretMapboxKeyControl->showDescription();
      setupButton->showDescription();
      updateSpeedLimitsToggle->showDescription();
    }
  }
}

void FrogPilotNavigationPanel::updateButtons() {
  FrogPilotUIState &fs = *frogpilotUIState();
  FrogPilotUIScene &frogpilot_scene = fs.frogpilot_scene;

  QString ipAddress = fs.wifi->getIp4Address();
  ipLabel->setText(ipAddress.isEmpty() ? tr("Offline...") : QString("%1:8082").arg(ipAddress));

  mapboxPublicKeySet = QString::fromStdString(params.get("MapboxPublicKey")).startsWith("pk");
  mapboxSecretKeySet = QString::fromStdString(params.get("MapboxSecretKey")).startsWith("sk");

  publicMapboxKeyControl->setText(0, mapboxPublicKeySet ? tr("REMOVE") : tr("ADD"));
  publicMapboxKeyControl->setVisibleButton(1, mapboxPublicKeySet && frogpilot_scene.online);
  secretMapboxKeyControl->setText(0, mapboxSecretKeySet ? tr("REMOVE") : tr("ADD"));
  secretMapboxKeyControl->setVisibleButton(1, mapboxSecretKeySet && frogpilot_scene.online);
}

void FrogPilotNavigationPanel::updateState(const UIState &s, const FrogPilotUIState &fs) {
  if (!isVisible() || s.sm->frame % (UI_FREQ / 2) != 0) {
    return;
  }

  const FrogPilotUIScene &frogpilot_scene = fs.frogpilot_scene;

  updateButtons();
  updateStep();

  bool parked = !s.scene.started || frogpilot_scene.parked || parent->isFrogsGoMoo;

  if (updatingLimits) {
    if (QString::fromStdString(params_memory.get("UpdateSpeedLimitsStatus")) == "Completed!") {
      updatingLimits = false;

      updateSpeedLimitsToggle->setValue(tr("Completed!"));

      QTimer::singleShot(2500, this, [this]() {
        updateSpeedLimitsToggle->clearCheckedButtons();
        updateSpeedLimitsToggle->setValue("");
        updateSpeedLimitsToggle->setVisibleButton(0, false);
        updateSpeedLimitsToggle->setVisibleButton(1, true);

        params_memory.remove("UpdateSpeedLimitsStatus");
      });
    } else {
      updateSpeedLimitsToggle->setValue(QString::fromStdString(params_memory.get("UpdateSpeedLimitsStatus")));
    }
  } else {
    updateSpeedLimitsToggle->setEnabledButton(1, frogpilot_scene.online && util::system_time_valid() && parked);
    updateSpeedLimitsToggle->setValue(frogpilot_scene.online ? (parked ? "" : "Not parked") : tr("Offline..."));
  }

  parent->keepScreenOn = primelessLayout->currentIndex() == 1 || updatingLimits;
}

void FrogPilotNavigationPanel::updateStep() {
  QString currentStep;
  if (mapboxPublicKeySet) {
    currentStep = "../../frogpilot/navigation/navigation_training/public_key_set.png";
  } else {
    currentStep = "../../frogpilot/navigation/navigation_training/no_keys_set.png";
  }

  QPixmap pixmap;
  pixmap.load(currentStep);
  imageLabel->setPixmap(pixmap.scaledToWidth(1500, Qt::SmoothTransformation));

  update();
}
