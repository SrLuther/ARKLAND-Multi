#pragma once
#include "pch.h"

namespace FazendaRecursos::FarmSync {
struct RedemptionStack {
    std::string redemption_id;
    std::string resource_id;
    int stack_index = 0;
    int quantity = 0;
};

void Start();
void Stop();
void QueuePlayer(const std::string& steam_id);
void QueueCatalog();
bool SyncUploadedResourceNow(const std::string& steam_id, const std::string& upload_id);
bool ClaimRedemptionStacks(const std::string& steam_id, const std::string& server_id,
                          std::vector<RedemptionStack>& stacks);
bool CompleteRedemptionStack(const RedemptionStack& stack, const std::string& steam_id,
                             const std::string& server_id, bool delivered);
}
