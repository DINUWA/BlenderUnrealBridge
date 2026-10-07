#include "Scene/BridgeSceneBuilder.h"
#include "Reader/BridgePackageReader.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SceneComponent.h"

bool FBridgeSceneBuilder::BuildScene(
	UWorld* World,
	const FBridgePackageData& PackageData,
	const TMap<FString, UStaticMesh*>& MeshMap,
	const TMap<FString, UMaterialInterface*>& MaterialMap,
	FBridgeValidationReport& OutReport,
	FBridgeSpawnedScene& OutSpawnedScene)
{
	if (!World)
	{
		OutReport.AddError(TEXT("SCENE_BUILD_NO_WORLD"), TEXT("Cannot build scene: Target World is null"));
		return false;
	}

	OutSpawnedScene.SpawnedActors.Empty(PackageData.Objects.Num());
	OutSpawnedScene.RootActors.Empty();
	OutSpawnedScene.CollectionFolders.Empty();

	// 1. Build Collection Folder Paths
	for (const FBridgeCollection& Col : PackageData.Scene.Collections)
	{
		FString FolderPath = FBridgePackageReader::BuildCollectionFolderPath(PackageData, Col.Id);
		if (!FolderPath.IsEmpty())
		{
			OutSpawnedScene.CollectionFolders.Add(Col.Id, FName(*FolderPath));
		}
	}

	// 2. Pass 1: Spawn all actors and assign meshes/materials
	for (const FBridgeObject& Obj : PackageData.Objects)
	{
		AActor* SpawnedActor = nullptr;
		FActorSpawnParameters SpawnParams;
		SpawnParams.Name = !Obj.Name.IsEmpty() ? FName(*Obj.Name) : FName(*Obj.Id);
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

		if (Obj.Type == TEXT("STATIC_MESH") && Obj.HasMesh())
		{
			AStaticMeshActor* MeshActor = World->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), SpawnParams);
			if (MeshActor)
			{
				UStaticMeshComponent* MeshComp = MeshActor->GetStaticMeshComponent();
				if (MeshComp)
				{
					UStaticMesh* const* FoundMesh = MeshMap.Find(Obj.MeshReference.MeshId);
					if (FoundMesh && *FoundMesh)
					{
						MeshComp->SetStaticMesh(*FoundMesh);

						// Slot materials
						for (const FBridgeMaterialSlot& Slot : Obj.MaterialSlots)
						{
							if (!Slot.MaterialId.IsEmpty())
							{
								UMaterialInterface* const* FoundMat = MaterialMap.Find(Slot.MaterialId);
								if (FoundMat && *FoundMat)
								{
									MeshComp->SetMaterial(Slot.SlotIndex, *FoundMat);
								}
							}
						}
					}
				}
				SpawnedActor = MeshActor;
			}
		}
		else
		{
			// Empty / Locator or generic actor
			AActor* EmptyActor = World->SpawnActor<AActor>(AActor::StaticClass(), SpawnParams);
			if (EmptyActor)
			{
				USceneComponent* RootComp = NewObject<USceneComponent>(EmptyActor, TEXT("RootComponent"));
				EmptyActor->SetRootComponent(RootComp);
				RootComp->RegisterComponent();
				SpawnedActor = EmptyActor;
			}
		}

		if (!SpawnedActor)
		{
			OutReport.AddError(
				TEXT("ACTOR_SPAWN_FAILED"),
				FString::Printf(TEXT("Failed to spawn actor for object '%s' (%s)"), *Obj.Name, *Obj.Id),
				Obj.Id);
			continue;
		}

#if WITH_EDITOR
		SpawnedActor->SetActorLabel(Obj.Name);
#endif

		// Set Outliner Folder path from primary collection
		if (!Obj.CollectionId.IsEmpty())
		{
			const FName* FolderName = OutSpawnedScene.CollectionFolders.Find(Obj.CollectionId);
			if (FolderName && !FolderName->IsNone())
			{
				SpawnedActor->SetFolderPath(*FolderName);
			}
		}

		// Visibility
		SpawnedActor->SetActorHiddenInGame(!Obj.bVisible);
#if WITH_EDITOR
		SpawnedActor->SetIsTemporarilyHiddenInEditor(!Obj.bVisible);
#endif

		OutSpawnedScene.SpawnedActors.Add(Obj.Id, SpawnedActor);
	}

	// 3. Pass 2: Establish Parent-Child Hierarchy and Apply Transforms
	TArray<const FBridgeObject*> OrderedObjects;
	if (!FBridgePackageReader::GetTopologicalObjectOrder(PackageData, OrderedObjects))
	{
		// Fallback to iterating PackageData.Objects directly if cycle or issue
		for (const FBridgeObject& Obj : PackageData.Objects)
		{
			OrderedObjects.Add(&Obj);
		}
	}

	for (const FBridgeObject* ObjPtr : OrderedObjects)
	{
		if (!ObjPtr)
		{
			continue;
		}

		const FBridgeObject& Obj = *ObjPtr;
		AActor** FoundActor = OutSpawnedScene.SpawnedActors.Find(Obj.Id);
		if (!FoundActor || !(*FoundActor))
		{
			continue;
		}

		AActor* Actor = *FoundActor;
		FTransform LocalTransform = FBridgePackageReader::GetUnrealLocalTransform(Obj);

		if (Obj.HasParent())
		{
			AActor** FoundParent = OutSpawnedScene.SpawnedActors.Find(Obj.ParentId);
			if (FoundParent && *FoundParent)
			{
				AActor* ParentActor = *FoundParent;
				Actor->AttachToActor(ParentActor, FAttachmentTransformRules::KeepRelativeTransform);
				if (Actor->GetRootComponent())
				{
					Actor->GetRootComponent()->SetRelativeTransform(LocalTransform);
				}
			}
			else
			{
				OutReport.AddWarning(
					TEXT("ATTACHMENT_PARENT_NOT_SPAWNED"),
					FString::Printf(TEXT("Object '%s' parent '%s' was not spawned; keeping as root"), *Obj.Id, *Obj.ParentId),
					Obj.Id);
				Actor->SetActorTransform(LocalTransform);
				OutSpawnedScene.RootActors.Add(Actor);
			}
		}
		else
		{
			// Root object: Local transform is the World transform
			Actor->SetActorTransform(LocalTransform);
			OutSpawnedScene.RootActors.Add(Actor);
		}
	}

	OutReport.AddInfo(
		TEXT("SCENE_BUILD_SUCCESS"),
		FString::Printf(TEXT("Successfully reconstructed scene '%s' with %d actors (%d roots)"),
			*PackageData.Scene.Name, OutSpawnedScene.SpawnedActors.Num(), OutSpawnedScene.RootActors.Num()));

	return true;
}
