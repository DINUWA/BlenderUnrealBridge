#include "Mesh/BridgeMeshBuilder.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshDescription.h"

UStaticMesh* FBridgeMeshBuilder::CreateStaticMesh(
	UObject* Outer,
	const FName& Name,
	const FBridgeMeshData& MeshData,
	FBridgeValidationReport& OutReport)
{
	if (!Outer)
	{
		Outer = GetTransientPackage();
	}

	UStaticMesh* StaticMesh = NewObject<UStaticMesh>(Outer, Name, RF_Public | RF_Standalone);
	if (!StaticMesh)
	{
		OutReport.AddError(
			TEXT("STATIC_MESH_ALLOC_FAILED"),
			FString::Printf(TEXT("Failed to allocate UStaticMesh object '%s'"), *Name.ToString()),
			MeshData.MeshId);
		return nullptr;
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	TVertexAttributesRef<FVector3f> VertexPositions = Attributes.GetVertexPositions();
	TVertexInstanceAttributesRef<FVector3f> VertexNormals = Attributes.GetVertexInstanceNormals();
	TVertexInstanceAttributesRef<FVector2f> VertexUVs = Attributes.GetVertexInstanceUVs();
	TPolygonGroupAttributesRef<FName> MaterialSlotNames = Attributes.GetPolygonGroupMaterialSlotNames();

	VertexUVs.SetNumChannels(FMath::Max(1, MeshData.UVLayerCount));

	// 1. Add Vertices
	TArray<FVertexID> VertexIDs;
	VertexIDs.Reserve(MeshData.Vertices.Num());
	for (const FVector3f& Pos : MeshData.Vertices)
	{
		FVertexID VertexID = MeshDescription.CreateVertex();
		VertexPositions[VertexID] = Pos;
		VertexIDs.Add(VertexID);
	}

	// 2. Add Polygon Groups (Material Slots)
	TMap<int32, FPolygonGroupID> SlotToPolygonGroupMap;
	int32 NumSlots = FMath::Max(1, MeshData.MaterialSlots.Num());
	for (int32 SlotIdx = 0; SlotIdx < NumSlots; ++SlotIdx)
	{
		FName SlotFName = (MeshData.MaterialSlots.IsValidIndex(SlotIdx) && !MeshData.MaterialSlots[SlotIdx].SlotName.IsEmpty())
			? FName(*MeshData.MaterialSlots[SlotIdx].SlotName)
			: FName(*FString::Printf(TEXT("MaterialSlot_%d"), SlotIdx));

		FPolygonGroupID GroupID = MeshDescription.CreatePolygonGroup();
		MaterialSlotNames[GroupID] = SlotFName;
		SlotToPolygonGroupMap.Add(SlotIdx, GroupID);

		FStaticMaterial StaticMaterial;
		StaticMaterial.MaterialSlotName = SlotFName;
		StaticMaterial.ImportedMaterialSlotName = SlotFName;
		StaticMesh->GetStaticMaterials().Add(StaticMaterial);
	}

	// 3. Add Triangles
	for (const FBridgeMeshTriangle& Tri : MeshData.Triangles)
	{
		const FPolygonGroupID* GroupIDPtr = SlotToPolygonGroupMap.Find(Tri.MaterialSlotIndex);
		FPolygonGroupID GroupID = GroupIDPtr ? *GroupIDPtr : SlotToPolygonGroupMap[0];

		TArray<FVertexInstanceID> TriInstanceIDs;
		TriInstanceIDs.Reserve(3);

		for (int32 Corner = 0; Corner < 3; ++Corner)
		{
			int32 VIdx = Tri.VertexIndices[Corner];
			if (!VertexIDs.IsValidIndex(VIdx)) continue;

			FVertexInstanceID InstanceID = MeshDescription.CreateVertexInstance(VertexIDs[VIdx]);
			VertexNormals[InstanceID] = Tri.Normals[Corner];
			VertexUVs.Set(InstanceID, 0, Tri.UVs[Corner]);
			TriInstanceIDs.Add(InstanceID);
		}

		if (TriInstanceIDs.Num() == 3)
		{
			MeshDescription.CreateTriangle(GroupID, TriInstanceIDs);
		}
	}

	// 4. Build Static Mesh LOD Resources
	TArray<const FMeshDescription*> MeshDescriptionPtrs;
	MeshDescriptionPtrs.Add(&MeshDescription);

	UStaticMesh::FBuildMeshDescriptionsParams BuildParams;
	// Default params: bCommitMeshDescription=true, bFastBuild=false → full render data build.
	// Note: bBuildRenderData does NOT exist in UE 5.8's FBuildMeshDescriptionsParams.

	if (!StaticMesh->BuildFromMeshDescriptions(MeshDescriptionPtrs, BuildParams))
	{
		OutReport.AddError(
			TEXT("STATIC_MESH_BUILD_FAILED"),
			FString::Printf(TEXT("BuildFromMeshDescriptions failed for mesh '%s'"), *Name.ToString()),
			MeshData.MeshId);
		return nullptr;
	}

	OutReport.AddInfo(
		TEXT("STATIC_MESH_BUILD_SUCCESS"),
		FString::Printf(TEXT("Successfully created UStaticMesh '%s' with %d vertices and %d triangles"),
			*Name.ToString(), MeshData.Vertices.Num(), MeshData.Triangles.Num()),
		MeshData.MeshId);

	return StaticMesh;
}
