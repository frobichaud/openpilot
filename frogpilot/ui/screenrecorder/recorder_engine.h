#pragma once

#include <atomic>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include <QImage>

#include "frogpilot/ui/screenrecorder/screen_encoder.h"

class RecorderEngine {
public:
  RecorderEngine(int width, int height, int fps, int bitrate);
  ~RecorderEngine();

  bool is_recording() const { return recording; }
  bool start();

  bool can_accept_frame() const;
  void request_stop();
  void stop();
  void submit_frame(QImage &&frame, uint64_t ts_ns);

private:
  struct CapturedFrame {
    QImage image;

    uint64_t ts_ns;
  };

  bool open_segment();

  const QImage &blend_frames(const QImage &a, const QImage &b);

  void worker_loop();

  static constexpr size_t MAX_QUEUE = 4;

  static std::atomic<bool> engine_active;

  const int bitrate;
  const int fps;
  const int height;
  const int width;

  uint64_t segment_start_ns = 0;

  QImage blend_buf;
  bool size_warned = false;

  std::atomic<bool> recording{false};
  std::atomic<bool> worker_finished{true};

  std::condition_variable q_cv;

  std::deque<CapturedFrame> queue;

  mutable std::mutex q_mutex;

  std::string segment_path() const;

  std::thread worker;

  std::unique_ptr<ScreenEncoder> encoder;
};
