#pragma once

#include "CoreMinimal.h"
#include "BridgeDiagnostics.h"

/**
 * Coordinate system specification from manifest.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeCoordinateSystem
{
	FString UpAxis;
	FString ForwardAxis;
	FString RightAxis;
	FString Handedness;
	FString Unit;

	FBridgeCoordinateSystem()
		: UpAxis(TEXT("Z"))
		, ForwardAxis(TEXT("X"))
		, RightAxis(TEXT("Y"))
		, Handedness(TEXT("left_handed"))
		, Unit(TEXT("centimeter"))
	{
	}
};

/**
 * Content summary from manifest.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeContentSummary
{
	int32 ObjectCount = 0;
	int32 MeshCount = 0;
	int32 MaterialCount = 0;
	int32 TextureCount = 0;
};

/**
 * Manifest representation from manifest.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeManifest
{
	FString Format;
	FString Version;
	FString CreatedAt;

	FString GeneratorName;
	FString GeneratorVersion;

	FString SourceApplication;
	FString SourceVersion;
	FString SourceSceneName;
	FString SourceUnitLength;
	float SourceUnitScale = 1.0f;

	FString TargetApplication;
	FString TargetVersion;
	FString TargetUnitLength;

	FBridgeCoordinateSystem CoordinateSystem;
	FBridgeContentSummary ContentSummary;
};

/**
 * Collection metadata from scene.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeCollection
{
	FString Id;
	FString Name;
	FString ParentId;
	FString ColorTag;
};

/**
 * Scene-level metadata from scene.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeScene
{
	FString Name;
	TArray<FBridgeCollection> Collections;
	FLinearColor BackgroundColor = FLinearColor(0.05f, 0.05f, 0.05f, 1.0f);
	float AmbientIntensity = 1.0f;
};

/**
 * Canonical Bridge transform representation from objects.json.
 * Conforms strictly to DATA_PROTOCOL.md §4.3 and Milestone 2 rules:
 *   - Up: +Z
 *   - Forward: +X
 *   - Right: +Y
 *   - Unit: Centimeter
 *   - Handedness: Left-handed
 */
struct BLENDERUNREALBRIDGE_API FBridgeCanonicalTransform
{
	FVector Location = FVector::ZeroVector;
	FQuat RotationQuaternion = FQuat::Identity;
	FVector RotationEuler = FVector::ZeroVector;
	FString RotationMode = TEXT("QUATERNION");
	FVector Scale = FVector::OneVector;
	bool bHasNegativeScale = false;
	FVector OriginOffset = FVector::ZeroVector;
};

/**
 * Mesh reference on an object node.
 */
struct BLENDERUNREALBRIDGE_API FBridgeMeshReference
{
	FString MeshId;
	FString File;
	int32 SubmeshIndex = 0;

	bool IsValid() const
	{
		return !MeshId.IsEmpty();
	}
};

/**
 * Material slot binding.
 */
struct BLENDERUNREALBRIDGE_API FBridgeMaterialSlot
{
	int32 SlotIndex = 0;
	FString SlotName;
	FString MaterialId;
};

/**
 * Single triangle in canonical mesh representation.
 */
struct BLENDERUNREALBRIDGE_API FBridgeMeshTriangle
{
	int32 VertexIndices[3] = { 0, 0, 0 };
	FVector3f Normals[3] = { FVector3f(0.f, 0.f, 1.f), FVector3f(0.f, 0.f, 1.f), FVector3f(0.f, 0.f, 1.f) };
	FVector2f UVs[3] = { FVector2f::ZeroVector, FVector2f::ZeroVector, FVector2f::ZeroVector };
	int32 MaterialSlotIndex = 0;
};

/**
 * Bounding box for canonical mesh.
 */
struct BLENDERUNREALBRIDGE_API FBridgeMeshBounds
{
	FVector3f Min = FVector3f::ZeroVector;
	FVector3f Max = FVector3f::ZeroVector;
};

/**
 * Complete canonical mesh asset payload loaded from meshes/<mesh_id>.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeMeshData
{
	FString Format;
	FString Version;
	FString MeshId;
	FString Name;

	int32 VertexCount = 0;
	int32 TriangleCount = 0;
	int32 UVLayerCount = 0;
	int32 MaterialSlotCount = 0;

	FBridgeMeshBounds Bounds;

	TArray<FVector3f> Vertices;
	TArray<FBridgeMeshTriangle> Triangles;
	TArray<FBridgeMaterialSlot> MaterialSlots;
};

/**
 * Object node from objects.json.
 */
struct BLENDERUNREALBRIDGE_API FBridgeObject
{
	FString Id;
	FString Name;
	FString Type;
	bool bVisible = true;
	FString CollectionId;
	FString ParentId;

	FBridgeCanonicalTransform Transform;
	FBridgeMeshReference MeshReference;
	TArray<FBridgeMaterialSlot> MaterialSlots;

	bool HasParent() const
	{
		return !ParentId.IsEmpty();
	}

	bool HasMesh() const
	{
		return Type == TEXT("STATIC_MESH") && MeshReference.IsValid();
	}
};

/**
 * Complete in-memory Bridge Package model loaded from a .bubridge package.
 */
struct BLENDERUNREALBRIDGE_API FBridgePackageData
{
	FString PackageDirectory;
	FBridgeManifest Manifest;
	FBridgeScene Scene;
	TArray<FBridgeObject> Objects;
	TMap<FString, FBridgeMeshData> Meshes;

	/** Fast lookup index mapping Bridge ID -> Object index in Objects array */
	TMap<FString, int32> IdToIndexMap;

	const FBridgeObject* FindObjectById(const FString& InId) const
	{
		const int32* FoundIndex = IdToIndexMap.Find(InId);
		if (FoundIndex && Objects.IsValidIndex(*FoundIndex))
		{
			return &Objects[*FoundIndex];
		}
		return nullptr;
	}

	const FBridgeMeshData* FindMeshById(const FString& InMeshId) const
	{
		return Meshes.Find(InMeshId);
	}

	void RebuildIdMap()
	{
		IdToIndexMap.Empty(Objects.Num());
		for (int32 Idx = 0; Idx < Objects.Num(); ++Idx)
		{
			if (!Objects[Idx].Id.IsEmpty())
			{
				IdToIndexMap.Add(Objects[Idx].Id, Idx);
			}
		}
	}
};
