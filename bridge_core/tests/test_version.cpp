#include "bridge_core/version.h"
#include <iostream>
#include <string>
#include <cassert>

int main() {
    std::cout << "[RUNNING] Bridge Core Version Tests..." << std::endl;

    // Test version string
    assert(std::string(bubridge::GetVersionString()) == "0.1.0");
    std::cout << "  ✓ GetVersionString() == '0.1.0'" << std::endl;

    // Test format name
    assert(std::string(bubridge::GetFormatName()) == "BUBRIDGE");
    std::cout << "  ✓ GetFormatName() == 'BUBRIDGE'" << std::endl;

    // Test version components
    assert(bubridge::GetVersionMajor() == 0);
    assert(bubridge::GetVersionMinor() == 1);
    assert(bubridge::GetVersionPatch() == 0);
    std::cout << "  ✓ Version components == 0.1.0" << std::endl;

    // Test compatibility checks
    assert(bubridge::IsFormatCompatible("BUBRIDGE", 0, 1) == true);
    assert(bubridge::IsFormatCompatible("BUBRIDGE", 0, 0) == true);
    assert(bubridge::IsFormatCompatible("BUBRIDGE", 1, 0) == false);
    assert(bubridge::IsFormatCompatible("UNKNOWN", 0, 1) == false);
    std::cout << "  ✓ IsFormatCompatible checks passed" << std::endl;

    std::cout << "[PASSED] All Bridge Core Version Tests passed successfully." << std::endl;
    return 0;
}
