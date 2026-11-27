#ifdef _WIN32
#define NOMINMAX
#include <Windows.h>
#include <bcrypt.h>
#endif
#include "OwnerDirectory.h"
#include <json.hpp>
#include <fstream>
#include <sstream>
#include <regex>
#include <set>
#include <chrono>
#include <array>
#include <stdexcept>

namespace StructureLimits {
namespace {
using Json=nlohmann::json;
std::filesystem::path Utf8Path(const std::string& text){
    std::u8string encoded;for(unsigned char c:text)encoded.push_back(static_cast<char8_t>(c));return std::filesystem::path(encoded);
}
std::uint32_t Id(const Json& value){
    if(!value.is_number_integer()||value.is_boolean())throw std::invalid_argument("owner_id_type");
    auto n=value.get<std::int64_t>();if(n<=0||n>=0xffffffffLL)throw std::invalid_argument("owner_id_range");
    return static_cast<std::uint32_t>(n);
}
std::string DigestFile(const std::filesystem::path& path,std::uint64_t expected){
#ifdef _WIN32
    if(!expected||expected>8*1024*1024||std::filesystem::file_size(path)!=expected)throw std::runtime_error("source_size");
    const auto before=std::filesystem::last_write_time(path);
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("hash_provider");
    std::string result;
    std::vector<unsigned char> object;
    try{
        DWORD length=0,used=0;if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&length),sizeof(length),&used,0)<0)throw std::runtime_error("hash_size");
        object.resize(length);std::array<unsigned char,32> digest{};
        if(BCryptCreateHash(algorithm,&hash,object.data(),length,nullptr,0,0)<0)throw std::runtime_error("hash_create");
        std::ifstream stream(path,std::ios::binary);if(!stream)throw std::runtime_error("source_open");
        std::array<char,65536> buffer{};std::uint64_t total=0;
        while(stream){stream.read(buffer.data(),buffer.size());auto count=stream.gcount();total+=count;
            if(total>expected)throw std::runtime_error("source_changed");
            if(count&&BCryptHashData(hash,reinterpret_cast<PUCHAR>(buffer.data()),static_cast<ULONG>(count),0)<0)throw std::runtime_error("hash_update");}
        if(!stream.eof()||total!=expected||std::filesystem::file_size(path)!=expected||std::filesystem::last_write_time(path)!=before)throw std::runtime_error("source_changed");
        if(BCryptFinishHash(hash,digest.data(),static_cast<ULONG>(digest.size()),0)<0)throw std::runtime_error("hash_finish");
        const char* hex="0123456789abcdef";for(auto byte:digest){result+=hex[byte>>4];result+=hex[byte&15];}
    }catch(...){if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);throw;}
    BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);return result;
#else
    throw std::runtime_error("native_owner_verification_requires_windows");
#endif
}
}

OwnerDirectory ParseOwnerDirectory(const std::string& text,const MapIdentity& expected){
    if(text.size()>2*1024*1024)throw std::invalid_argument("owner_index_size");
    std::vector<std::set<std::string>> keys;bool duplicate=false;
    auto root=Json::parse(text,[&](int,Json::parse_event_t event,Json& parsed){
        if(event==Json::parse_event_t::object_start)keys.emplace_back();
        else if(event==Json::parse_event_t::key&&!keys.back().insert(parsed.get<std::string>()).second)duplicate=true;
        else if(event==Json::parse_event_t::object_end)keys.pop_back();return true;});
    if(duplicate||root.at("format")!="arkland-owner-directory-v1"||root.at("instance")!=expected.displayId||
       root.at("canonical_instance_path")!=expected.canonicalInstancePath||root.at("enforcement_authority")!=false||
       root.at("parser_commit")!="1d9a3e2b1a8052fdfc187174edfc920ca53216f3")
        throw std::invalid_argument("owner_index_scope");
    OwnerDirectory result;result.state="pending_sources";result.savedDirectory=root.at("saved_directory").get<std::string>();
    if(!std::regex_match(result.savedDirectory,std::regex("[A-Za-z0-9_-]{1,64}")))throw std::invalid_argument("owner_source_directory");
    if(!root.at("sources").is_array()||root.at("sources").size()>1024)throw std::invalid_argument("owner_source_count");
    std::set<std::string> names;std::uint64_t bytes=0;
    for(const auto& source:root.at("sources")){
        OwnerSource s{source.at("name").get<std::string>(),source.at("sha256").get<std::string>(),source.at("bytes").get<std::uint64_t>()};
        if(!std::regex_match(s.name,std::regex("[0-9]{1,20}\\.(arktribe|arkprofile)"))||
           !std::regex_match(s.sha256,std::regex("[0-9a-f]{64}"))||!s.bytes||s.bytes>8*1024*1024||!names.insert(s.name).second)
            throw std::invalid_argument("owner_source_invalid");
        bytes+=s.bytes;if(bytes>64*1024*1024)throw std::invalid_argument("owner_sources_size");result.sources.push_back(std::move(s));
    }
    if(!root.at("tribes").is_array()||root.at("tribes").size()>4096||!root.at("solos").is_array()||root.at("solos").size()>4096)
        throw std::invalid_argument("owner_count");
    for(const auto& tribe:root.at("tribes")){
        auto id=Id(tribe.at("tribe_id"));auto source=tribe.at("source").get<std::string>();
        if(source!=std::to_string(id)+".arktribe"||!names.count(source)||!result.tribes.emplace(id,std::to_string(id)).second)
            throw std::invalid_argument("tribe_source_mismatch");
    }
    for(const auto& solo:root.at("solos")){
        auto id=Id(solo.at("player_data_id"));auto steam=solo.at("steam_id").get<std::string>();auto source=solo.at("source").get<std::string>();
        if(!std::regex_match(steam,std::regex("7656119[0-9]{10}"))||source!=steam+".arkprofile"||!names.count(source)||solo.at("raw_tribe_id")!=0||
           result.tribes.count(id)||!result.solos.emplace(id,steam).second)throw std::invalid_argument("solo_source_mismatch");
    }
    return result;
}

bool VerifyOwnerSources(OwnerDirectory& directory,const std::function<bool(const OwnerSource&)>& verify){
    directory.valid=false;
    for(const auto& source:directory.sources)if(!verify(source)){
        directory.state="source_changed";directory.tribes.clear();directory.solos.clear();return false;}
    directory.valid=true;directory.state="verified";return true;
}

OwnerDirectoryStore::OwnerDirectoryStore(std::filesystem::path index,MapIdentity identity):index_(std::move(index)),identity_(std::move(identity)),current_(std::make_shared<OwnerDirectory>()){
    if(!index_.empty()){auto loading=std::make_shared<OwnerDirectory>();loading->state="loading";current_=loading;worker_=std::thread(&OwnerDirectoryStore::Run,this);}
}
OwnerDirectoryStore::~OwnerDirectoryStore(){
    {std::lock_guard<std::mutex> lock(mutex_);stopping_=true;}wake_.notify_all();if(worker_.joinable())worker_.join();
}
std::shared_ptr<const OwnerDirectory> OwnerDirectoryStore::Snapshot()const{std::lock_guard<std::mutex> lock(mutex_);return current_;}
void OwnerDirectoryStore::Run(){
    for(;;){
        auto result=std::make_shared<OwnerDirectory>();result->state="unavailable";
        try{
            auto size=std::filesystem::file_size(index_);if(!size||size>2*1024*1024)throw std::runtime_error("index_size");
            auto before=std::filesystem::last_write_time(index_);
            std::ifstream input(index_,std::ios::binary);std::string text(static_cast<std::size_t>(size),'\0');
            if(!input.read(text.data(),size))throw std::runtime_error("index_read");
            *result=ParseOwnerDirectory(text,identity_);result->fingerprint=DigestFile(index_,size);
            if(std::filesystem::last_write_time(index_)!=before)throw std::runtime_error("index_changed");
            auto root=Utf8Path(identity_.canonicalInstancePath)/"ShooterGame"/"Saved"/Utf8Path(result->savedDirectory);
            VerifyOwnerSources(*result,[&](const OwnerSource& source){
                try{return DigestFile(root/Utf8Path(source.name),source.bytes)==source.sha256;}catch(...){return false;}});
        }catch(...){result=std::make_shared<OwnerDirectory>();result->state="invalid_or_unavailable";}
        std::unique_lock<std::mutex> lock(mutex_);current_=std::move(result);
        if(wake_.wait_for(lock,std::chrono::seconds(5),[&]{return stopping_;}))break;
    }
}
}
