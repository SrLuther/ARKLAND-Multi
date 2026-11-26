#include "LiveInventoryRuntime.h"
#include "ObservedInventory.h"
#include <chrono>
#include <immintrin.h>
#include <unordered_map>

namespace StructureLimits {
namespace {
using Json=nlohmann::json;
ObservedInventory inventory;
PluginConfiguration configuration;
std::unique_ptr<InventoryJournal> journal;
UClass* supplyClass=nullptr;
bool installed=false,scanning=false,dirty=false;
bool runtimeHealthy=true;
bool acceptingEvents=false;
int stage=0,levelIndex=0,actorIndex=0;
std::size_t scanned=0,excluded=0,duplicates=0,scans=0;
std::unordered_map<std::string,AActor*> scanIds;
std::unordered_map<int,std::string> teamTribes,playerSteam;
std::chrono::steady_clock::time_point nextScan,nextPublish;
bool Ready(){return ArkApi::GetApiUtils().GetStatus()==ArkApi::ServerStatus::Ready;}
std::string Text(const FString& value){return value.IsEmpty()?"":value.ToString();}
Json Record(const ObservedStructure& record){
    Json result={{"structure_id",record.id},{"blueprint",record.blueprint},{"targeting_team",record.targetingTeam},
        {"player_data_id",static_cast<std::uint32_t>(record.playerId)},{"steam_id",record.steamId},{"tribe_id",record.tribeId},
        {"placement_confirmed",record.placementConfirmed},{"coordinates_available",record.hasCoordinates}};
    if(record.hasCoordinates)result["position"]={{"x",record.x},{"y",record.y},{"z",record.z},{"latitude",record.latitude},{"longitude",record.longitude}};
    return result;
}
void RefreshOwners(){
    teamTribes.clear();playerSteam.clear();
    for(auto weak:ArkApi::GetApiUtils().GetWorld()->PlayerControllerListField()){
        auto* player=static_cast<AShooterPlayerController*>(weak.Get());if(!player)continue;
        const auto steam=ArkApi::GetApiUtils().GetSteamIdFromController(player);
        const auto playerId=ArkApi::GetApiUtils().GetPlayerID(player);
        auto* state=static_cast<AShooterPlayerState*>(player->PlayerStateField());
        if(state){if(auto* tribe=state->MyTribeDataField()){
            const int id=tribe->TribeIDField();if(id>0&&player->TargetingTeamField()==id)teamTribes[id]=std::to_string(id);
        }else if(state->GetTribeId()<=0&&steam&&playerId&&playerId!=static_cast<std::uint64_t>(-1)){
            playerSteam[static_cast<int>(playerId)]=std::to_string(steam);
        }}
    }
}
std::optional<ObservedStructure> Capture(APrimalStructure* structure,bool removing=false){
    if(!structure||!structure->ClassField()||structure->bIsPreviewStructure().Get()||
       (!removing&&structure->IsPendingKillPending())||
       (supplyClass&&structure->IsA(supplyClass)))return std::nullopt;
    ObservedStructure value;value.id=std::to_string(structure->StructureIDField());
    value.targetingTeam=structure->TargetingTeamField();value.playerId=structure->OwningPlayerIDField();
    if(value.id=="0"||(!value.targetingTeam&&!value.playerId))return std::nullopt;
    FString name;structure->ClassField()->GetFullName(&name,nullptr);
    value.blueprint=NormalizeBlueprintKey(Text(name));
    if(auto tribe=teamTribes.find(value.targetingTeam);tribe!=teamTribes.end())value.tribeId=tribe->second;
    if(auto player=playerSteam.find(value.playerId);player!=playerSteam.end())value.steamId=player->second;
    if(auto* root=structure->RootComponentField()){
        float xyz[4]{};_mm_storeu_ps(xyz,root->ComponentToWorldField().Translation);
        value.x=xyz[0];value.y=xyz[1];value.z=xyz[2];
        auto* world=ArkApi::GetApiUtils().GetWorld();
        if(world&&world->GetWorldSettings(false,true)){
            const auto coords=ArkApi::GetApiUtils().FVectorToCoords(FVector(xyz[0],xyz[1],xyz[2]));
            value.latitude=coords.y;value.longitude=coords.x;value.hasCoordinates=true;
        }
    }
    return value;
}
Json Status(bool includeRecords){
    Json state={{"format","arkland-structure-limits-observed-v1"},{"plugin_version","0.8-dev"},
        {"instance",configuration.Identity().displayId},{"canonical_instance_path",configuration.Identity().canonicalInstancePath},
        {"complete_inventory",false},{"enforcement",false},{"reason","resident_and_local_stasis_coverage_not_yet_validated"},
        {"observed_structures",inventory.Records().size()},{"removed_this_boot",inventory.RemovedCount()},
        {"identity_conflicts",inventory.Conflicts()},{"scan_duplicate_ids",duplicates},{"scan_in_progress",scanning},
        {"completed_scans",scans},{"actors_visited",scanned},{"excluded_actors",excluded},
        {"runtime_healthy",runtimeHealthy},{"journal_healthy",journal&&journal->Healthy()},{"journal_pending",journal?journal->Pending():0},
        {"updated_at_unix",std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()}};
    if(includeRecords){state["structures"]=Json::array();for(const auto& [id,value]:inventory.Records())state["structures"].push_back(Record(value));}
    return state;
}
void ScanActor(AActor* actor){
    ++scanned;if(!actor||!actor->IsA(APrimalStructure::GetPrivateStaticClass()))return;
    auto record=Capture(static_cast<APrimalStructure*>(actor));
    if(!record){++excluded;return;}
    const auto prior=scanIds.find(record->id);
    if(prior!=scanIds.end()){if(prior->second!=actor)++duplicates;return;}
    scanIds.emplace(record->id,actor);
    const auto change=inventory.Observe(*record);
    if(change==ObservedInventory::Change::Added||change==ObservedInventory::Change::Updated){
        journal->Record(record->id,Record(inventory.Records().at(record->id)));dirty=true;}
}
void TickBody(){
    if(!journal||!acceptingEvents||!Ready())return;
    auto* world=ArkApi::GetApiUtils().GetWorld();if(!world)return;
    const auto now=std::chrono::steady_clock::now();
    if(!scanning&&now>=nextScan){
        RefreshOwners();scanning=true;stage=0;levelIndex=0;actorIndex=0;scanned=0;excluded=0;duplicates=0;scanIds.clear();
    }
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(2);
    for(int budget=0;scanning&&budget<512&&std::chrono::steady_clock::now()<deadline;++budget){
        if(stage==0){
            auto* level=world->PersistentLevelField();
            if(!level||actorIndex>=level->GetActorsField().Num()){stage=1;actorIndex=0;continue;}
            ScanActor(level->GetActorsField()[actorIndex++]);
        }else if(stage==1){
            const auto levels=world->LevelsField();
            if(levelIndex>=levels.Num()){stage=2;actorIndex=0;continue;}
            auto* level=levels[levelIndex];
            if(!level||level==world->PersistentLevelField()||actorIndex>=level->GetActorsField().Num()){++levelIndex;actorIndex=0;continue;}
            ScanActor(level->GetActorsField()[actorIndex++]);
        }else{
            auto& stasis=world->LocalStasisActorsField();
            if(actorIndex>=stasis.Num()){
                scanning=false;++scans;nextScan=now+std::chrono::seconds(30);dirty=true;
                Log::GetLog()->info("StructureLimits inventory: observed={} scans={} visited={} excluded={} duplicate_ids={} complete=false enforcement=false",inventory.Records().size(),scans,scanned,excluded,duplicates);
                break;
            }
            ScanActor(stasis[actorIndex++].Get());
        }
    }
    if(dirty&&now>=nextPublish){journal->State(Status(false));dirty=false;nextPublish=now+std::chrono::seconds(5);}
}
void Tick(float){
    if(!runtimeHealthy)return;
    try {TickBody();}
    catch(const std::exception& error){runtimeHealthy=false;
        Log::GetLog()->error("StructureLimits live inventory suspended: {}",error.what());}
}
void ShowLimits(AShooterPlayerController* player,FString*,bool){
    if(!Ready()||!player)return;
    RefreshOwners();
    std::string tribe;const auto found=teamTribes.find(player->TargetingTeamField());if(found!=teamTribes.end())tribe=found->second;
    const auto steam=ArkApi::GetApiUtils().GetSteamIdFromController(player);
    if(!steam)return;
    const auto summary=inventory.Summary(Owner::ForPlayer(tribe,std::to_string(steam)),configuration.limits);
    const auto text=std::string("Contagem observada (inventario em validacao; bloqueio desativado).\n")+FormatPrimaryLimitsMessage(summary);
    ArkApi::GetApiUtils().SendChatMessage(player,L"ARKLAND",L"{}",ArkApi::Tools::Utf8Decode(text).c_str());
}
void RconStatus(RCONClientConnection* connection,RCONPacket* packet,UWorld*){
    const auto text=ArkApi::Tools::Utf8Decode(Status(false).dump());FString response(text.c_str());
    connection->SendMessageW(packet->Id,0,&response);
}
}
void StartLiveInventory(const PluginConfiguration& config,DurableOutbox& outbox){
    configuration=config;inventory=ObservedInventory();
    supplyClass=APrimalStructureItemContainer_SupplyCrate::GetPrivateStaticClass(nullptr);
    journal=std::make_unique<InventoryJournal>(outbox,config.localSnapshotFile.parent_path()/"observed-inventory.json");
    installed=true;runtimeHealthy=true;acceptingEvents=true;
    ArkApi::GetCommands().AddOnTickCallback("StructureLimitsLiveInventory",&Tick);
    ArkApi::GetCommands().AddChatCommand(L"/limites",&ShowLimits);
    ArkApi::GetCommands().AddRconCommand(L"StructureLimits.Status",&RconStatus);
    scanning=false;scans=0;nextScan={};nextPublish={};dirty=true;
    Log::GetLog()->info("StructureLimits 0.8-dev: live ledger, completed placement, destruction, GPS, asynchronous journal and /limites active; enforcement=false");
}
void StopLiveInventory(){
    acceptingEvents=false;
    if(installed){ArkApi::GetCommands().RemoveOnTickCallback("StructureLimitsLiveInventory");
        ArkApi::GetCommands().RemoveChatCommand(L"/limites");ArkApi::GetCommands().RemoveRconCommand(L"StructureLimits.Status");installed=false;}
    if(journal)journal->State(Status(false));
    journal.reset();inventory=ObservedInventory();scanIds.clear();teamTribes.clear();playerSteam.clear();
}
void SuspendLiveInventory(){acceptingEvents=false;}
void ObserveCompletedPlacement(APrimalStructure* structure,APlayerController* player){
    if(!journal||!acceptingEvents||!Ready())return;
    RefreshOwners();auto value=Capture(structure);if(!value)return;value->placementConfirmed=true;
    const auto prior=inventory.Records().find(value->id);
    const bool alreadyConfirmed=prior!=inventory.Records().end()&&prior->second.placementConfirmed;
    const auto change=inventory.Observe(*value);
    if(change!=ObservedInventory::Change::Added&&change!=ObservedInventory::Change::Updated)return;
    journal->Record(value->id,Record(inventory.Records().at(value->id)));
    dirty=true;if(alreadyConfirmed)return;
    auto event=Record(*value);event["type"]="placement_confirmed";event["instance"]=configuration.Identity().displayId;
    if(player&&player->IsA(AShooterPlayerController::GetPrivateStaticClass()))
        event["actor_steam_id"]=std::to_string(ArkApi::GetApiUtils().GetSteamIdFromController(static_cast<AShooterPlayerController*>(player)));
    journal->Event(std::move(event));dirty=true;
    Log::GetLog()->info("StructureLimits inventory: placed id={} observed={} lat={} lon={}",value->id,inventory.Records().size(),value->latitude,value->longitude);
}
void ObserveLiveDestruction(APrimalStructure* structure){
    if(!journal||!acceptingEvents||!Ready())return;
    auto value=Capture(structure,true);if(!value)return;
    const auto existing=inventory.Records().find(value->id);
    if(existing!=inventory.Records().end()&&existing->second.blueprint!=value->blueprint)return;
    const auto prior=inventory.Remove(value->id);
    // An untracked destruction cannot subtract another structure's count.
    auto event=Record(prior?*prior:*value);event["type"]=prior?"removed":"untracked_destruction";
    event["removal_cause"]="unspecified";event["instance"]=configuration.Identity().displayId;
    if(prior){journal->Record(value->id,nullptr);journal->Event(std::move(event));dirty=true;
        Log::GetLog()->info("StructureLimits inventory: removed id={} observed={} lat={} lon={} cause=unspecified",value->id,inventory.Records().size(),value->latitude,value->longitude);}
}
}
