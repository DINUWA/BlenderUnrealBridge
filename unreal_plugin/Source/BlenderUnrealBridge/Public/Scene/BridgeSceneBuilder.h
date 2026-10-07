#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"
#include "GameFramework/Actor.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"

/**
 * Result structure containing spawned actors, roots, and folder paths.
 */
struct BLENDERUNREALBRIDGE_API FBridgeSpawnedScene
{
	/** Map of Bridge Object ID -> Spawned AActor* */
	TMap<FString, AActor*> SpawnedActors;

	/** Root-level actors (actors without parents) */
	TArray<AActor*> RootActors;

	/** Map of Collection ID -> Folder Path in Unreal Outliner */
	TMap<FString, FName> CollectionFolders;
};

/**
 * Reconstructs the complete scene hierarchy inside a native Unreal World/Level.
 *
 * Responsibilities:
 * 1. Spawns native AStaticMeshActor instances for mesh objects with assigned static meshes and materials.
 * 2. Spawns native AActor instances with root USceneComponent for empty/locator objects.
 * 3. Applies local transforms to child actors and attaches them to parent actors (AActor::AttachToActor).
 * 4. Applies world transforms to root actors without parenting.
 * 5. Reconstructs collection folders in Unreal World Outliner using AActor::SetFolderPath().
 * 6. Reconstructs visibility and labels.
 */
class BLENDERUNREALBRIDGE_API FBridgeSceneBuilder
{
public:
	/**
	 * Spawns and reconstructs the scene hierarchy in the target World.
	 *
	 * @param World Target UWorld to spawn actors into
	 * @param PackageData Ingested and validated bridge package data
	 * @param MeshMap Map of MeshId -> UStaticMesh*
	 * @param MaterialMap Map of MaterialId -> UMaterialInterface*
	 * @param OutReport Diagnostic report
	 * @param OutSpawnedScene Result structure containing spawned actors and hierarchy
	 * @return true if all actors were spawned and attached successfully without errors
	 */
	static bool BuildScene(
		UWorld* World,
		const FBridgePackageData& PackageData,
		const TMap<FString, UStaticMesh*>& MeshMap,
		const TMap<FString, UMaterialInterface*>& MaterialMap,
		FBridgeValidationReport& OutReport,
		FBridgeSpawnedScene& OutSpawnedScene);
};
