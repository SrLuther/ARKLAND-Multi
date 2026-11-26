#include <API/ARK/Ark.h>
#include <Logger/Logger.h>
#include "ChatTransport.h"
#include <atomic>
#include <filesystem>
#include <set>
#include <unordered_map>
#include <chrono>
#include <cmath>

extern "C" IMAGE_DOS_HEADER __ImageBase;

namespace ChatArkland {
namespace {
std::unique_ptr<Transport> transport;
std::unordered_map<std::string,std::string> sessions;
std::unordered_map<std::string,Json> actors;
std::unordered_map<std::string,std::chrono::steady_clock::time_point> last_message;
std::array<uint64_t,4> observed{};
double sample_elapsed=1.0;
double debug_elapsed=0.0;
bool legacy_warned=false;
using GetGroupsFn=TArray<FString>(*)(uint64);

bool LegacyLoaded(){return GetModuleHandleW(L"KalsCrossChat.dll")!=nullptr;}
bool Ready(){return ArkApi::GetApiUtils().GetStatus()==ArkApi::ServerStatus::Ready;}
std::string String(const FString& value){return value.IsEmpty()?"":Utf8(std::wstring(*value));}
FString GameString(const std::string& value){return FString(Wide(value).c_str());}
std::string Steam(AShooterPlayerController* player){auto id=ArkApi::GetApiUtils().GetSteamIdFromController(player);return id?std::to_string(id):"";}
std::vector<AShooterPlayerController*> Controllers(){
    std::vector<AShooterPlayerController*> result;if(!Ready())return result;
    for(auto weak:ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField())if(auto* player=static_cast<AShooterPlayerController*>(weak.Get()))result.push_back(player);
    return result;
}
Json Groups(uint64_t steam){
    Json groups=Json::array({"Default"});
    if(HMODULE module=GetModuleHandleW(L"Permissions.dll")){
        auto function=reinterpret_cast<GetGroupsFn>(GetProcAddress(module,"?GetPlayerGroups@Permissions@@YA?AV?$TArray@VFString@@VFDefaultAllocator@@@@_K@Z"));
        if(function)for(const auto& group:function(steam)){if(groups.size()>=100)break;auto value=String(group);if(!value.empty())groups.push_back(value);}
    }
    return groups;
}
Json Actor(AShooterPlayerController* player){
    std::string steam=Steam(player);if(steam.empty())return Json();
    auto* state=static_cast<AShooterPlayerState*>(player->PlayerStateField());
    if(!state)return Json();
    auto* character=player->GetPlayerCharacter();
    std::string name=character?String(character->PlayerNameField()):String(state->PlayerNameField());
    std::string tribe_name,tribe_id;
    if(FTribeData* tribe=state->MyTribeDataField()){
        tribe_name=String(tribe->TribeNameField());int id=tribe->TribeIDField();if(id>0)tribe_id=std::to_string(id);
    }else{
        int id=state->GetTribeId();if(id>0)tribe_id=std::to_string(id);
    }
    uint64_t pdid=ArkApi::GetApiUtils().GetPlayerID(player);
    if(!pdid||pdid==static_cast<uint64_t>(-1))pdid=player->GetLinkedPlayerID();
    auto session=sessions.find(steam);if(session==sessions.end())session=sessions.emplace(steam,"ca-"+transport->Boot()+"-"+CompactId()).first;
    return {{"steam_id",steam},{"session_id",session->second},{"name",name},{"steam_name",String(state->PlayerNameField())},
            {"character_id",pdid&&pdid!=static_cast<uint64_t>(-1)?std::to_string(pdid):""},
            {"tribe_id",tribe_id},{"tribe_name",tribe_name},{"groups",Groups(std::stoull(steam))}};
}
bool Active(){return transport&&Ready()&&!transport->ObserveOnly()&&!transport->State()->observer&&!LegacyLoaded()&&!transport->State()->config.at("DisableChat").get<bool>();}
bool OwnCommands(){
    if(!transport||!Ready()||transport->ObserveOnly()||LegacyLoaded())return false;
    auto state=transport->State();auto map=state->config.at("Maps").value(transport->ServerKey(),Json::object());return map.value("Enabled",false);
}
void Chat(AShooterPlayerController* player,const std::string& text,bool rich=false){
    FChatMessage message{};message.Message=GameString(rich?text:GameChatText(text));player->ClientChatMessage(message);
}
void Notice(AShooterPlayerController* player,const std::string& text,float scale=0.5f,float seconds=10.f,std::array<float,4> color={1,1,1,1}){
    ArkApi::GetApiUtils().SendNotification(player,{color[0],color[1],color[2],color[3]},scale,seconds,nullptr,L"{}",Wide(Escape(text)).c_str());
}
std::string Arguments(const FString& value,const std::string& command){
    std::string body=String(value);if(body.size()>=command.size())body.erase(0,command.size());
    auto start=body.find_first_not_of(" \t");return start==std::string::npos?"":body.substr(start);
}
void QueueCommand(AShooterPlayerController* player,FString* text,const std::string& command,const std::string& kind){
    try{
        if(!OwnCommands())return;
        auto state=transport->State();
        bool disabled=state->config.at("DisableChat").get<bool>()||((kind=="pm"||kind=="reply")&&!state->config.at("PrivateMessages").at("Enabled").get<bool>())
            ||(kind=="online"&&!state->config.at("OnlinePlayersCommand").at("Enabled").get<bool>())
            ||(kind=="joinleave"&&!state->config.at("CrossMapNotifications").at("Enabled").get<bool>());
        if(disabled){Notice(player,Message(state->config,"Disabled"));return;}
        if(!transport->Healthy()){Notice(player,Message(state->config,"Unavailable"));return;}
        Json actor=Actor(player);if(actor.is_null())return;
        if(!actors.count(actor.at("steam_id").get<std::string>())){Notice(player,Message(state->config,"PendingIdentity"));return;}
        Json event={{"event_id",NewId()},{"steam_id",actor.at("steam_id")},{"kind",kind},{"body",Arguments(*text,command)}};
        if(!transport->Enqueue(event))Notice(player,Message(state->config,"Unavailable"));
    }catch(...){if(player&&transport)Notice(player,Message(transport->State()->config,"Unavailable"));}
}
bool HandleCommand(AShooterPlayerController* player,FString* text){
    std::vector<std::pair<std::string,std::string>> desired;
    if(OwnCommands()){
        const auto& cfg=transport->State()->config;
        desired.push_back({cfg["OnlinePlayersCommand"]["Command"].get<std::string>(),"online"});
        desired.push_back({cfg["PrivateMessages"]["Command"].get<std::string>(),"pm"});
        desired.push_back({cfg["PrivateMessages"]["ReplyCommand"].get<std::string>(),"reply"});
        desired.push_back({cfg["CrossMapNotifications"]["ToggleCommand"].get<std::string>(),"joinleave"});
    }
    auto value=String(*text);auto end=value.find_first_of(" \t");auto token=value.substr(0,end);
    for(const auto& [command,kind]:desired)if(_stricmp(token.c_str(),command.c_str())==0){QueueCommand(player,text,command,kind);return true;}
    if(OwnCommands()&&(_stricmp(token.c_str(),"/pm")==0||_stricmp(token.c_str(),"/r")==0)){
        auto state=transport->State();bool reply=_stricmp(token.c_str(),"/r")==0;
        auto usage=Message(state->config,reply?"ReplyUsage":"PrivateUsage"),command=state->config.at("PrivateMessages").at(reply?"ReplyCommand":"Command").get<std::string>();
        size_t position=0;while((position=usage.find("{comando}",position))!=std::string::npos){usage.replace(position,9,command);position+=command.size();}
        Notice(player,usage);return true;
    }
    return false;
}
bool OnChat(AShooterPlayerController* player,FString* message,EChatSendMode::Type mode,bool,bool executed){
    try{
        if(static_cast<size_t>(mode)<observed.size())++observed[static_cast<size_t>(mode)];
        if(!player||!message||executed)return false;
        // O registro global de comandos remove por nome, sem dono. Tratar os
        // nossos no callback evita remover comandos pertencentes a outro plugin.
        if(HandleCommand(player,message))return true;
        if(!Active())return false;
        auto state=transport->State();std::string original=NormalizeEmojis(String(*message));
        if(original.empty()||original.front()=='/')return false;
        std::string body=state->filter->Apply(original);if(body!=original)*message=GameString(GameChatText(body));
        // Mensagens locais, de tribo e de aliados nunca entram no transporte.
        if(mode!=EChatSendMode::GlobalChat||!state->config.at("UseCrossChat").get<bool>())return false;
        if(!transport->Healthy())return false;
        Json actor=Actor(player);if(actor.is_null())return false;
        std::string steam=actor.at("steam_id").get<std::string>();
        if(!state->players.contains(steam)||!actors.count(steam)){Notice(player,Message(state->config,"PendingIdentity"));return false;}
        bool immune=false;
        if(state->config.at("AdminImmuneToMuteAndSpamDelay").get<bool>())for(const auto& group:actor.at("groups"))
            for(const auto& admin:state->config.at("AdminGroups"))immune|=group==admin;
        auto now=std::chrono::steady_clock::now();auto previous=last_message.find(steam);
        if(!immune&&previous!=last_message.end()&&std::chrono::duration<double>(now-previous->second).count()<state->config.at("GlobalChatSpamDelaySec").get<double>()){
            auto notice=Message(state->config,"Spam");auto position=notice.find("{segundos}");
            auto remaining=static_cast<int>(std::ceil(state->config.at("GlobalChatSpamDelaySec").get<double>()-std::chrono::duration<double>(now-previous->second).count()));
            if(position!=std::string::npos)notice.replace(position,std::string("{segundos}").size(),std::to_string(std::max(1,remaining)));Notice(player,notice);return true;
        }
        Json event={{"event_id",NewId()},{"steam_id",steam},{"kind","global"},{"body",body},{"_actor",actor}};
        if(!transport->Enqueue(event)){Notice(player,Message(state->config,"Unavailable"));return false;}
        last_message[steam]=now;return true;
    }catch(...){return false;}
}
bool Deliver(const Json& item){
    std::string kind=item.value("kind","");if(kind=="cursor")return true;
    auto state=transport->State();bool delivered=false;
    std::set<std::string> recipients;for(const auto& steam:item.value("recipients",Json::array()))recipients.insert(steam.get<std::string>());
    if(kind!="global"&&kind!="local_fallback"&&recipients.empty())return false;
    for(auto* player:Controllers()){
        auto steam=Steam(player);if(!recipients.empty()&&!recipients.count(steam))continue;
        if(kind=="global"||kind=="local_fallback"){
            std::string rich=item.value("rich","");
            if(kind=="global"){
                bool same=item.value("source_server_key","")==transport->ServerKey(),own=item.value("sender_steam","")==steam;
                if(own)rich=item.value(same?"own_local_rich":"own_rich",rich);
                else if(same)rich=item.value("local_rich",rich);
            }
            if(!rich.empty()){Chat(player,rich,true);delivered=true;}
        }else if(kind=="notification"){
            const auto& policy=state->config.at("CrossMapNotifications");if(!policy.at("Enabled").get<bool>())continue;
            bool same=item.value("source_server_key","")==transport->ServerKey();
            std::string color=item.value("event","")=="join"?(same?"JoinSameColor":"JoinDifferentColor"):(same?"LeaveSameColor":"LeaveDifferentColor");
            Notice(player,item.at("text").get<std::string>(),policy.at("DisplayScale").get<float>(),policy.at("DisplayTime").get<float>(),Color(policy.at(color).get<std::string>()));delivered=true;
        }else if(kind=="online"){
            Notice(player,item.at("text").get<std::string>(),item.value("scale",0.5f),item.value("duration",10.f));delivered=true;
        }else if(kind=="pm"||kind=="notice"){
            Chat(player,item.at("text").get<std::string>());delivered=true;
        }
    }
    return delivered;
}
void Tick(float delta){
    try{
        if(!transport||!Ready())return;
        debug_elapsed+=delta;
        if(debug_elapsed>=30.0){debug_elapsed=0;if(transport->State()->config.at("Debug").get<bool>())Log::GetLog()->info("Chat Arkland diagnóstico: {} | modos observados global={}, tribo={}, local={}, aliança={}",transport->Status().dump(),observed[0],observed[1],observed[2],observed[3]);}
        if(LegacyLoaded()&&!legacy_warned){Log::GetLog()->warn("Chat Arkland em observação: KalsCrossChat está carregado. Valide e isole o piloto antes de ativar o encaminhamento.");legacy_warned=true;}
        sample_elapsed+=delta;
        if(sample_elapsed>=1.0){
            sample_elapsed=0;Json snapshot=Json::array();std::set<std::string> present;actors.clear();
            for(auto* player:Controllers())try{auto actor=Actor(player);if(actor.is_null())continue;auto steam=actor.at("steam_id").get<std::string>();present.insert(steam);actors[steam]=actor;snapshot.push_back(actor);}catch(...){}
            for(auto it=sessions.begin();it!=sessions.end();)if(!present.count(it->first)){last_message.erase(it->first);it=sessions.erase(it);}else++it;
            transport->Snapshot(std::move(snapshot));
        }
        for(const auto& item:transport->Drain()){
            bool delivered=false;try{if(Active()||item.value("kind","")=="cursor")delivered=Deliver(item);}catch(...){}
            transport->Processed(item,delivered);
        }
    }catch(...){Log::GetLog()->warn("Chat Arkland: ciclo adiado; chat nativo preservado.");}
}
void Status(APlayerController* pc,FString*,bool){
    std::string message=transport?transport->Status().dump():"Chat Arkland não iniciou. Confira config.json.";
    Log::GetLog()->info("Chat Arkland: {}",message);
    if(pc)Notice(static_cast<AShooterPlayerController*>(pc),message);
}
}
}
extern "C" __declspec(dllexport) void Plugin_Init(){
    using namespace ChatArkland;
    Log::Get().Init("ChatArkland");
    try{
        wchar_t path[32768]{};GetModuleFileNameW(reinterpret_cast<HMODULE>(&__ImageBase),path,32768);
        transport=std::make_unique<Transport>(std::filesystem::path(path).parent_path()/"config.json");
        ArkApi::GetCommands().AddOnTickCallback(L"ChatArkland.Tick",Tick);
        ArkApi::GetCommands().AddOnChatMessageCallback(L"ChatArkland.Chat",OnChat);
        ArkApi::GetCommands().AddConsoleCommand(L"ChatArkland.Status",Status);
        transport->Start();
        Log::GetLog()->info("Chat Arkland 0.1.1 carregado; aguardando configuração e validação da instância.");
    }catch(...){Log::GetLog()->error("Chat Arkland não iniciou. Verifique o arquivo config.json; o chat nativo permanece disponível.");}
}
extern "C" __declspec(dllexport) void Plugin_Unload(){
    using namespace ChatArkland;
    ArkApi::GetCommands().RemoveOnChatMessageCallback(L"ChatArkland.Chat");
    ArkApi::GetCommands().RemoveOnTickCallback(L"ChatArkland.Tick");
    ArkApi::GetCommands().RemoveConsoleCommand(L"ChatArkland.Status");
    if(transport){transport->Stop();transport.reset();}
    sessions.clear();actors.clear();last_message.clear();
    Log::GetLog()->info("Chat Arkland encerrado com callbacks e transporte removidos.");
}
