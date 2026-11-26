#include "ChatTransport.h"
#include "ChatDefaults.h"
#include <winhttp.h>
#include <algorithm>
#include <ctime>
#include <fstream>
#include <set>
#include <stdexcept>

namespace ChatArkland {
namespace {
struct HttpHandle {
    HINTERNET value=nullptr;
    explicit HttpHandle(HINTERNET h=nullptr):value(h){}
    ~HttpHandle(){if(value)WinHttpCloseHandle(value);}
    HttpHandle(const HttpHandle&)=delete;
    operator HINTERNET()const{return value;}
};
constexpr size_t kMaxQueue=512,kMaxInbox=2048,kMaxSeen=4096,kMaxBody=1024*1024;
std::string Key(const Json& value){return value.value("delivery_id",value.value("event_id",""));}
Json Read(const std::filesystem::path& path){
    if(!std::filesystem::is_regular_file(path)||std::filesystem::file_size(path)>kMaxBody)throw std::runtime_error("config.json ausente ou maior que 1 MiB.");
    std::ifstream stream(path);Json value;stream>>value;return value;
}
}
Transport::Transport(std::filesystem::path path):path_(std::move(path)),boot_(CompactId().substr(0,8)) {
    document_=Read(path_);local_=document_.at("Local");
    if(local_.contains("ObserveOnly")&&!local_.at("ObserveOnly").is_boolean())throw std::runtime_error("Local.ObserveOnly deve ser verdadeiro ou falso.");
    auto api_key=local_.value("ApiKey","");if(api_key.size()>512||api_key.find_first_of("\r\n")!=std::string::npos)throw std::runtime_error("Chave interna inválida.");
    server_key_=local_.value("ServerKey","");
    if(server_key_.empty()||server_key_.size()>100||local_.value("ApiKey","").empty())throw std::runtime_error("Configure Local.ServerKey e Local.ApiKey antes de carregar o Chat Arkland.");
    auto initial=std::make_shared<SharedState>();
    initial->config=Json::parse(kDefaultShared);
    if(document_.contains("Shared"))try{ValidateShared(document_.at("Shared").at("config"));initial->config=document_["Shared"]["config"];initial->revision=document_["Shared"].value("revision",0ULL);}catch(...){initial->revision=0;}
    ValidateShared(initial->config);initial->filter=std::make_shared<WordFilter>(initial->config);
    auto runtime=document_.value("Runtime",Json::object());
    if(runtime.value("ServerKey",server_key_)==server_key_){
        cursor_=runtime.value("Cursor",0ULL);resume_=runtime.value("Resume",false);identities_=runtime.value("Players",Json::object());if(!identities_.is_object())identities_=Json::object();
        for(const auto& id:runtime.value("Seen",Json::array()))if(id.is_string()){seen_.insert(id.get<std::string>());seen_order_.push_back(id.get<std::string>());}
    }
    while(seen_order_.size()>kMaxSeen){seen_.erase(seen_order_.front());seen_order_.pop_front();}
    initial->players=identities_;state_=initial;
}
Transport::~Transport(){Stop();}
void Transport::Start(){if(!worker_.joinable()){stop_=false;worker_=std::thread([this]{try{Run();}catch(...){healthy_=false;}});}}
void Transport::Stop(){stop_=true;cv_.notify_all();if(worker_.joinable())worker_.join();healthy_=false;}
void Transport::Snapshot(Json players){std::lock_guard lock(mutex_);snapshot_=std::move(players);}
bool Transport::Enqueue(Json event){
    std::lock_guard lock(mutex_);if(outbound_.size()>=kMaxQueue)return false;
    event["_queued_at"]=std::time(nullptr);outbound_.push_back(std::move(event));cv_.notify_all();return true;
}
std::shared_ptr<const SharedState> Transport::State()const{std::lock_guard lock(mutex_);return state_;}
Json Transport::Status()const{std::lock_guard lock(mutex_);return {{"rede_disponivel",healthy_.load()},{"observacao",ObserveOnly()||state_->observer},{"revisao",state_->revision},{"fila_saida",outbound_.size()},{"fila_entrada",inbound_.size()}};}
bool Transport::Inbox(Json value){
    const std::string key=Key(value);
    if(!key.empty()&&seen_.count(key)){
        if(value.contains("delivery_id"))for(const auto& steam:value.at("recipients")){
            bool queued=std::any_of(acks_.begin(),acks_.end(),[&](const Json& ack){return ack.at("delivery_id")==value.at("delivery_id")&&ack.at("recipient")==steam;});
            if(!queued&&acks_.size()<kMaxInbox)acks_.push_back({{"delivery_id",value.at("delivery_id")},{"recipient",steam}});
        }
        return true;
    }
    if(!key.empty()&&pending_.count(key))return true;
    if(inbound_.size()>=kMaxInbox)return false;
    if(!key.empty())pending_.insert(key);inbound_.push_back(std::move(value));return true;
}
std::vector<Json> Transport::Drain(size_t maximum){
    std::lock_guard lock(mutex_);std::vector<Json> result;
    while(!inbound_.empty()&&result.size()<maximum){result.push_back(std::move(inbound_.front()));inbound_.pop_front();}
    return result;
}
void Transport::Processed(const Json& item,bool delivered){
    std::lock_guard lock(mutex_);
    if(item.value("kind","")=="cursor"){cursor_=std::max(cursor_,item.at("cursor").get<uint64_t>());return;}
    auto key=Key(item);pending_.erase(key);
    if(!delivered)return;
    if(!key.empty()&&seen_.insert(key).second){seen_order_.push_back(key);while(seen_order_.size()>kMaxSeen){seen_.erase(seen_order_.front());seen_order_.pop_front();}}
    if(item.contains("delivery_id"))for(const auto& steam:item.at("recipients"))acks_.push_back({{"delivery_id",item.at("delivery_id")},{"recipient",steam}});
}
void Transport::Persist(){
    Json value;
    {std::lock_guard lock(mutex_);value=document_;value["Shared"]={{"revision",state_->revision},{"config",state_->config}};
     value["Runtime"]={{"ServerKey",server_key_},{"Cursor",cursor_},{"Resume",resume_},{"Players",identities_},{"Seen",seen_order_}};}
    // Uma publicação global nunca substitui a identificação/chave local.
    try {auto current=Read(path_);value["Local"]=current.at("Local");if(current["Local"].value("ServerKey","")!=server_key_)return;}catch(...){return;}
    std::string encoded=value.dump(2);if(encoded.size()>kMaxBody)return;
    auto temporary=path_;temporary+=L".tmp";
    {std::ofstream out(temporary,std::ios::binary|std::ios::trunc);out<<encoded;if(!out)throw std::runtime_error("Falha ao preservar o cache local.");}
    if(!MoveFileExW(temporary.c_str(),path_.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("Não foi possível atualizar o cache local.");
}
Json Transport::Request(const Json& body){
    auto url=Wide(local_.value("ApiUrl",""));URL_COMPONENTS parts{};parts.dwStructSize=sizeof(parts);parts.dwHostNameLength=parts.dwUrlPathLength=parts.dwExtraInfoLength=parts.dwUserNameLength=parts.dwPasswordLength=static_cast<DWORD>(-1);
    if(!WinHttpCrackUrl(url.c_str(),0,0,&parts)||(parts.nScheme!=INTERNET_SCHEME_HTTP&&parts.nScheme!=INTERNET_SCHEME_HTTPS)||parts.dwUserNameLength||parts.dwPasswordLength||parts.dwExtraInfoLength)
        throw std::runtime_error("Endereço da API inválido.");
    std::wstring host(parts.lpszHostName,parts.dwHostNameLength),path=parts.dwUrlPathLength?std::wstring(parts.lpszUrlPath,parts.dwUrlPathLength):std::wstring();
    while(!path.empty()&&path.back()==L'/')path.pop_back();path+=L"/api/chat-arkland/plugin/exchange";
    HttpHandle session(WinHttpOpen(L"ChatArkland/0.1.0",WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0));
    if(!session.value)throw std::runtime_error("Não foi possível iniciar o transporte.");
    WinHttpSetTimeouts(session,500,1000,1000,1500);
    HttpHandle connection(WinHttpConnect(session,host.c_str(),parts.nPort,0));
    HttpHandle request(WinHttpOpenRequest(connection,L"POST",path.c_str(),nullptr,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,parts.nScheme==INTERNET_SCHEME_HTTPS?WINHTTP_FLAG_SECURE:0));
    if(!connection.value||!request.value)throw std::runtime_error("API temporariamente indisponível.");
    DWORD policy=WINHTTP_OPTION_REDIRECT_POLICY_NEVER;WinHttpSetOption(request,WINHTTP_OPTION_REDIRECT_POLICY,&policy,sizeof(policy));
    std::wstring headers=L"Content-Type: application/json; charset=utf-8\r\nX-API-Key: "+Wide(local_.at("ApiKey").get<std::string>())+L"\r\n";
    std::string encoded=body.dump();if(encoded.size()>kMaxBody)throw std::runtime_error("Lote de comunicação maior que o limite.");
    if(!WinHttpSendRequest(request,headers.c_str(),static_cast<DWORD>(headers.size()),encoded.data(),static_cast<DWORD>(encoded.size()),static_cast<DWORD>(encoded.size()),0)||!WinHttpReceiveResponse(request,nullptr))throw std::runtime_error("Envio não confirmado pela API.");
    DWORD status=0,length=sizeof(status);WinHttpQueryHeaders(request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,&status,&length,WINHTTP_NO_HEADER_INDEX);
    if(status!=200)throw std::runtime_error("A API recusou temporariamente a comunicação.");
    std::string output;DWORD available=0,read=0;char buffer[8192];auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(6);
    while(WinHttpQueryDataAvailable(request,&available)&&available){while(available){if(std::chrono::steady_clock::now()>deadline)throw std::runtime_error("Tempo total de leitura excedido.");DWORD amount=std::min<DWORD>(available,sizeof(buffer));if(!WinHttpReadData(request,buffer,amount,&read)||!read)throw std::runtime_error("Resposta da API incompleta.");output.append(buffer,read);if(output.size()>kMaxBody)throw std::runtime_error("Resposta da API excede o limite.");available-=read;}}
    Json response=Json::parse(output);if(!response.value("ok",false))throw std::runtime_error("A API não confirmou o lote.");return response;
}
void Transport::Run(){
    while(true){
        bool stopping=stop_.load();Json body,batch=Json::array();size_t ack_count=0;
        {
            std::lock_guard lock(mutex_);
            while(!outbound_.empty()&&std::time(nullptr)-outbound_.front().value("_queued_at",int64_t(0))>state_->config.at("MessageTtlSeconds").get<int>())outbound_.pop_front();
            for(size_t i=0;i<std::min<size_t>(50,outbound_.size());++i){Json event=outbound_[i];event.erase("_actor");event.erase("_fallback");event.erase("_queued_at");batch.push_back(std::move(event));}
            Json ack_batch=Json::array();for(size_t i=0;i<std::min<size_t>(200,acks_.size());++i)ack_batch.push_back(acks_[i]);ack_count=ack_batch.size();
            body={{"server_key",server_key_},{"boot_id",boot_},{"plugin_version","0.1.0"},{"observer",ObserveOnly()},
                  {"revision",state_->revision},{"players",stopping?Json::array():snapshot_},{"events",batch},{"acks",ack_batch},
                  {"cursor",cursor_},{"resume",resume_},{"stopping",stopping}};
        }
        try{
            Json response=Request(body);auto next=std::make_shared<SharedState>(*State());
            if(response.contains("config")&&!response.at("config").is_null()){
                ValidateShared(response.at("config"));next->config=response.at("config");next->revision=response.at("revision").get<uint64_t>();
                next->filter=std::make_shared<WordFilter>(next->config);
            }
            next->observer=response.value("observer",true);
            std::set<std::string> accepted;for(const auto& id:response.at("accepted"))accepted.insert(id.get<std::string>());
            {
                std::lock_guard lock(mutex_);
                for(auto it=response.at("players").begin();it!=response.at("players").end();++it)identities_[it.key()]=it.value();
                while(identities_.size()>500)identities_.erase(identities_.begin());next->players=identities_;state_=next;resume_=true;
                for(const auto& reject:response.at("rejected")){
                    std::string id=reject.value("event_id","");accepted.insert(id);
                    for(const auto& pending:outbound_)if(pending.value("event_id","")==id)Inbox({{"kind","notice"},{"event_id",id},{"recipients",Json::array({pending.at("steam_id")})},{"text",reject.value("reason",Message(next->config,"Unavailable"))}});
                }
                if(next->observer)for(const auto& pending:outbound_)accepted.insert(pending.at("event_id").get<std::string>());
                outbound_.erase(std::remove_if(outbound_.begin(),outbound_.end(),[&](const Json& value){return accepted.count(value.at("event_id").get<std::string>())!=0;}),outbound_.end());
                for(size_t i=0;i<ack_count&&!acks_.empty();++i)acks_.pop_front();
                bool complete=true;for(const auto& item:response.at("deliveries"))complete=Inbox(item)&&complete;
                if(complete)Inbox({{"kind","cursor"},{"cursor",response.at("cursor")}});
            }
            healthy_=true;Persist();
        }catch(...){
            healthy_=false;
            std::lock_guard lock(mutex_);
            for(auto& event:outbound_)if(event.value("kind","")=="global"&&!event.value("_fallback",false)){
                try{
                auto actor=event.value("_actor",Json::object());actor["body"]=event.value("body","");
                std::string rich=LocalFormat(*state_,actor,server_key_,false);
                if(!rich.empty())Inbox({{"kind","local_fallback"},{"event_id",event.at("event_id")},{"rich",rich}});
                }catch(...){}
                event["_fallback"]=true;
            }
        }
        if(stopping)break;
        double delay=State()->config.at("PollRate").get<double>();
        std::unique_lock lock(mutex_);cv_.wait_for(lock,std::chrono::duration<double>(delay),[&]{return stop_.load();});
    }
    try{Persist();}catch(...){}
}
}
