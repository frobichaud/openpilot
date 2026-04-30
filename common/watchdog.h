#pragma once

#include <cstdint>

bool watchdog_kick(uint64_t ts);
void watchdog_stage(const char *stage);
