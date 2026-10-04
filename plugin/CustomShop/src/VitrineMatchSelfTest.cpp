// Executa a comparacao do Couro. Nao entra na DLL.
#include "VitrineMatch.h"

#include <cstdio>

int main() {
    const char* catalog =
        "/Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.PrimalItemResource_Hide";
    const char* forms[] = {
        "/Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.PrimalItemResource_Hide",
        "Blueprint'/Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.PrimalItemResource_Hide'",
        "BlueprintGeneratedClass /Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.PrimalItemResource_Hide_C",
        "PrimalItemResource_Hide_C /Game/PrimalEarth/CoreBlueprints/Resources/"
        "PrimalItemResource_Hide.Default__PrimalItemResource_Hide_C",
        "PrimalItemResource_Hide",
        "PrimalItemResource_Hide_C",
    };
    int failed = 0;
    for (const char* form : forms) {
        if (!CustomShop::VitrineMatch::SameRaw(catalog, form)) {
            std::printf("FAIL match: %s\n", form);
            ++failed;
        }
    }
    if (CustomShop::VitrineMatch::SameRaw(
            catalog,
            "/Game/PrimalEarth/CoreBlueprints/Resources/"
            "PrimalItemResource_Metal.PrimalItemResource_Metal")) {
        std::printf("FAIL metal casou com couro\n");
        ++failed;
    }
    const auto id = CustomShop::VitrineMatch::Identify(catalog);
    if (id.short_key != "primalitemresource_hide") {
        std::printf("FAIL short: %s\n", id.short_key.c_str());
        ++failed;
    }
    return failed == 0 ? 0 : 1;
}
