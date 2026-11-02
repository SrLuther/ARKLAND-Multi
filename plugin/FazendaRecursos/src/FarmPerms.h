#pragma once
#include "pch.h"
namespace FazendaRecursos::Perms {
    void Init();
    bool IsInGroup(uint64_t steam_id, const std::string& group);
    bool IsAvailable();
}
