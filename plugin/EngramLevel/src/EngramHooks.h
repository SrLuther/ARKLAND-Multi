#pragma once

namespace EngramLevel {
namespace Hooks {

void Register();
void Unregister();

// Enquanto Enabled (e a supressão) estiver ligado, deixa
// bAutoUnlockAllEngrams false e zera OverridePlayerLevelEngramPoints >= buyout.
// Não repõe no fim do ServerApplyLevelUp.
void SyncCrashMask();

// Unload ou Enabled false: repõe o que foi lido na primeira máscara bem sucedida.
void ReleaseCrashMask();

} // namespace Hooks
} // namespace EngramLevel
