#include "ChatCore.h"
#include <algorithm>
#include <cmath>
#include <cctype>
#include <climits>
#include <cwctype>
#include <ctime>
#include <iomanip>
#include <locale>
#include <set>
#include <sstream>
#include <stdexcept>
#include <objbase.h>

namespace ChatArkland {
std::wstring Wide(const std::string& value) {
    if (value.empty()) return {};
    int size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),nullptr,0);
    if (!size) throw std::runtime_error("Texto UTF-8 inválido.");
    std::wstring out(size,L'\0');
    MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),out.data(),size);
    return out;
}
std::string Utf8(const std::wstring& value) {
    if(value.empty()) return {};
    int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),nullptr,0,nullptr,nullptr);
    if(!size) throw std::runtime_error("Texto Unicode inválido.");
    std::string out(size,'\0');
    WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),static_cast<int>(value.size()),out.data(),size,nullptr,nullptr);
    return out;
}
std::string NewId() {
    GUID id{}; if(FAILED(CoCreateGuid(&id))) throw std::runtime_error("Não foi possível criar o identificador da mensagem.");
    wchar_t text[40]{}; StringFromGUID2(id,text,40);
    std::wstring value(text+1,36); std::transform(value.begin(),value.end(),value.begin(),::towlower);
    return Utf8(value);
}
std::string CompactId() { auto id=NewId(); id.erase(std::remove(id.begin(),id.end(),'-'),id.end()); return id; }
std::string Escape(const std::string& text) {
    std::string out;
    for(char c:text) { if(c=='<') out+="&lt;"; else if(c=='>') out+="&gt;"; else if(c=='&') out+="&amp;"; else out+=c; }
    return out;
}
std::string Name(const std::string& text) {
    auto value=Wide(text);
    for(auto& c:value) { if(c==L'[') c=L'［'; else if(c==L']') c=L'］'; else if(c==L'<') c=L'‹'; else if(c==L'>') c=L'›'; else if(c==L':') c=L'：'; else if(c<32) c=L' '; }
    return Utf8(value);
}
std::array<float,4> Color(const std::string& value) {
    if(value.size()!=9 || value[0]!='#') throw std::runtime_error("Cor inválida na configuração.");
    std::array<float,4> result{};
    for(size_t i=0;i<4;++i) {
        std::string part=value.substr(1+i*2,2);
        if(!std::all_of(part.begin(),part.end(),[](unsigned char c){return std::isxdigit(c)!=0;})) throw std::runtime_error("Cor inválida.");
        result[i]=std::stoi(part,nullptr,16)/255.f;
    }
    return result;
}
void ValidateShared(const Json& cfg) {
    if(!cfg.is_object() || cfg.at("SchemaVersion").get<int>()!=1) throw std::runtime_error("Versão de configuração incompatível.");
    double poll=cfg.at("PollRate").get<double>();
    if(!std::isfinite(poll) || poll<0.1 || poll>30) throw std::runtime_error("PollRate deve estar entre 0,1 e 30 segundos.");
    if(cfg.at("MaxMessageLength").get<int>()<1 || cfg.at("MaxMessageLength").get<int>()>500) throw std::runtime_error("Limite de texto inválido.");
    for(const auto& key:{"DisableChat","DisableCrossServerChat","UseCrossChat","Debug","ShowMapName","ShowSteamName","HideServerTagOnLocal"})
        if(!cfg.at(key).is_boolean()) throw std::runtime_error("Controle de configuração inválido.");
    for(auto it=cfg.at("Colors").begin();it!=cfg.at("Colors").end();++it) if(it.value().is_string()) Color(it.value().get<std::string>());
    for(auto it=cfg.at("CrossMapNotifications").begin();it!=cfg.at("CrossMapNotifications").end();++it)
        if(it.key().find("Color")!=std::string::npos) Color(it.value().get<std::string>());
    if(cfg.at("Messages").at("Global").get<std::string>().find("{id}")==std::string::npos) throw std::runtime_error("O ID público é obrigatório no chat global.");
    if(!cfg.at("Tags").is_array() || !cfg.at("ChatColors").is_array() || !cfg.at("Maps").is_object()) throw std::runtime_error("Cadastro compartilhado inválido.");
    if(cfg.at("BadWords").at("Words").size()>1000) throw std::runtime_error("A lista do filtro excede o limite.");
    std::set<std::string> commands;
    for(const auto& cmd:{cfg.at("OnlinePlayersCommand").at("Command"),cfg.at("PrivateMessages").at("Command"),
                        cfg.at("PrivateMessages").at("ReplyCommand"),cfg.at("CrossMapNotifications").at("ToggleCommand")}) {
        std::string value=cmd.get<std::string>();
        if(value.size()<2 || value.size()>25 || value[0]!='/' || !commands.insert(value).second) throw std::runtime_error("Comandos inválidos ou repetidos.");
    }
}
std::string Message(const Json& cfg,const std::string& key) { return cfg.at("Messages").at(key).get<std::string>(); }

namespace {
bool IsWord(wchar_t c) { WORD kind=0; GetStringTypeW(CT_CTYPE1,&c,1,&kind); return c==L'_' || (kind&(C1_ALPHA|C1_DIGIT))!=0; }
std::wstring Fold(const std::wstring& input,std::vector<size_t>* positions=nullptr) {
    std::wstring result;
    for(size_t i=0;i<input.size();++i) {
        wchar_t c=input[i];
        switch(c) { case L'0':c=L'o';break;case L'1':c=L'i';break;case L'3':c=L'e';break;case L'4':c=L'a';break;case L'5':c=L's';break;case L'7':c=L't';break;case L'@':c=L'a';break; }
        wchar_t normalized[32]{},lower[32]{};
        int count=NormalizeString(NormalizationKD,&c,1,normalized,32);
        if(count<=0){ normalized[0]=c;count=1; }
        int lowered=LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_LOWERCASE,normalized,count,lower,32,nullptr,nullptr,0);
        if(lowered<=0){std::copy(normalized,normalized+count,lower);lowered=count;}
        for(int j=0;j<lowered;++j) {
            WORD kind=0;GetStringTypeW(CT_CTYPE3,&lower[j],1,&kind);
            if(kind&(C3_NONSPACING|C3_DIACRITIC)) continue;
            if(lower[j]==L'ß') { result+=L"ss";if(positions){positions->push_back(i);positions->push_back(i);} }
            else {result+=lower[j];if(positions)positions->push_back(i);}
        }
    }
    return result;
}
void Replace(std::string& text,const std::string& token,const std::string& value) {
    size_t position=0; while((position=text.find(token,position))!=std::string::npos){text.replace(position,token.size(),value);position+=value.size();}
}
std::string Span(const std::string& value,const std::string& paint) {
    auto rgba=Color(paint);std::ostringstream out;out.imbue(std::locale::classic());
    out<<"<RichColor Color=\""<<std::fixed<<std::setprecision(4)<<rgba[0]<<","<<rgba[1]<<","<<rgba[2]<<","<<rgba[3]<<"\">"<<Escape(value)<<"</>";return out.str();
}
}
WordFilter::WordFilter(const Json& cfg) {
    enabled_=cfg.at("BadWords").at("Enabled").get<bool>();
    for(const auto& c:cfg.at("BadWords").at("IgnoredLetters")) ignored_+=Wide(c.get<std::string>());
    if(!enabled_)return;
    for(const auto& word:cfg.at("BadWords").at("Words")) {
        auto folded=Fold(Wide(word.get<std::string>()));size_t node=0;bool useful=false;
        for(wchar_t c:folded) {
            if(ignored_.find(c)!=std::wstring::npos) continue;
            useful=true;
            auto found=nodes_[node].next.find(c);
            if(found==nodes_[node].next.end()){size_t next=nodes_.size();nodes_[node].next.emplace(c,next);nodes_.push_back({});node=next;}
            else node=found->second;
        }
        if(useful)nodes_[node].terminal=true;
    }
}
std::string WordFilter::Apply(const std::string& text) const {
    if(!enabled_ || nodes_.size()==1) return text;
    auto original=Wide(text);std::vector<size_t> positions;auto folded=Fold(original,&positions);
    std::vector<bool> censored(original.size(),false);
    for(size_t start=0;start<folded.size();++start) {
        if(start && IsWord(folded[start-1]))continue;
        size_t node=0;
        for(size_t at=start;at<folded.size();++at) {
            wchar_t c=folded[at];
            if(at!=start && ignored_.find(c)!=std::wstring::npos) continue;
            auto found=nodes_[node].next.find(c);if(found==nodes_[node].next.end())break;
            node=found->second;
            if(nodes_[node].terminal && (at+1==folded.size() || !IsWord(folded[at+1])))
                for(size_t k=positions[start];k<=positions[at];++k)censored[k]=true;
        }
    }
    for(size_t i=0;i<original.size();++i)if(censored[i])original[i]=L'*';
    return Utf8(original);
}
std::string LocalFormat(const SharedState& state,const Json& actor,const std::string& key,bool verified) {
    const auto& cfg=state.config;std::string steam=actor.value("steam_id","");
    if(!state.players.contains(steam) || !state.players.at(steam).contains("public_id"))return {};
    auto colors=cfg.at("Colors");Json selected;int best=INT_MAX;bool best_admin=false;
    std::set<std::string> groups{"Default"};for(const auto& group:actor.at("groups"))groups.insert(group.get<std::string>());
    std::set<std::string> licenses;
    if(verified)for(const auto& entry:state.players.at(steam).value("licenses",Json::array())) {
        if(entry.at("expires_epoch").is_null() || entry.at("expires_epoch").get<int64_t>()>std::time(nullptr))licenses.insert(entry.at("group").get<std::string>());
    }
    auto matches=[&](const Json& rule) {
        if(!rule.value("Approved",false)||!rule.value("Enabled",false))return false;
        auto kind=rule.value("Kind","");bool permission=false,license=false;
        auto rule_groups=rule.value("PermissionGroups",Json::array());if(kind=="admin" && rule_groups.empty())rule_groups=cfg.at("AdminGroups");
        for(const auto& group:rule_groups)permission|=groups.count(group.get<std::string>())!=0;
        for(const auto& group:rule.value("LicenseGroups",Json::array()))license|=licenses.count(group.get<std::string>())!=0;
        bool identity=false;for(const auto& id:rule.value("SteamIds",Json::array()))identity|=id.get<std::string>()==steam;
        for(const auto& id:rule.value("TribeIds",Json::array()))identity|=id.get<std::string>()==actor.value("tribe_id","");
        bool identity_scope=!rule.value("SteamIds",Json::array()).empty()||!rule.value("TribeIds",Json::array()).empty();
        if(kind=="admin")return permission&&(!identity_scope||identity);
        if(kind=="license")return license&&(!(identity_scope||!rule_groups.empty())||permission||identity);
        return kind=="everyone"||permission||license||identity;
    };
    for(const auto& tag:cfg.at("Tags"))if(matches(tag)) {
        bool admin=tag.value("Kind","")=="admin";int priority=tag.value("Priority",0);
        if(selected.is_null() || (admin&&!best_admin) || (admin==best_admin&&(priority<best||(priority==best&&tag.at("Key").get<std::string>()<selected.at("Key").get<std::string>())))){selected=tag;best=priority;best_admin=admin;}
    }
    const Json* style=nullptr;best=INT_MAX;best_admin=false;
    for(const auto& rule:cfg.at("ChatColors"))if(matches(rule)){
        bool admin=rule.value("Kind","")=="admin";int priority=rule.value("Priority",0);
        if(!style||(admin&&!best_admin)||(admin==best_admin&&(priority<best||(priority==best&&rule.at("Key").get<std::string>()<style->at("Key").get<std::string>())))){style=&rule;best=priority;best_admin=admin;}
    }
    if(style){auto overrides=style->value("Colors",Json::object());for(auto it=overrides.begin();it!=overrides.end();++it)colors[it.key()]=it.value();}
    Json map=cfg.at("Maps").value(key,Json::object());std::string label=map.value("Label",key);
    std::string name=actor.value("name",steam);if(cfg.at("ShowSteamName").get<bool>()&&!actor.value("steam_name","").empty())name=actor.at("steam_name").get<std::string>();
    std::string tribe=actor.value("tribe_name","");std::string message=actor.value("body","");
    time_t stamp=std::time(nullptr)-3*3600;tm parts{};gmtime_s(&parts,&stamp);char hour[6]{};std::strftime(hour,sizeof(hour),"%H:%M",&parts);
    std::string output=cfg.at("Messages").at("Global").get<std::string>();if(!cfg.at("ShowMapName").get<bool>())Replace(output,"[{mapa}]","");
    Replace(output,"{hora}",hour);Replace(output,"{mapa}",Span(Name(label),map.value("Color",colors.at("Map").get<std::string>())));
    Replace(output,"{tag}",selected.is_null()?"":Span("<"+Name(selected.at("Label").get<std::string>())+"> ",selected.value("Color",colors.at("Tag").get<std::string>())));
    Replace(output,"{jogador}",Span(Name(name),colors.at("Name").get<std::string>()));
    Replace(output,"{id}",Span(state.players.at(steam).at("public_id").get<std::string>(),colors.at("Id").get<std::string>()));
    Replace(output,"{tribo}",tribe.empty()||colors.at("HideTribeName").get<bool>()?"":Span(" ["+Name(tribe)+"]",colors.at("Tribe").get<std::string>()));
    Replace(output,"{mensagem}",Span(message,colors.at("Message").get<std::string>()));return output;
}
}
