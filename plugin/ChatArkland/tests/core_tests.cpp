#include "ChatCore.h"
#include "ChatDefaults.h"
#include <iostream>
#include <stdexcept>

using namespace ChatArkland;
void Check(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
int main(){
    try{
        Json cfg=Json::parse(kDefaultShared);ValidateShared(cfg);
        Check(cfg.at("PollRate").get<double>()==1.0,"PollRate padrao");
        Check(cfg.at("BadWords").at("Enabled").get<bool>()==false,"Filtro padrao");
        cfg["BadWords"]["Enabled"]=true;cfg["BadWords"]["Words"]=Json::array({"palavra","proibido"});
        WordFilter filter(cfg);
        Check(filter.Apply("Essa PALAVRA é proibida.")=="Essa ******* é proibida.","Censura sem bloquear");
        Check(filter.Apply("p.a.l.a.v.r.a")=="*************","Evasao por pontuacao");
        Check(filter.Apply("p4l4vr4")=="*******","Evasao simples");
        Check(filter.Apply("antepalavra palavrão")=="antepalavra palavrão","Limites de palavras");
        Check(filter.Apply("Olá, João! çãé Ω")=="Olá, João! çãé Ω","Unicode preservado");
        cfg["PollRate"]=0.25;ValidateShared(cfg);cfg["PollRate"]=0;
        bool rejected=false;try{ValidateShared(cfg);}catch(...){rejected=true;}Check(rejected,"PollRate invalido rejeitado");cfg["PollRate"]=1.0;
        SharedState state;state.config=cfg;state.filter=std::make_shared<WordFilter>(cfg);
        state.players["76561198000000001"]={{"public_id","125"},{"licenses",Json::array()}};
        Json actor={{"steam_id","76561198000000001"},{"groups",Json::array({"Default"})},{"name","João"},{"tribe_name",""},{"body","Olá!"}};
        std::string formatted=LocalFormat(state,actor,"Mapa",false);
        Check(formatted.find("125")!=std::string::npos&&formatted.find("João")!=std::string::npos,"Nome e ID no formato");
        Check(formatted.find("[]")==std::string::npos,"Sem tribo vazia");
        Check(NewId().size()==36&&CompactId().size()==32,"UUIDs");
        Check(Color("#FF0000FF")[0]==1.f,"Cor valida");
        std::cout<<"Chat Arkland: testes C++ do nucleo passaram.\n";return 0;
    }catch(const std::exception& failure){std::cerr<<failure.what()<<"\n";return 1;}
}
