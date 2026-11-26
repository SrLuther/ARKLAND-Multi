#include "LiveInventoryRuntime.h"
#include "ObservedInventory.h"
#include <chrono>
#include <immintrin.h>
#include <unordered_map>
#include <array>

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
struct ScanReference { AActor* actor; unsigned sources; };
struct ClassEvidence { std::string blueprint, shortName; bool structure=false, supplyCrate=false; };
std::unordered_map<std::string,ScanReference> scanIds;
std::unordered_map<UClass*,ClassEvidence> classEvidence;
bool classCatalogOverflow=false;
std::array<std::size_t,3> sourceEntries{},sourceStructures{};
std::unordered_map<ULevel*,int> collectionSizes;
int initialLevelCount=0,priorStasisSize=-1;
std::size_t collectionMutations=0;
Json lastCompletedScan=nullptr;
std::map<std::string,Json> scanExcluded,lastExcluded;
bool exclusionOverflow=false;
MapCalibration gpsCalibration;
std::unordered_map<int,std::string> teamTribes,playerSteam;
std::chrono::steady_clock::time_point nextScan,nextPublish;
bool Ready(){return ArkApi::GetApiUtils().GetStatus()==ArkApi::ServerStatus::Ready;}
std::string Text(const FString& value){return value.IsEmpty()?"":value.ToString();}
std::string ShortName(const std::string& value){const auto split=value.find_last_of('.');return split==std::string::npos?value:value.substr(split+1);}
const ClassEvidence* Classify(AActor* actor){
    if(!actor||!actor->ClassField())return nullptr;
    auto* cls=actor->ClassField();const auto found=classEvidence.find(cls);if(found!=classEvidence.end())return &found->second;
    if(classEvidence.size()>=2048){classCatalogOverflow=true;return nullptr;}
    FString full;cls->GetFullName(&full,nullptr);const auto name=Text(full);
    ClassEvidence value{NormalizeBlueprintKey(name),ShortName(name),actor->IsA(APrimalStructure::GetPrivateStaticClass()),supplyClass&&actor->IsA(supplyClass)};
    return &classEvidence.emplace(cls,std::move(value)).first->second;
}
bool DeathCache(APrimalStructure* structure){
    if(!structure||!structure->IsA(APrimalStructureItemContainer::GetPrivateStaticClass()))return false;
    auto* container=static_cast<APrimalStructureItemContainer*>(structure);
    return IsGeneratedDeathCache(container->bUseDeathCacheCharacterID().Get(),static_cast<double>(container->DeathCacheCreationTimeField()));
}
Json Record(const ObservedStructure& record){
    Json result={{"structure_id",record.id},{"blueprint",record.blueprint},{"targeting_team",record.targetingTeam},
        {"player_data_id",static_cast<std::uint32_t>(record.playerId)},{"steam_id",record.steamId},{"tribe_id",record.tribeId},
        {"placement_confirmed",record.placementConfirmed},{"coordinates_available",record.hasCoordinates},
        {"actor_name",record.actorName},{"actor_full_name",record.actorFullName},{"observed_sources",record.observedSources}};
    if(record.hasCoordinates)result["position"]={{"x",record.x},{"y",record.y},{"z",record.z},{"latitude",record.latitude},{"longitude",record.longitude}};
    return result;
}
void RefreshOwners(){
    teamTribes.clear();playerSteam.clear();
    auto* world=ArkApi::GetApiUtils().GetWorld();
    if(auto* mode=static_cast<AShooterGameMode*>(world->AuthorityGameModeField())){
        // Read only the resident tribe registry; no profile loading or I/O in a callback.
        auto& tribes=*GetNativePointerField<TArray<FTribeData>*>(mode,"AShooterGameMode.TribesData");
        for(auto& entry:tribes){const int id=entry.TribeIDField();
            if(id>0)teamTribes[id]=std::to_string(id);}
    }
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
       (supplyClass&&structure->IsA(supplyClass))||DeathCache(structure))return std::nullopt;
    ObservedStructure value;value.id=std::to_string(structure->StructureIDField());
    value.targetingTeam=structure->TargetingTeamField();value.playerId=structure->OwningPlayerIDField();
    if(value.id=="0"||(!value.targetingTeam&&!value.playerId))return std::nullopt;
    if(const auto* type=Classify(structure))value.blueprint=type->blueprint;
    else {FString name;structure->ClassField()->GetFullName(&name,nullptr);value.blueprint=NormalizeBlueprintKey(Text(name));}
    FString actorName;structure->GetFullName(&actorName,nullptr);
    value.actorFullName=Text(actorName);value.actorName=ShortName(value.actorFullName);
    if(auto tribe=teamTribes.find(value.targetingTeam);tribe!=teamTribes.end())value.tribeId=tribe->second;
    if(auto player=playerSteam.find(value.playerId);player!=playerSteam.end())value.steamId=player->second;
    if(auto* root=structure->RootComponentField()){
        float xyz[4]{};_mm_storeu_ps(xyz,root->ComponentToWorldField().Translation);
        value.x=xyz[0];value.y=xyz[1];value.z=xyz[2];
        auto* world=ArkApi::GetApiUtils().GetWorld();
        if(world&&world->GetWorldSettings(false,true)){
            auto* settings=static_cast<APrimalWorldSettings*>(world->GetWorldSettings(false,true));
            gpsCalibration={settings->LatitudeScaleField(),settings->LongitudeScaleField(),settings->LatitudeOriginField(),settings->LongitudeOriginField()};
            if(const auto coords=PreciseMapPosition(xyz[0],xyz[1],gpsCalibration)){
                value.latitude=coords->latitude;value.longitude=coords->longitude;value.hasCoordinates=true;}
        }
    }
    return value;
}
Json Status(bool includeRecords,bool includeCatalog=false){
    Json state={{"format","arkland-structure-limits-observed-v2"},{"plugin_version","0.9.1-dev"},
        {"instance",configuration.Identity().displayId},{"canonical_instance_path",configuration.Identity().canonicalInstancePath},
        {"complete_inventory",false},{"enforcement",false},{"reason","resident_and_local_stasis_coverage_not_yet_validated"},
        {"observed_structures",inventory.Records().size()},{"removed_this_boot",inventory.RemovedCount()},
        {"identity_conflicts",inventory.Conflicts()},{"scan_duplicate_ids",duplicates},{"scan_in_progress",scanning},
        {"completed_scans",scans},{"actors_visited",scanned},{"excluded_actors",excluded},
        {"runtime_healthy",runtimeHealthy},{"journal_healthy",journal&&journal->Healthy()},{"journal_pending",journal?journal->Pending():0},
        {"last_completed_scan",lastCompletedScan},{"class_catalog_overflow",classCatalogOverflow},{"known_tribes",teamTribes.size()},
        {"excluded_identity_actors",lastExcluded.size()},{"excluded_identity_overflow",exclusionOverflow},
        {"updated_at_unix",std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()}};
    state["class_catalog_count"]=classEvidence.size();
    state["gps_calibration"]={{"latitude_scale",gpsCalibration.latitudeScale},{"longitude_scale",gpsCalibration.longitudeScale},
        {"latitude_origin",gpsCalibration.latitudeOrigin},{"longitude_origin",gpsCalibration.longitudeOrigin},{"rounded",false}};
    if(includeCatalog){state["class_catalog"]=Json::array();for(const auto& [cls,value]:classEvidence)
        state["class_catalog"].push_back({{"class_name",value.shortName},{"blueprint",value.blueprint},
            {"is_structure",value.structure},{"is_supply_crate",value.supplyCrate}});
        state["excluded_structure_actors"]=Json::array();for(const auto& [name,value]:lastExcluded)state["excluded_structure_actors"].push_back(value);}
    if(includeRecords){state["structures"]=Json::array();for(const auto& [id,value]:inventory.Records())state["structures"].push_back(Record(value));}
    return state;
}
void ScanActor(AActor* actor,unsigned source){
    ++scanned;++sourceEntries[source];Classify(actor);
    if(!actor||!actor->IsA(APrimalStructure::GetPrivateStaticClass()))return;
    auto record=Capture(static_cast<APrimalStructure*>(actor));
    if(!record){++excluded;
        auto* structure=static_cast<APrimalStructure*>(actor);
        const auto* type=Classify(actor);
        if(type&&!type->supplyCrate&&!structure->bIsPreviewStructure().Get()&&!structure->IsPendingKillPending()&&
            (DeathCache(structure)||!structure->StructureIDField()||(!structure->TargetingTeamField()&&!structure->OwningPlayerIDField()))){
            FString full;structure->GetFullName(&full,nullptr);const auto name=Text(full);
            if(scanExcluded.size()<4096||scanExcluded.count(name)){
                Json evidence={{"actor_name",ShortName(name)},{"actor_full_name",name},{"class_name",type->shortName},
                    {"blueprint",type->blueprint},{"structure_id",std::to_string(structure->StructureIDField())},
                    {"targeting_team",structure->TargetingTeamField()},{"player_data_id",static_cast<std::uint32_t>(structure->OwningPlayerIDField())},
                    {"net_startup",structure->bNetStartup().Get()},{"loaded_from_save",structure->bLoadedFromSaveGame().Get()},
                    {"reason",DeathCache(structure)?"generated_death_cache":!structure->StructureIDField()?"missing_structure_id":"missing_player_ownership"}};
                if(structure->IsA(APrimalStructureItemContainer::GetPrivateStaticClass())){
                    auto* container=static_cast<APrimalStructureItemContainer*>(structure);
                    evidence["death_cache_character_id_marker"]=container->bUseDeathCacheCharacterID().Get();
                    evidence["death_cache_creation_time"]=static_cast<double>(container->DeathCacheCreationTimeField());}
                if(auto* root=structure->RootComponentField()){float xyz[4]{};_mm_storeu_ps(xyz,root->ComponentToWorldField().Translation);
                    evidence["xyz"]={xyz[0],xyz[1],xyz[2]};}
                scanExcluded[name]=std::move(evidence);
            }else exclusionOverflow=true;
        }
        return;}
    const unsigned mask=1u<<source;record->observedSources=mask;
    const auto prior=scanIds.find(record->id);
    if(prior!=scanIds.end()){
        if(prior->second.actor!=actor){++duplicates;return;}
        if(!(prior->second.sources&mask)){++sourceStructures[source];prior->second.sources|=mask;}
    }else{scanIds.emplace(record->id,ScanReference{actor,mask});++sourceStructures[source];}
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
        sourceEntries={};sourceStructures={};collectionSizes.clear();collectionMutations=0;priorStasisSize=-1;scanExcluded.clear();
        initialLevelCount=GetNativePointerField<TArray<ULevel*>*>(world,"UWorld.Levels")->Num();
    }
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(2);
    for(int budget=0;scanning&&budget<512&&std::chrono::steady_clock::now()<deadline;++budget){
        if(stage==0){
            auto* level=world->PersistentLevelField();
            if(!level){stage=1;actorIndex=0;continue;}
            const auto& actors=*GetNativePointerField<TArray<AActor*>*>(level,"ULevelBase.Actors");
            auto [sizeIt,first]=collectionSizes.emplace(level,actors.Num());if(!first&&sizeIt->second!=actors.Num()){++collectionMutations;sizeIt->second=actors.Num();}
            if(actorIndex>=actors.Num()){stage=1;actorIndex=0;continue;}
            ScanActor(actors[actorIndex++],0);
        }else if(stage==1){
            const auto& levels=*GetNativePointerField<TArray<ULevel*>*>(world,"UWorld.Levels");
            if(levels.Num()!=initialLevelCount){++collectionMutations;initialLevelCount=levels.Num();}
            if(levelIndex>=levels.Num()){stage=2;actorIndex=0;continue;}
            auto* level=levels[levelIndex];
            if(!level||level==world->PersistentLevelField()){++levelIndex;actorIndex=0;continue;}
            const auto& actors=*GetNativePointerField<TArray<AActor*>*>(level,"ULevelBase.Actors");
            auto [sizeIt,first]=collectionSizes.emplace(level,actors.Num());if(!first&&sizeIt->second!=actors.Num()){++collectionMutations;sizeIt->second=actors.Num();}
            if(actorIndex>=actors.Num()){++levelIndex;actorIndex=0;continue;}
            ScanActor(actors[actorIndex++],1);
        }else{
            auto& stasis=world->LocalStasisActorsField();
            if(priorStasisSize>=0&&priorStasisSize!=stasis.Num())++collectionMutations;priorStasisSize=stasis.Num();
            if(actorIndex>=stasis.Num()){
                scanning=false;++scans;nextScan=now+std::chrono::seconds(30);dirty=true;
                lastExcluded=std::move(scanExcluded);
                lastCompletedScan={{"sequence",scans},{"unique_structures",scanIds.size()},
                    {"entries",sourceEntries},{"unique_structures_by_source",sourceStructures},
                    {"collection_mutations",collectionMutations},{"duplicate_ids",duplicates},
                    {"completed_at_unix",std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()}};
                Log::GetLog()->info("StructureLimits inventory: observed={} scans={} visited={} excluded={} duplicate_ids={} complete=false enforcement=false",inventory.Records().size(),scans,scanned,excluded,duplicates);
                break;
            }
            ScanActor(stasis[actorIndex++].Get(),2);
        }
    }
    if(dirty&&now>=nextPublish){journal->State(Status(false,true));dirty=false;nextPublish=now+std::chrono::seconds(5);}
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
    scanning=false;scans=0;nextScan={};nextPublish={};dirty=true;lastCompletedScan=nullptr;
    classEvidence.clear();classCatalogOverflow=false;scanExcluded.clear();lastExcluded.clear();exclusionOverflow=false;
    Log::GetLog()->info("StructureLimits 0.9.1-dev: native death-cache markers excluded, precise map GPS, observed census active; enforcement=false");
}
void StopLiveInventory(){
    acceptingEvents=false;
    if(installed){ArkApi::GetCommands().RemoveOnTickCallback("StructureLimitsLiveInventory");
        ArkApi::GetCommands().RemoveChatCommand(L"/limites");ArkApi::GetCommands().RemoveRconCommand(L"StructureLimits.Status");installed=false;}
    if(journal)journal->State(Status(false,true));
    journal.reset();inventory=ObservedInventory();scanIds.clear();teamTribes.clear();playerSteam.clear();classEvidence.clear();collectionSizes.clear();scanExcluded.clear();lastExcluded.clear();
}
void SuspendLiveInventory(){acceptingEvents=false;}
void ObserveCompletedPlacement(APrimalStructure* structure,APlayerController* player){
    if(!journal||!acceptingEvents||!Ready())return;
    RefreshOwners();auto value=Capture(structure);if(!value)return;value->placementConfirmed=true;value->observedSources=8;
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
