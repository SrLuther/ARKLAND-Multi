#include "InventoryJournal.h"
#include <chrono>
#include <stdexcept>
#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#include <objbase.h>
#endif

namespace StructureLimits {
namespace {
void AtomicState(const std::filesystem::path& path,const std::string& text) {
#ifdef _WIN32
    const auto temp=std::filesystem::path(path.wstring()+L".tmp");
    HANDLE file=CreateFileW(temp.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE) throw std::runtime_error("Cannot create observed inventory state");
    DWORD written=0;
    const bool ok=text.size()<=MAXDWORD && WriteFile(file,text.data(),static_cast<DWORD>(text.size()),&written,nullptr) &&
        written==text.size() && FlushFileBuffers(file);
    CloseHandle(file);
    if(!ok || !MoveFileExW(temp.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error("Cannot publish observed inventory state");
#else
    throw std::runtime_error("Inventory journal requires Windows");
#endif
}
}
InventoryJournal::InventoryJournal(DurableOutbox& outbox,std::filesystem::path stateFile):outbox_(outbox),stateFile_(std::move(stateFile)) {
#ifdef _WIN32
    GUID guid{};if(FAILED(CoCreateGuid(&guid)))throw std::runtime_error("Cannot create inventory boot ID");
    wchar_t value[40]{};StringFromGUID2(guid,value,40);
    for(auto ch:std::wstring(value))if(ch!=L'{'&&ch!=L'}')boot_+=static_cast<char>(ch);
#endif
    thread_=std::thread(&InventoryJournal::Run,this);
}
InventoryJournal::~InventoryJournal(){
    {std::lock_guard lock(mutex_);stopping_=true;}wake_.notify_all();
    if(thread_.joinable())thread_.join();
}
bool InventoryJournal::Event(nlohmann::json payload){
    std::lock_guard lock(mutex_);
    if(events_.size()>=4096){healthy_=false;return false;}
    const auto id=boot_+"-"+std::to_string(++sequence_);
    payload["event_id"]=id;
    payload["occurred_at_unix"]=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    events_.push_back({id,payload.dump()});wake_.notify_all();return true;
}
void InventoryJournal::State(nlohmann::json payload){std::lock_guard lock(mutex_);state_=std::move(payload);wake_.notify_all();}
void InventoryJournal::Record(const std::string& id,nlohmann::json payload,std::uint64_t inventoryRevision){
    std::lock_guard lock(mutex_);
    if(recordUpdates_.size()>=16384&&!recordUpdates_.count(id)){healthy_=false;return;}
    recordUpdates_[id]={std::move(payload),inventoryRevision};wake_.notify_all();
}
std::size_t InventoryJournal::Pending()const{std::lock_guard lock(mutex_);return events_.size();}
void InventoryJournal::Run(){
    std::map<std::string,nlohmann::json> records;
    std::uint64_t appliedRevision=0;
    for(;;){
        std::optional<OutboxEvent> event;std::optional<nlohmann::json> state;bool stopping;
        std::map<std::string,RecordUpdate> updates;
        {std::unique_lock lock(mutex_);wake_.wait(lock,[&]{return stopping_||!events_.empty()||state_.has_value()||!recordUpdates_.empty();});
         stopping=stopping_;if(!events_.empty())event=events_.front();if(state_)state=std::move(state_);state_.reset();updates.swap(recordUpdates_);}
        bool success=true;
        try{
            for(auto& [id,value]:updates){
                if(value.payload.is_null())records.erase(id);else records[id]=std::move(value.payload);
                if(value.revision>appliedRevision)appliedRevision=value.revision;
            }
            if(event){std::string error;if(!outbox_.Enqueue(event->eventId,event->payload,&error))throw std::runtime_error(error);
                std::lock_guard lock(mutex_);events_.pop_front();}
            if(state){(*state)["structures"]=nlohmann::json::array();
                (*state)["journal_applied_revision"]=appliedRevision;
                (*state)["journal_state_revision_match"]=state->value("inventory_revision",std::uint64_t(0))==appliedRevision;
                for(const auto& [id,value]:records)(*state)["structures"].push_back(value);
                AtomicState(stateFile_,state->dump());}
        }catch(...){success=false;healthy_=false;
            if(state){std::lock_guard lock(mutex_);if(!state_)state_=std::move(state);}}
        // On an unrecoverable disk failure do not hang Ark's shutdown forever.
        // The last durable state remains a candidate, never authoritative.
        if(stopping){std::lock_guard lock(mutex_);if(!success||(events_.empty()&&!state_&&recordUpdates_.empty()))break;}
        if(!success){std::unique_lock lock(mutex_);wake_.wait_for(lock,std::chrono::seconds(2),[&]{return stopping_;});}
    }
}
}
