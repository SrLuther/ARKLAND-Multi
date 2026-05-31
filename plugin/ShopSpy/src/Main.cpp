#include "pch.h"
#include <unordered_set>
#include <mutex>
#include <ctime>

// log proprio na pasta do plugin
static std::ofstream g_logFile;

static void SpyLog(const std::string& msg)
{
    Log::GetLog()->info("[ShopSpy] {}", msg);
    if (g_logFile.is_open())
    {
        time_t now = time(nullptr);
        char ts[20];
        strftime(ts, sizeof(ts), "%m/%d/%y %H:%M:%S", localtime(&now));
        g_logFile << ts << " " << msg << "\n";
        g_logFile.flush();
    }
}

static nlohmann::json g_cfg;

static void LoadConfig()
{
    try { std::ifstream f("ArkApi/Plugins/ShopSpy/config.json"); if (f.is_open()) f >> g_cfg; } catch (...) {}
    if (!g_cfg.contains("HexDumpKeywords"))
        g_cfg["HexDumpKeywords"] = nlohmann::json::array({"shop","buy","store","kit","point","item","sell","trade","server","open","ui"});
    if (!g_cfg.contains("HexDumpBytes")) g_cfg["HexDumpBytes"] = 64;
    if (!g_cfg.contains("LogAllRpcs"))   g_cfg["LogAllRpcs"]   = false;
}

static std::string HexDump(const void* data, size_t len)
{
    if (!data || IsBadReadPtr(data, len)) return "<unreadable>";
    std::ostringstream ss;
    const auto* p = static_cast<const uint8_t*>(data);
    for (size_t i = 0; i < len; ++i) { char b[4]; snprintf(b, sizeof(b), "%02X ", p[i]); ss << b; }
    return ss.str();
}

static std::string ToLower(std::string s) { std::transform(s.begin(), s.end(), s.begin(), ::tolower); return s; }

// Hook global — UObject.ProcessEvent
// RPCs de mods Blueprint chegam pelo actor do MOD, nao pelo PC.
// Filtra por nome de funcao (keywords) antes de qualquer outra operacao.
static std::mutex g_mutex;
static std::unordered_set<std::string> g_seen;

DECLARE_HOOK(UObject_ProcessEvent, void, UObject*, UFunction*, void*);

void Hook_UObject_ProcessEvent(UObject* obj, UFunction* func, void* params)
{
    UObject_ProcessEvent_original(obj, func, params);
    if (!obj || !func) return;

    const std::string fname = func->NameField().ToString().ToString();
    if (fname.empty()) return;

    const bool logAll = g_cfg.value("LogAllRpcs", false);
    const std::string fnameLow = ToLower(fname);

    bool relevant = logAll;
    if (!relevant)
        for (const auto& kw : g_cfg["HexDumpKeywords"])
            if (fnameLow.find(kw.get<std::string>()) != std::string::npos) { relevant = true; break; }
    if (!relevant) return;

    { std::lock_guard<std::mutex> lk(g_mutex); if (!g_seen.insert(fname).second) return; }

    std::string className = "?";
    if (UClass* cls = obj->ClassField()) className = cls->NameField().ToString().ToString();

    const size_t dumpLen = g_cfg.value("HexDumpBytes", 64);
    SpyLog(fmt::format("RPC  class={}  func={}  params=[{}]", className, fname, HexDump(params, dumpLen)));
}

DECLARE_HOOK(AShooterPlayerController_ClientServerNotification, void,
    AShooterPlayerController*, FString*, FLinearColor, float, float, UTexture2D*, USoundBase*);

void Hook_AShooterPlayerController_ClientServerNotification(
    AShooterPlayerController* pc, FString* msg, FLinearColor color,
    float displayScale, float displayTime, UTexture2D* icon, USoundBase* sound)
{
    if (pc && msg)
        SpyLog(fmt::format("NOTIF_OUT  steamId={}  msg=\"{}\"",
            ArkApi::IApiUtils::GetSteamIdFromController(pc), msg->ToString()));
    AShooterPlayerController_ClientServerNotification_original(pc, msg, color, displayScale, displayTime, icon, sound);
}

DECLARE_HOOK(AShooterPlayerController_ClientServerChatDirectMessage, void,
    AShooterPlayerController*, FString*, FLinearColor, bool);

void Hook_AShooterPlayerController_ClientServerChatDirectMessage(
    AShooterPlayerController* pc, FString* msg, FLinearColor color, bool bold)
{
    if (pc && msg)
        SpyLog(fmt::format("CHAT_OUT  steamId={}  msg=\"{}\"",
            ArkApi::IApiUtils::GetSteamIdFromController(pc), msg->ToString()));
    AShooterPlayerController_ClientServerChatDirectMessage_original(pc, msg, color, bold);
}

DECLARE_HOOK(AShooterGameMode_BeginPlay, void, AShooterGameMode*);

void Hook_AShooterGameMode_BeginPlay(AShooterGameMode* gm)
{
    AShooterGameMode_BeginPlay_original(gm);
    const bool loaded = ArkApi::Tools::IsPluginLoaded("ArkShopUI");
    SpyLog(fmt::format("BeginPlay ArkShopUI={}", loaded));
    if (loaded)
    {
        HMODULE h = GetModuleHandleA("ArkShopUI");
        SpyLog(fmt::format("exports: RequestUI={} Reload={} UpdatePoints={} PlayerKits={}",
            GetProcAddress(h,"RequestUI")?"OK":"MISSING", GetProcAddress(h,"Reload")?"OK":"MISSING",
            GetProcAddress(h,"UpdatePoints")?"OK":"MISSING", GetProcAddress(h,"PlayerKits")?"OK":"MISSING"));
    }
}

extern "C" __declspec(dllexport) void Plugin_Init()
{
    Log::Get().Init("ShopSpy");
    LoadConfig();
    g_logFile.open("ArkApi/Plugins/ShopSpy/ShopSpy.log", std::ios::out | std::ios::app);
    SpyLog("ShopSpy v2 — log: ArkApi/Plugins/ShopSpy/ShopSpy.log");
    SpyLog("Hook: UObject.ProcessEvent global, filtra keywords");

    ArkApi::GetHooks().SetHook("AShooterGameMode.BeginPlay()",
        Hook_AShooterGameMode_BeginPlay, &AShooterGameMode_BeginPlay_original);
    ArkApi::GetHooks().SetHook("UObject.ProcessEvent(UFunction*,void*)",
        Hook_UObject_ProcessEvent, &UObject_ProcessEvent_original);
    ArkApi::GetHooks().SetHook(
        "AShooterPlayerController.ClientServerNotification(FString,FLinearColor,float,float,UTexture2D*,USoundBase*)",
        Hook_AShooterPlayerController_ClientServerNotification,
        &AShooterPlayerController_ClientServerNotification_original);
    ArkApi::GetHooks().SetHook(
        "AShooterPlayerController.ClientServerChatDirectMessage(FString,FLinearColor,bool)",
        Hook_AShooterPlayerController_ClientServerChatDirectMessage,
        &AShooterPlayerController_ClientServerChatDirectMessage_original);

    SpyLog("ShopSpy v2 pronto. Abra MX-E (F2) e interaja com a loja.");
}

extern "C" __declspec(dllexport) void Plugin_Unload()
{
    ArkApi::GetHooks().DisableHook("AShooterGameMode.BeginPlay()", Hook_AShooterGameMode_BeginPlay);
    ArkApi::GetHooks().DisableHook("UObject.ProcessEvent(UFunction*,void*)", Hook_UObject_ProcessEvent);
    ArkApi::GetHooks().DisableHook(
        "AShooterPlayerController.ClientServerNotification(FString,FLinearColor,float,float,UTexture2D*,USoundBase*)",
        Hook_AShooterPlayerController_ClientServerNotification);
    ArkApi::GetHooks().DisableHook(
        "AShooterPlayerController.ClientServerChatDirectMessage(FString,FLinearColor,bool)",
        Hook_AShooterPlayerController_ClientServerChatDirectMessage);
    SpyLog("ShopSpy descarregado.");
    if (g_logFile.is_open()) g_logFile.close();
}
