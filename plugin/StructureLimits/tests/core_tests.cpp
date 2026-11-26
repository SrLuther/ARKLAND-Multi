#include "StructureLimitsCore.h"
#include "DurableOutbox.h"
#include "StructureLimitsConfig.h"
#include "LocalSnapshotStore.h"
#include "OutboxSynchronizer.h"
#include "ObservedInventory.h"
#include "InventoryJournal.h"

#include <atomic>
#include <chrono>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <thread>
#include <vector>

using namespace StructureLimits;

namespace {

MapIdentity Map() {
    return MakeMapIdentity("Ragnarok", "E:/Mapas/04/");
}

std::unique_ptr<LimitEngine> ReadyEngine(Configuration config,
                        std::vector<ExistingStructure> structures = {}) {
    auto engine = std::make_unique<LimitEngine>(std::move(config), Map());
    WorldSnapshot snapshot{Map(), true, true, true, std::move(structures)};
    std::string error;
    assert(engine->ActivateFromSnapshot(snapshot, &error));
    assert(error.empty());
    return engine;
}

void TestExtraRoundingAndValidation() {
    Configuration config{11, 25, {{"bp/generator", 1}}};
    assert(config.GlobalExtra() == 3);
    assert(config.SpecificExtra(1) == 1);
    config.globalPrimary = 0;
    bool threw = false;
    try { config.Validate(); } catch (...) { threw = true; }
    assert(threw);
}

void TestConfigurationParsingAndFailSafeValidation() {
    const auto disabled = ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":false,"LPG":0,"ExtraPercentage":25}})");
    assert(!disabled.enabled);

    const auto enabled = ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":true,"MapName":"Ragnarok","InstancePath":"E:/Mapas/04","LPG":100,"ExtraPercentage":25,"SpecificBlueprints":[{"Blueprint":"bp/gen","LEG":10}],"EnforcementRequiresValidatedInventory":true,"LocalSnapshotFile":"E:/Backups/StructureLimits/04/snapshot.json","LocalOutboxDirectory":"E:/Backups/StructureLimits/04/outbox"}})");
    assert(enabled.enabled);
    assert(enabled.limits.GlobalExtra() == 25);
    assert(enabled.limits.SpecificExtra(10) == 3);
    assert(enabled.Identity().displayId == "08RAG04");

    bool rejected = false;
    try {
        (void)ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":true,"MapName":"Ragnarok","InstancePath":"E:/Mapas/04","LPG":100,"LocalOutboxDirectory":"E:/outbox"}})");
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    rejected = false;
    try {
        (void)ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":true,"MapName":"Ragnarok","InstancePath":"E:/Mapas/04","LPG":100,"SpecificBlueprints":[{"Blueprint":"bp/gen","LEG":10},{"Blueprint":"bp/gen","LEG":20}],"LocalSnapshotFile":"E:/snapshot.json","LocalOutboxDirectory":"E:/outbox"}})");
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    rejected = false;
    try {
        (void)ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":true,"MapName":"Ragnarok","InstancePath":"E:/Mapas/04","LPG":100,"EnforcementRequiresValidatedInventory":false,"LocalSnapshotFile":"E:/snapshot.json","LocalOutboxDirectory":"E:/outbox"}})");
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    rejected = false;
    try {
        (void)ParsePluginConfiguration(R"({"StructureLimits":{"Enabled":true,"MapName":"Ragnarok","InstancePath":"Mapas/04","LPG":100,"LocalSnapshotFile":"E:/snapshot.json","LocalOutboxDirectory":"E:/outbox"}})");
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
}

void TestMapIdentity() {
    const auto ragnarok = MakeMapIdentity("Ragnarok", "E:/Mapas/04/");
    const auto island = MakeMapIdentity("The Island", "E:/Mapas/05");
    assert(ragnarok.displayId == "08RAG04");
    assert(island.displayId == "09THE05");
    assert(ragnarok.canonicalInstancePath == "e:\\mapas\\04");
    const auto otherInstance = MakeMapIdentity("Ragnarok", "e:/MAPAS/05");
    assert(otherInstance.displayId == "08RAG05");
    assert(otherInstance.canonicalInstancePath != ragnarok.canonicalInstancePath);
    const auto normalized = MakeMapIdentity("Ragnarok", "E:/Mapas/04/../04/.");
    assert(normalized.canonicalInstancePath == ragnarok.canonicalInstancePath);
}

void TestIncompleteSnapshotFailsOpen() {
    auto engine = std::make_unique<LimitEngine>(Configuration{1, 0, {}}, Map());
    WorldSnapshot incomplete{Map(), false, false, false, {}};
    std::string error;
    assert(!engine->ActivateFromSnapshot(incomplete, &error));
    assert(!error.empty());
    assert(!engine->IsEnforcing());
    const auto decision = engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(decision.state == PlacementState::BypassEnforcement);
}

void TestMismatchedInstanceCannotActivate() {
    auto engine = std::make_unique<LimitEngine>(Configuration{1, 0, {}}, Map());
    const auto otherMap = MakeMapIdentity("Ragnarok", "E:/Mapas/05");
    WorldSnapshot snapshot{otherMap, true, true, true, {}};
    std::string error;
    assert(!engine->ActivateFromSnapshot(snapshot, &error));
    assert(!engine->IsEnforcing());
    assert(error.find("different map instance") != std::string::npos);
}

void TestUnprovenPlacementHookCannotActivateEnforcement() {
    auto engine = std::make_unique<LimitEngine>(Configuration{1, 0, {}}, Map());
    WorldSnapshot snapshot{Map(), true, true, false, {}};
    std::string error;
    assert(!engine->ActivateFromSnapshot(snapshot, &error));
    assert(error.find("hook safety") != std::string::npos);
    assert(engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100).state ==
           PlacementState::BypassEnforcement);
}

void TestGlobalCapAndReservationRelease() {
    auto engine = ReadyEngine(Configuration{1, 0, {}});
    const auto first = engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(first.state == PlacementState::Reserved);
    const auto second = engine->ReservePlacement("tribe-a", "steam-b", "bp/door", 100);
    assert(second.state == PlacementState::Denied);
    assert(engine->CancelPlacement(first.reservationId));
    const auto retry = engine->ReservePlacement("tribe-a", "steam-b", "bp/door", 100);
    assert(retry.state == PlacementState::Reserved);
    assert(engine->CommitPlacement(retry.reservationId, "structure-1"));
    assert(!engine->CommitPlacement(retry.reservationId, "structure-2"));
    assert(engine->ReleaseStructure("structure-1"));
    assert(!engine->ReleaseStructure("structure-1"));
}

void TestExtraCapacityIsSharedAcrossLicensedPlayers() {
    auto engine = ReadyEngine(Configuration{1, 100, {}}, {
        {"primary", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"}
    });
    engine->PutLicense("steam-a", 1000);
    engine->PutLicense("steam-b", 1000);
    auto first = engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(first.state == PlacementState::Reserved && first.usesGlobalExtra);
    assert(engine->CommitPlacement(first.reservationId, "extra-1"));
    auto second = engine->ReservePlacement("tribe-a", "steam-b", "bp/wall", 100);
    assert(second.state == PlacementState::Denied);
}

void TestSpecificAndCrossDimensionLicense() {
    auto engine = ReadyEngine(Configuration{3, 50, {{"bp/gen", 1}}}, {
        {"s1", Owner::ForPlayer("tribe-a", "steam-a"), "bp/gen"},
        {"s2", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"}
    });
    auto denied = engine->ReservePlacement("tribe-a", "steam-a", "bp/gen", 100);
    assert(denied.state == PlacementState::Denied);
    assert(denied.usesSpecificExtra);
    engine->PutLicense("steam-a", 101);
    auto allowed = engine->ReservePlacement("tribe-a", "steam-a", "bp/gen", 100);
    assert(allowed.state == PlacementState::Reserved);
    assert(allowed.usesSpecificExtra && !allowed.usesGlobalExtra);
    assert(engine->CancelPlacement(allowed.reservationId));

    auto globalEngine = ReadyEngine(Configuration{2, 50, {{"bp/gen", 1}}}, {
        {"g1", Owner::ForPlayer("tribe-a", "steam-a"), "bp/gen"},
        {"g2", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"}
    });
    globalEngine->PutLicense("steam-a", 101);
    auto globalExtra = globalEngine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(globalExtra.state == PlacementState::Reserved);
    assert(globalExtra.usesGlobalExtra && !globalExtra.usesSpecificExtra);
}

void TestLicenseRenewalIsCumulative() {
    auto engine = ReadyEngine(Configuration{1, 0, {}});
    constexpr std::int64_t day = 24 * 60 * 60;
    engine->PutLicense("steam-a", 2 * day);
    assert(engine->RenewLicense("steam-a", 0) == 32 * day);
    assert(engine->HasActiveLicense("steam-a", 31 * day));
    assert(!engine->HasActiveLicense("steam-a", 32 * day));
}

void TestSoloPlayerGetsIndependentOwner() {
    auto engine = ReadyEngine(Configuration{1, 0, {}});
    auto one = engine->ReservePlacement("", "steam-one", "bp/wall", 100);
    assert(one.state == PlacementState::Reserved);
    assert(engine->CommitPlacement(one.reservationId, "solo-structure"));
    const auto own = engine->GetSummary("", "steam-one");
    const auto other = engine->GetSummary("", "steam-two");
    assert(own.globalUsed == 1);
    assert(other.globalUsed == 0);
}

void TestOwnershipReassignmentMovesCountsExactlyOnce() {
    auto engine = ReadyEngine(Configuration{5, 25, {{"bp/gen", 2}}}, {
        {"placed", Owner::ForPlayer("tribe-a", "steam-a"), "bp/gen"}
    });
    assert(engine->ReassignStructure("placed", Owner::ForPlayer("tribe-b", "steam-b")));
    assert(engine->GetSummary("tribe-a", "steam-a").globalUsed == 0);
    assert(engine->GetSummary("tribe-b", "steam-b").globalUsed == 1);
    assert(engine->GetSummary("tribe-b", "steam-b").specific.front().used == 1);
    assert(engine->ReassignStructure("placed", Owner::ForPlayer("tribe-b", "steam-c")));
    assert(engine->GetSummary("tribe-b", "steam-c").globalUsed == 1);
}

void TestLoweredLimitsPreserveExistingStructures() {
    auto engine = ReadyEngine(Configuration{1, 0, {}}, {
        {"old-1", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"},
        {"old-2", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"}
    });
    assert(engine->GetSummary("tribe-a", "steam-a").globalUsed == 2);
    const auto denied = engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(denied.state == PlacementState::Denied);
    assert(engine->GetSummary("tribe-a", "steam-a").globalUsed == 2);
}

void TestSuspendingEnforcementPreservesInflightReservation() {
    auto engine = ReadyEngine(Configuration{1, 0, {}});
    const auto reservation = engine->ReservePlacement("tribe-a", "steam-a", "bp/wall", 100);
    assert(reservation.state == PlacementState::Reserved);
    engine->SuspendEnforcement();
    assert(engine->CommitPlacement(reservation.reservationId, "inflight"));
    assert(engine->GetSummary("tribe-a", "steam-a").globalUsed == 1);
    assert(engine->ReservePlacement("tribe-a", "steam-b", "bp/wall", 100).state ==
           PlacementState::BypassEnforcement);
}

void TestChatSummaryShowsPrimaryOnly() {
    LimitsSummary summary{7, 10, 3, {{"bp/generator", 2, 4, 2}}};
    const auto message = FormatPrimaryLimitsMessage(summary);
    assert(message.find("LPG: 7/10") != std::string::npos);
    assert(message.find("LEG bp/generator: 2/4") != std::string::npos);
    assert(message.find("LPE:") == std::string::npos);
    assert(message.find("LEE:") == std::string::npos);
}

void TestTribeMergeUsesOnlyGlobalCombinedLimit() {
    auto engine = ReadyEngine(Configuration{5, 25, {{"bp/gen", 1}}}, {
        {"a1", Owner::ForPlayer("a", "steam-a"), "bp/gen"},
        {"a2", Owner::ForPlayer("a", "steam-a"), "bp/gen"},
        {"a3", Owner::ForPlayer("a", "steam-a"), "bp/gen"},
        {"b1", Owner::ForPlayer("b", "steam-b"), "bp/gen"},
        {"b2", Owner::ForPlayer("b", "steam-b"), "bp/gen"},
        {"b3", Owner::ForPlayer("b", "steam-b"), "bp/gen"}
    });
    assert(engine->CanMergeTribes("a", "b")); // 6 <= ceil(5 + 25%)
    auto larger = ReadyEngine(Configuration{5, 25, {}}, {
        {"a1", Owner::ForPlayer("a", "steam-a"), "bp/wall"},
        {"a2", Owner::ForPlayer("a", "steam-a"), "bp/wall"},
        {"a3", Owner::ForPlayer("a", "steam-a"), "bp/wall"},
        {"a4", Owner::ForPlayer("a", "steam-a"), "bp/wall"},
        {"a5", Owner::ForPlayer("a", "steam-a"), "bp/wall"},
        {"b1", Owner::ForPlayer("b", "steam-b"), "bp/wall"},
        {"b2", Owner::ForPlayer("b", "steam-b"), "bp/wall"},
        {"b3", Owner::ForPlayer("b", "steam-b"), "bp/wall"}
    });
    assert(!larger->CanMergeTribes("a", "b"));
}

void TestConcurrentReservationsCannotOverbookPrimaryCap() {
    auto engine = ReadyEngine(Configuration{1, 0, {}});
    std::atomic<int> reserved{0};
    std::vector<std::thread> workers;
    for (int i = 0; i < 24; ++i) {
        workers.emplace_back([&, i] {
            auto decision = engine->ReservePlacement("tribe-a",
                "steam-" + std::to_string(i), "bp/wall", 100);
            if (decision.state == PlacementState::Reserved) ++reserved;
        });
    }
    for (auto& worker : workers) worker.join();
    assert(reserved.load() == 1);
}

void TestOutboxIdempotencyAndAcknowledgement() {
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto path = std::filesystem::temp_directory_path() /
        ("arkland-structure-limits-test-outbox-" + std::to_string(nonce));
    std::error_code ec;
    DurableOutbox outbox(path);
    outbox.Initialize();
    std::string error;
    assert(outbox.Enqueue("event_1", "{\"type\":\"placed\"}", &error));
    assert(outbox.Enqueue("event_1", "{\"type\":\"placed\"}", &error));
    assert(!outbox.Enqueue("event_1", "{\"type\":\"destroyed\"}", &error));
    assert(!outbox.Enqueue("../escape", "{}", &error));
    DurableOutbox afterRestart(path);
    const auto restoredPending = afterRestart.Pending(&error);
    assert(restoredPending.size() == 1 && restoredPending.front().eventId == "event_1");
    auto pending = outbox.Pending(&error);
    assert(pending.size() == 1 && pending.front().eventId == "event_1");
    assert(outbox.Acknowledge("event_1", &error));
    assert(outbox.Pending(&error).empty());
    { std::ofstream orphan(path / "orphan.tmp", std::ios::binary); orphan << "partial"; }
    assert(outbox.Pending(&error).empty());
    assert(error.find("interrupted temporary") != std::string::npos);
    std::filesystem::remove_all(path, ec);
}

void TestLocalSnapshotCandidateNeverEnablesEnforcement() {
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto path = std::filesystem::temp_directory_path() /
        ("arkland-structure-limits-test-snapshot-" + std::to_string(nonce)) /
        "world.snapshot.json";
    std::error_code ec;
    const auto map = Map();
    LocalSnapshotStore store(path, map);
    WorldSnapshot snapshot{map, true, true, true, {
        {"structure-1", Owner::ForPlayer("tribe-a", "steam-a"), "bp/wall"},
        {"structure-2", Owner::ForPlayer("tribe-a", "steam-b"), "bp/gen"}
    }};
    std::string error;
    assert(store.Save(snapshot, &error));
    auto loaded = store.LoadCandidate();
    assert(loaded.found && loaded.usable && loaded.candidate.structures.size() == 2);
    assert(!loaded.candidate.complete && !loaded.candidate.validated &&
           !loaded.candidate.placementHookValidated);
    LimitEngine engine(Configuration{100, 25, {}}, map);
    assert(!engine.ActivateFromSnapshot(loaded.candidate, &error));
    assert(!engine.IsEnforcing());

    WorldSnapshot incomplete{map, false, false, false, snapshot.structures};
    assert(!store.Save(incomplete, &error));
    const auto wrongMapPath = MakeMapIdentity("Ragnarok", "E:/Mapas/05");
    LocalSnapshotStore wrongMapStore(path, wrongMapPath);
    assert(!wrongMapStore.LoadCandidate().usable);

    { std::ofstream output(path, std::ios::binary | std::ios::trunc); output << "broken"; }
    assert(!store.LoadCandidate().usable);
    std::filesystem::remove_all(path.parent_path(), ec);

    const auto orphanPath = std::filesystem::temp_directory_path() /
        ("arkland-structure-limits-test-orphan-" + std::to_string(nonce)) /
        "missing.snapshot.json";
    std::filesystem::create_directories(orphanPath.parent_path());
    { std::ofstream output(orphanPath.string() + ".1.tmp", std::ios::binary); output << "partial"; }
    const auto orphan = LocalSnapshotStore(orphanPath, map).LoadCandidate();
    assert(!orphan.found && orphan.interruptedWriteFound && !orphan.usable);
    std::filesystem::remove_all(orphanPath.parent_path(), ec);
}

void TestOutboxSynchronizerRetriesWithoutDroppingEvent() {
    const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
    const auto path = std::filesystem::temp_directory_path() /
        ("arkland-structure-limits-test-sync-" + std::to_string(nonce));
    std::error_code ec;
    DurableOutbox outbox(path);
    outbox.Initialize();
    std::string error;
    assert(outbox.Enqueue("retry_event", "{\"type\":\"placed\"}", &error));
    std::atomic<int> attempts{0};
    OutboxSynchronizer sync(outbox,
        [&attempts](const OutboxEvent& event, std::string& sendError) {
            assert(event.eventId == "retry_event");
            if (++attempts == 1) {
                sendError = "temporary sink failure";
                return false;
            }
            return true;
        }, std::chrono::milliseconds(10));
    assert(sync.Start(&error));
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (sync.DeliveredCount() == 0 && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    sync.Stop();
    assert(attempts >= 2 && sync.DeliveredCount() == 1);
    assert(outbox.Pending(&error).empty());
    std::filesystem::remove_all(path, ec);
}

} // namespace

void TestObservedLedgerIdempotencyAndPartialCoverage() {
    StructureLimits::ObservedInventory inventory;
    using Change=StructureLimits::ObservedInventory::Change;
    StructureLimits::ObservedStructure first;
    first.id="123";first.blueprint="/Game/Test/Foundation.Foundation_C";
    first.targetingTeam=50001;first.playerId=10;first.tribeId="50001";first.steamId="steam-a";
    first.hasCoordinates=true;first.latitude=52.5;first.longitude=42.1;
    assert(inventory.Observe(first)==Change::Added);
    assert(inventory.Observe(first)==Change::None);
    first.placementConfirmed=true;
    assert(inventory.Observe(first)==Change::Updated);
    assert(inventory.Records().size()==1);
    const Configuration config{100,25,{}};
    assert(inventory.Summary(Owner::ForPlayer("50001","steam-b"),config).globalUsed==1);
    assert(inventory.Summary(Owner::ForPlayer("other","steam-a"),config).globalUsed==0);
    auto partial=first;partial.id="234";partial.tribeId="other";
    assert(inventory.Observe(partial)==Change::Added);
    // A later partial scan does not erase the original structure.
    assert(inventory.Observe(partial)==Change::None);
    assert(inventory.Records().size()==2);
    auto removed=inventory.Remove("123");assert(removed&&removed->latitude==52.5);
    assert(!inventory.Remove("123"));
    assert(inventory.Records().size()==1&&inventory.RemovedCount()==1);
    assert(inventory.Observe(first)==Change::Tombstoned);
    assert(inventory.Summary(Owner::ForPlayer("50001","steam-a"),config).globalUsed==0);
}

void TestObservedLedgerOwnershipAndConflict() {
    StructureLimits::ObservedInventory inventory;
    using Change=StructureLimits::ObservedInventory::Change;
    StructureLimits::ObservedStructure value;
    value.id="1";value.blueprint="bp/wall";value.targetingTeam=400;value.playerId=10;
    value.steamId="solo-a";
    assert(inventory.Observe(value)==Change::Added);
    Configuration config{100,25,{}};
    assert(inventory.Summary(Owner::ForPlayer("","solo-a"),config).globalUsed==1);
    assert(inventory.Summary(Owner::ForPlayer("","solo-b"),config).globalUsed==0);
    auto changed=value;changed.targetingTeam=50002;changed.steamId.clear();
    assert(inventory.Observe(changed)==Change::Updated);
    assert(inventory.Summary(Owner::ForPlayer("","solo-a"),config).globalUsed==0);
    changed.tribeId="50002";
    assert(inventory.Observe(changed)==Change::Updated);
    assert(inventory.Summary(Owner::ForPlayer("50002","solo-b"),config).globalUsed==1);
    changed.blueprint="bp/door";
    assert(inventory.Observe(changed)==Change::Conflict&&inventory.Conflicts()==1);
    assert(inventory.Records().at("1").blueprint==NormalizeBlueprintKey("bp/wall"));
    changed.id="0";assert(inventory.Observe(changed)==Change::Invalid);
}

void TestAsynchronousInventoryJournal() {
    const auto path=std::filesystem::temp_directory_path()/("arkland-inventory-journal-test-"+
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    DurableOutbox outbox(path);outbox.Initialize();
    {
        InventoryJournal journal(outbox,path/"observed-inventory.json");
        assert(journal.Event({{"type","placement_confirmed"},{"structure_id","123"}}));
        assert(journal.Event({{"type","removed"},{"structure_id","123"}}));
        journal.Record("123",{{"structure_id","123"},{"latitude",52.5}});
        journal.Record("123",nullptr);
        journal.Record("456",{{"structure_id","456"},{"latitude",42.3}});
        journal.State({{"complete_inventory",false},{"observed_structures",0}});
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
        while((journal.Pending()||!std::filesystem::exists(path/"observed-inventory.json"))&&std::chrono::steady_clock::now()<deadline)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        assert(journal.Healthy()&&journal.Pending()==0);
    }
    const auto pending=outbox.Pending();assert(pending.size()==2&&pending[0].eventId!=pending[1].eventId);
    assert(std::filesystem::exists(path/"observed-inventory.json"));
    {std::ifstream file(path/"observed-inventory.json");nlohmann::json state;file>>state;
        assert(state.at("structures").size()==1&&state.at("structures")[0].at("structure_id")=="456");}
    std::error_code ec;std::filesystem::remove_all(path,ec);
}

void TestObservedActorIdentityAndSources() {
    StructureLimits::ObservedInventory inventory;
    using Change=StructureLimits::ObservedInventory::Change;
    StructureLimits::ObservedStructure value;
    value.id="9";value.blueprint="bp/floor";value.targetingTeam=50001;
    value.actorName="Floor_C_1";value.actorFullName="Floor_C TheIsland.PersistentLevel.Floor_C_1";value.observedSources=1;
    assert(inventory.Observe(value)==Change::Added);
    value.observedSources=4;
    assert(inventory.Observe(value)==Change::Updated);
    assert(inventory.Records().at("9").observedSources==5);
    value.actorName.clear();value.actorFullName.clear();value.observedSources=0;
    assert(inventory.Observe(value)==Change::None);
    assert(inventory.Records().at("9").actorName=="Floor_C_1");
    value.actorName="Floor_C_2";value.actorFullName="Floor_C TheIsland.PersistentLevel.Floor_C_2";
    assert(inventory.Observe(value)==Change::Conflict);
    assert(inventory.Records().at("9").actorName=="Floor_C_1"&&inventory.Conflicts()==1);
}

int main() {
    TestObservedActorIdentityAndSources();
    TestAsynchronousInventoryJournal();
    TestObservedLedgerIdempotencyAndPartialCoverage();
    TestObservedLedgerOwnershipAndConflict();
    TestExtraRoundingAndValidation();
    TestConfigurationParsingAndFailSafeValidation();
    TestMapIdentity();
    TestIncompleteSnapshotFailsOpen();
    TestMismatchedInstanceCannotActivate();
    TestUnprovenPlacementHookCannotActivateEnforcement();
    TestGlobalCapAndReservationRelease();
    TestExtraCapacityIsSharedAcrossLicensedPlayers();
    TestSpecificAndCrossDimensionLicense();
    TestLicenseRenewalIsCumulative();
    TestSoloPlayerGetsIndependentOwner();
    TestOwnershipReassignmentMovesCountsExactlyOnce();
    TestLoweredLimitsPreserveExistingStructures();
    TestSuspendingEnforcementPreservesInflightReservation();
    TestChatSummaryShowsPrimaryOnly();
    TestTribeMergeUsesOnlyGlobalCombinedLimit();
    TestConcurrentReservationsCannotOverbookPrimaryCap();
    TestOutboxIdempotencyAndAcknowledgement();
    TestLocalSnapshotCandidateNeverEnablesEnforcement();
    TestOutboxSynchronizerRetriesWithoutDroppingEvent();
    std::cout << "StructureLimits core tests passed\n";
    return 0;
}
