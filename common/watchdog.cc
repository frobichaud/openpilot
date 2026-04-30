#include <string>
#include <algorithm>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

#include "common/watchdog.h"
#include "common/timing.h"
#include "common/util.h"
#include "system/hardware/hw.h"

const std::string watchdog_fn_prefix = Path::shm_path() + "/wd_";  // + <pid>

bool watchdog_kick(uint64_t ts) {
  static std::string fn = watchdog_fn_prefix + std::to_string(getpid());
  return util::write_file(fn.c_str(), &ts, sizeof(ts), O_WRONLY | O_CREAT) > 0;
}

void watchdog_stage(const char *stage) {
  static int fd = -2;
  if (fd == -2) {
    static std::string fn = watchdog_fn_prefix + "stage_" + std::to_string(getpid());
    fd = open(fn.c_str(), O_WRONLY | O_CREAT | O_CLOEXEC, 0644);
  }
  if (fd < 0) return;

  char buf[256];
  int n = snprintf(buf, sizeof(buf), "pid=%d\nnanos=%llu\nstage=%s\n",
                   getpid(), (unsigned long long)nanos_since_boot(), stage);
  if (n <= 0) return;

  size_t len = std::min<size_t>(n, sizeof(buf) - 1);
  if (pwrite(fd, buf, len, 0) >= 0) {
    ftruncate(fd, len);
  }
}
