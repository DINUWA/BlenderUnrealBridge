#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"
#include "Engine/StaticMesh.h"

/**
 * Builds native Unreal Engine UStaticMesh assets from canonical Bridge mesh data.
 */
class BLENDERUNREALBRIDGE_API FBridgeMeshBuilder
{
public:
	/**
	 * Builds a UStaticMesh asset from canonical FBridgeMeshData using FMeshDescription.
	 *
	 * @param Outer Package or Outer object for the new UStaticMesh
	 * @param Name Name for the new UStaticMesh asset
	 * @param MeshData Canonical mesh geometry and slot data
	 * @param OutReport Diagnostic report collecting any warnings or errors
	 * @return Created UStaticMesh or nullptr on failure
	 */
	static UStaticMesh* CreateStaticMesh(
		UObject* Outer,
		const FName& Name,
		const FBridgeMeshData& MeshData,
		FBridgeValidationReport& OutReport);
};
