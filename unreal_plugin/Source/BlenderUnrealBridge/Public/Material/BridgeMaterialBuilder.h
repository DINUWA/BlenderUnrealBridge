#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"
#include "Materials/MaterialInterface.h"

/**
 * Builds native Unreal Engine UMaterialInterface (UMaterialInstanceDynamic) assets
 * from canonical Bridge PBR material data.
 */
class BLENDERUNREALBRIDGE_API FBridgeMaterialBuilder
{
public:
	/**
	 * Creates a UMaterialInstanceDynamic from canonical FBridgeMaterialData.
	 *
	 * @param Outer Package or Outer object for the new material instance
	 * @param MaterialData Canonical PBR material data
	 * @param OutReport Diagnostic report collecting any warnings or errors
	 * @param MasterMaterial Optional master material to instantiate from; if null, uses default surface material
	 * @return Created UMaterialInterface or nullptr on failure
	 */
	static UMaterialInterface* CreateMaterial(
		UObject* Outer,
		const FBridgeMaterialData& MaterialData,
		FBridgeValidationReport& OutReport,
		UMaterialInterface* MasterMaterial = nullptr);

	/**
	 * Creates all materials defined in a Bridge package data.
	 *
	 * @param Outer Package or Outer object for the new materials
	 * @param PackageData Complete package data containing materials
	 * @param OutReport Diagnostic report
	 * @param MasterMaterial Optional master material template
	 * @return Map of MaterialId -> UMaterialInterface*
	 */
	static TMap<FString, UMaterialInterface*> CreateMaterialsForPackage(
		UObject* Outer,
		const FBridgePackageData& PackageData,
		FBridgeValidationReport& OutReport,
		UMaterialInterface* MasterMaterial = nullptr);
};
