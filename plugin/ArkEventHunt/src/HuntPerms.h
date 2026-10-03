#pragma once

#include "pch.h"

namespace ArkEventHunt {
namespace Perms {

// Chamado em Plugin_Init: tentativa silenciosa. A Permissions normalmente
// ainda não está carregada (ordem alfabética do ArkApi) — NÃO é erro.
void Init();

// Tenta (re)ligar à Permissions. log_failure=true emite warning (1x) com o
// caminho procurado. Seguro chamar várias vezes.
bool Resolve(bool log_failure);

bool IsAvailable();

// "Default" sempre true. Liga lazy à Permissions no primeiro uso.
// Sem Permissions → false (excepto Default).
bool IsInGroup(uint64_t steam_id, const std::string& group);
bool IsInAnyGroup(uint64_t steam_id, const std::vector<std::string>& groups);

} // namespace Perms
} // namespace ArkEventHunt
