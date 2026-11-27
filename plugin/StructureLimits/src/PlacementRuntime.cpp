#include "PlacementRuntime.h"
#include <chrono>
#include <map>
#include <optional>
#include <set>
#include <sstream>

namespace StructureLimits {
namespace {
using Clock=std::chrono::steady_clock;
using Json=nlohmann::json;
LimitEngine* engine=nullptr;
InventoryJournal* journal=nullptr;
bool installed=false,pilotEnabled=false;
std::string suspendedReason="inventory_not_validated";
std::string instance;
struct Pending { std::string reservation,steam,blueprint; FVector location; Clock::time_point started; };
using Key=std::pair<std::uintptr_t,std::string>;
std::map<Key,Pending> pending;
std::set<std::string> provenBlueprints;
std::uint64_t denied=0,committed=0,cancelled=0,bypassed=0;
struct Trial {
    std::string steam,blueprint,itemBlueprint,state="idle";
    Clock::time_point expires{},checkAfter{};
    std::int64_t before=-1,after=-1;
    unsigned placementCallbacks=0;
    std::map<std::string,std::int64_t> armedItems;
};
Trial trial;

std::string Blueprint(UClass* type){
    if(!type)return {};
    FString name;type->GetFullName(&name,nullptr);
    return NormalizeBlueprintKey(name.ToString());
}
std::string Steam(APlayerController* player){
    if(!player||!player->IsA(AShooterPlayerController::GetPrivateStaticClass()))return {};
    const auto id=ArkApi::GetApiUtils().GetSteamIdFromController(static_cast<AShooterPlayerController*>(player));
    return id?std::to_string(id):std::string();
}
AShooterPlayerController* Player(const std::string& steam){
    auto* world=ArkApi::GetApiUtils().GetWorld();if(!world)return nullptr;
    for(auto weak:world->PlayerControllerListField()){
        auto* base=weak.Get();if(base&&base->IsA(AShooterPlayerController::GetPrivateStaticClass())&&Steam(static_cast<APlayerController*>(base))==steam)
            return static_cast<AShooterPlayerController*>(base);
    }
    return nullptr;
}
std::int64_t ItemCount(AShooterPlayerController* player,const std::string& blueprint){
    if(!player||blueprint.empty())return -1;
    auto* inventory=player->GetPlayerInventory();if(!inventory)return -1;
    const auto items=inventory->InventoryItemsField();
    if(items.Num()>16384)return -1;
    std::int64_t count=0;
    for(auto* item:items)if(item&&Blueprint(item->ClassField())==blueprint){
        const auto quantity=item->ItemQuantityField();if(quantity<0)return -1;
        count+=quantity;
    }
    return count;
}
std::optional<std::map<std::string,std::int64_t>> InventoryAtArm(AShooterPlayerController* player){
    if(!player||!player->GetPlayerInventory())return std::nullopt;
    const auto items=player->GetPlayerInventory()->InventoryItemsField();if(items.Num()>16384)return std::nullopt;
    std::map<std::string,std::int64_t> result;
    for(auto* item:items)if(item){const auto quantity=item->ItemQuantityField();if(quantity<0)return std::nullopt;
        const auto name=Blueprint(item->ClassField());if(!name.empty())result[name]+=quantity;}
    return result;
}
bool Event(const std::string& type,Json extra=Json::object()){
    extra["type"]=type;extra["instance"]=instance;extra["pilot_state"]=trial.state;
    if(!extra.contains("blueprint"))extra["blueprint"]=trial.blueprint;
    if(type.rfind("placement_pilot_",0)==0)extra["actor_steam_id"]=trial.steam;
    if(!journal||!journal->Event(std::move(extra))){SuspendPlacementRuntime("placement_journal_unhealthy");return false;}
    return true;
}
void Reply(RCONClientConnection* connection,RCONPacket* packet,const std::string& text){
    const auto wide=ArkApi::Tools::Utf8Decode(text);FString response(wide.c_str());connection->SendMessageW(packet->Id,0,&response);
}
void PilotCommand(RCONClientConnection* connection,RCONPacket* packet,UWorld*){
    try {
        std::istringstream input(packet->Body.ToString());std::string command,steam,blueprint,extra;
        input>>command>>steam>>blueprint>>extra;
        if(!pilotEnabled){Reply(connection,packet,"Pilot disabled by configuration");return;}
        if(steam=="cancel"){
            // An already vetoed attempt still completes its retention measurement.
            if(trial.state=="armed"){trial.state="cancelled";Event("placement_pilot_cancelled");}
            Reply(connection,packet,PlacementRuntimeStatus().dump());return;
        }
        if(trial.state=="armed"||trial.state=="observing_item"){
            Reply(connection,packet,"A pilot attempt is already pending; inspect StructureLimits.Status");return;
        }
        if(steam.size()!=17||steam.find_first_not_of("0123456789")!=std::string::npos||blueprint.empty()||!extra.empty()||!Player(steam)){
            Reply(connection,packet,"Usage: StructureLimits.Pilot <connected SteamID64> <blueprint|next>; one final placement, expires in 120 seconds");return;
        }
        const auto target=blueprint=="next"?std::string():NormalizeBlueprintKey(blueprint);
        if(blueprint!="next"&&target.empty()){Reply(connection,packet,"Invalid blueprint");return;}
        const auto baseline=InventoryAtArm(Player(steam));
        if(!baseline){Reply(connection,packet,"Player inventory unavailable; pilot not armed");return;}
        trial=Trial{};trial.steam=steam;trial.blueprint=target;trial.state="armed";trial.expires=Clock::now()+std::chrono::seconds(120);trial.armedItems=*baseline;
        if(!Event("placement_pilot_armed")){Reply(connection,packet,"Pilot not armed: journal unavailable");return;}
        Reply(connection,packet,"Pilot armed for one final allowed attempt by the selected player only. Check StructureLimits.Status after the attempt; no general limit enforcement enabled.");
    }catch(const std::exception& e){Reply(connection,packet,std::string("Pilot command failed: ")+e.what());}
}
void Tick(float){
    try {
        if(!engine)return;
        if(!journal||!journal->Healthy()||ArkApi::GetApiUtils().GetStatus()!=ArkApi::ServerStatus::Ready){
            SuspendPlacementRuntime("runtime_or_journal_unavailable");return;
        }
        const auto now=Clock::now();
        for(const auto& [key,value]:pending)if(now-value.started>std::chrono::seconds(5)){
            // Never free a potentially live reservation while continuing to enforce.
            SuspendPlacementRuntime("placement_reservation_timeout");break;
        }
        if(trial.state=="armed"&&now>=trial.expires){trial.state="expired";Event("placement_pilot_expired");}
        if(trial.state=="observing_item"&&now>=trial.checkAfter){
            trial.after=ItemCount(Player(trial.steam),trial.itemBlueprint);
            trial.state=trial.placementCallbacks?"placement_after_veto":trial.after<0?"item_measurement_unavailable":
                trial.after==trial.before?"item_preserved":"item_quantity_changed";
            if(trial.state=="item_preserved")provenBlueprints.insert(trial.blueprint);
            else {provenBlueprints.erase(trial.blueprint);SuspendPlacementRuntime("veto_retention_not_proven");}
            Event("placement_pilot_result",{{"item_before",trial.before},{"item_after",trial.after},{"placement_callbacks",trial.placementCallbacks}});
            Log::GetLog()->info("StructureLimits veto pilot: state={} blueprint={} item_before={} item_after={} placement_callbacks={}",trial.state,trial.blueprint,trial.before,trial.after,trial.placementCallbacks);
        }
    }catch(const std::exception& error){SuspendPlacementRuntime(std::string("placement_runtime_error: ")+error.what());}
}
}

void StartPlacementRuntime(const PluginConfiguration& config,LimitEngine& value,InventoryJournal& sink){
    engine=&value;journal=&sink;pilotEnabled=config.placementPilotEnabled;instance=config.Identity().displayId;
    pending.clear();provenBlueprints.clear();trial=Trial{};denied=committed=cancelled=bypassed=0;
    suspendedReason="inventory_not_validated";
    installed=true;
    ArkApi::GetCommands().AddOnTickCallback("StructureLimitsPlacement",&Tick);
    ArkApi::GetCommands().AddRconCommand(L"StructureLimits.Pilot",&PilotCommand);
}
void SuspendPlacementRuntime(const std::string& reason){
    suspendedReason=reason;
    if(engine){engine->SuspendEnforcement();for(const auto& [key,value]:pending)engine->CancelPlacement(value.reservation);}
    pending.clear();if(trial.state=="armed"||trial.state=="observing_item")trial.state="suspended";
    if(reason=="world_cleanup"||reason=="stopped")provenBlueprints.clear();
}
void StopPlacementRuntime(){
    SuspendPlacementRuntime("stopped");
    if(installed){ArkApi::GetCommands().RemoveOnTickCallback("StructureLimitsPlacement");ArkApi::GetCommands().RemoveRconCommand(L"StructureLimits.Pilot");installed=false;}
    engine=nullptr;journal=nullptr;pilotEnabled=false;
}
int CheckPlacementGate(APrimalStructure* structure,APlayerController* player,const FVector& location,bool finalPlacement,int originalResult){
    if(!engine||!journal||!journal->Healthy()||!structure||!finalPlacement||originalResult!=1)return originalResult;
    const auto steam=Steam(player),blueprint=Blueprint(structure->ClassField());if(steam.empty()||blueprint.empty())return originalResult;
    const auto now=Clock::now();
    if(pilotEnabled&&trial.state=="armed"&&now<trial.expires&&trial.steam==steam&&(trial.blueprint.empty()||trial.blueprint==blueprint)){
        trial.blueprint=blueprint;trial.itemBlueprint=Blueprint(structure->ConsumesPrimalItemField().uClass);
        const auto initial=trial.armedItems.find(trial.itemBlueprint);
        trial.before=initial==trial.armedItems.end()?-1:initial->second;
        const auto atHook=ItemCount(static_cast<AShooterPlayerController*>(player),trial.itemBlueprint);
        if(trial.before<=0||atHook!=trial.before){trial.state="inventory_changed_before_hook";
            Event("placement_pilot_unverifiable",{{"item_at_arm",trial.before},{"item_at_hook",atHook}});return originalResult;}
        trial.state="observing_item";trial.checkAfter=now+std::chrono::seconds(2);
        if(!Event("placement_pilot_veto",{{"item_before",trial.before},{"original_result",originalResult}})){
            trial.state="journal_unavailable";return originalResult;}
        ++denied;
        ArkApi::GetApiUtils().SendChatMessage(static_cast<AShooterPlayerController*>(player),L"ARKLAND",L"Piloto de bloqueio: posicionamento recusado. Aguarde 2 segundos; o item deve permanecer no inventario.");
        return 0;
    }
    if(!engine->IsEnforcing()){++bypassed;return originalResult;}
    // Evidence is scoped to the blueprint actually exercised, never a global JSON bypass.
    if(!provenBlueprints.count(blueprint)){++bypassed;return originalResult;}
    const Key key{reinterpret_cast<std::uintptr_t>(structure),steam};
    if(auto prior=pending.find(key);prior!=pending.end()){
        if(prior->second.blueprint==blueprint&&prior->second.location.X==location.X&&prior->second.location.Y==location.Y&&prior->second.location.Z==location.Z)return originalResult;
        engine->CancelPlacement(prior->second.reservation);pending.erase(prior);++cancelled;
    }
    if(pending.size()>=2048){SuspendPlacementRuntime("placement_reservation_capacity");return originalResult;}
    auto* shooter=static_cast<AShooterPlayerController*>(player);
    auto* state=static_cast<AShooterPlayerState*>(shooter->PlayerStateField());
    if(!state){SuspendPlacementRuntime("player_ownership_unavailable");return originalResult;}
    std::string tribe;
    if(auto* data=state->MyTribeDataField()){
        const auto id=data->TribeIDField();if(id==0||id==-1||id!=shooter->TargetingTeamField()){SuspendPlacementRuntime("player_ownership_conflict");return originalResult;}
        tribe=std::to_string(static_cast<std::uint32_t>(id));
    }else if(state->GetTribeId()>0){SuspendPlacementRuntime("player_tribe_unavailable");return originalResult;}
    const auto unixNow=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    const auto decision=engine->ReservePlacement(tribe,steam,blueprint,unixNow);
    if(decision.state==PlacementState::Denied){
        if(!Event("placement_limit_denied",{{"reason",decision.reason},{"blueprint",blueprint},{"actor_steam_id",steam}}))return originalResult;
        ++denied;
        ArkApi::GetApiUtils().SendChatMessage(shooter,L"ARKLAND",L"Limite de estruturas atingido. Consulte /limites e Minha Area ARKLAND.");return 0;}
    if(decision.state==PlacementState::Reserved)pending.emplace(key,Pending{decision.reservationId,steam,blueprint,location,now});
    return originalResult;
}
void CompletePlacementGate(APrimalStructure* structure,APlayerController* player,bool placed){
    if(!engine||!structure)return;
    const auto steam=Steam(player),blueprint=placed?Blueprint(structure->ClassField()):std::string();
    if(placed&&trial.state=="observing_item"&&steam==trial.steam&&blueprint==trial.blueprint)++trial.placementCallbacks;
    const Key key{reinterpret_cast<std::uintptr_t>(structure),steam};const auto entry=pending.find(key);
    if(entry==pending.end()){if(placed&&engine->IsEnforcing())SuspendPlacementRuntime("placement_without_reservation");return;}
    const auto reservation=entry->second.reservation;pending.erase(entry);
    if(!placed){engine->CancelPlacement(reservation);++cancelled;return;}
    const auto id=structure->StructureIDField();
    if(!id||!engine->CommitPlacement(reservation,std::to_string(id))){engine->CancelPlacement(reservation);SuspendPlacementRuntime("placement_commit_identity_conflict");return;}
    ++committed;
}
void RemovePlacementGate(APrimalStructure* structure){
    if(!engine||!structure)return;
    for(auto it=pending.begin();it!=pending.end();)if(it->first.first==reinterpret_cast<std::uintptr_t>(structure)){
        engine->CancelPlacement(it->second.reservation);it=pending.erase(it);++cancelled;
    }else ++it;
}
void ReleasePlacementCount(const std::string& structureId){if(engine)engine->ReleaseStructure(structureId);}
Json PlacementRuntimeStatus(){
    return {{"cap_enforcement",engine&&engine->IsEnforcing()},{"suspended_reason",suspendedReason},{"pending_reservations",pending.size()},
        {"denied",denied},{"committed",committed},{"cancelled",cancelled},{"bypassed",bypassed},{"pilot_enabled",pilotEnabled},
        {"pilot_state",trial.state},{"pilot_blueprint",trial.blueprint},{"item_before",trial.before},{"item_after",trial.after},
        {"placement_callbacks_after_veto",trial.placementCallbacks},{"proven_blueprints",provenBlueprints},
        {"pilot_seconds_remaining",trial.state=="armed"?(std::max)(0LL,std::chrono::duration_cast<std::chrono::seconds>(trial.expires-Clock::now()).count()):0LL}};
}
std::string PlacementPilotMessage(const std::string& steam){
    return trial.steam==steam&&trial.state=="armed"?"\nPiloto de veto armado para sua proxima tentativa; verifique a retencao do item.":std::string();
}
}
