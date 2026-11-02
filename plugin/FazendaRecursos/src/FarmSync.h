#pragma once
#include "pch.h"

namespace FazendaRecursos::FarmSync {
void Start();
void Stop();
void QueuePlayer(const std::string& steam_id);
}
