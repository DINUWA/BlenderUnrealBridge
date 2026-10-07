#include "Reader/BridgePackageValidator.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/Paths.h"

const FString FBridgePackageValidator::SupportedFormat = TEXT("BUBRIDGE");
const int32 FBridgePackageValidator::SupportedMajorVersion = 0;
const int32 FBridgePackageValidator::SupportedMinorVersion = 1;

bool FBridgePackageValidator::IsValidBridgeId(const FString& Id)
{
	// Expected format: "obj_" followed by at least 8 hexadecimal characters
	if (!Id.StartsWith(TEXT("obj_")) || Id.Len() < 12)
	{
		return false;
	}

	for (int32 i = 4; i < Id.Len(); ++i)
	{
		TCHAR C = Id[i];
		if (!FChar::IsHexDigit(C))
		{
			return false;
		}
	}

	return true;
}

bool FBridgePackageValidator::IsValidMeshId(const FString& Id)
{
	// Expected format: "mesh_" followed by at least 8 hexadecimal characters
	if (!Id.StartsWith(TEXT("mesh_")) || Id.Len() < 13)
	{
		return false;
	}

	for (int32 i = 5; i < Id.Len(); ++i)
	{
		TCHAR C = Id[i];
		if (!FChar::IsHexDigit(C))
		{
			return false;
		}
	}

	return true;
}

bool FBridgePackageValidator::IsValidMaterialId(const FString& Id)
{
	// Expected format: "mat_" followed by at least 8 hexadecimal characters
	if (!Id.StartsWith(TEXT("mat_")) || Id.Len() < 12)
	{
		return false;
	}

	for (int32 i = 4; i < Id.Len(); ++i)
	{
		TCHAR C = Id[i];
		if (!FChar::IsHexDigit(C))
		{
			return false;
		}
	}

	return true;
}

bool FBridgePackageValidator::IsValidTextureId(const FString& Id)
{
	// Expected format: "tex_" followed by at least 8 hexadecimal characters
	if (!Id.StartsWith(TEXT("tex_")) || Id.Len() < 12)
	{
		return false;
	}

	for (int32 i = 4; i < Id.Len(); ++i)
	{
		TCHAR C = Id[i];
		if (!FChar::IsHexDigit(C))
		{
			return false;
		}
	}

	return true;
}

bool FBridgePackageValidator::ValidatePackage(
	const FBridgePackageData& PackageData,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	bValid &= ValidateManifest(PackageData.Manifest, OutReport);
	bValid &= ValidateScene(PackageData.Scene, OutReport);
	bValid &= ValidateObjects(PackageData.Objects, OutReport);
	bValid &= ValidateMeshes(PackageData.Meshes, PackageData.Objects, OutReport);
	bValid &= ValidateMaterials(PackageData.Materials, PackageData.Meshes, PackageData.Objects, OutReport);
	bValid &= ValidateTextures(PackageData.Textures, PackageData.Materials, PackageData.PackageDirectory, OutReport);

	return bValid && OutReport.IsValid();
}

bool FBridgePackageValidator::ValidateManifest(
	const FBridgeManifest& Manifest,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	// Format check
	if (Manifest.Format != SupportedFormat)
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_FORMAT"),
			FString::Printf(TEXT("Expected format '%s', got '%s'"), *SupportedFormat, *Manifest.Format));
		bValid = false;
	}

	// Version check (SemVer: Major.Minor.Patch)
	TArray<FString> VersionParts;
	Manifest.Version.ParseIntoArray(VersionParts, TEXT("."));
	if (VersionParts.Num() < 2)
	{
		OutReport.AddError(
			TEXT("MANIFEST_MALFORMED_VERSION"),
			FString::Printf(TEXT("Malformed protocol version string '%s'"), *Manifest.Version));
		bValid = false;
	}
	else
	{
		int32 Major = FCString::Atoi(*VersionParts[0]);
		int32 Minor = FCString::Atoi(*VersionParts[1]);

		if (Major != SupportedMajorVersion)
		{
			OutReport.AddError(
				TEXT("MANIFEST_UNSUPPORTED_MAJOR_VERSION"),
				FString::Printf(TEXT("Unsupported protocol major version '%d'. Supported major version is '%d'"),
					Major, SupportedMajorVersion));
			bValid = false;
		}
		else if (Minor > SupportedMinorVersion)
		{
			OutReport.AddWarning(
				TEXT("MANIFEST_NEWER_MINOR_VERSION"),
				FString::Printf(TEXT("Package protocol minor version '%d' is newer than reader supported minor version '%d'. Processing with compatibility mode."),
					Minor, SupportedMinorVersion));
		}
	}

	// Coordinate system check (DATA_PROTOCOL.md §3)
	if (Manifest.CoordinateSystem.UpAxis != TEXT("Z"))
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_UP_AXIS"),
			FString::Printf(TEXT("Expected up_axis 'Z', got '%s'"), *Manifest.CoordinateSystem.UpAxis));
		bValid = false;
	}
	if (Manifest.CoordinateSystem.ForwardAxis != TEXT("X"))
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_FORWARD_AXIS"),
			FString::Printf(TEXT("Expected forward_axis 'X', got '%s'"), *Manifest.CoordinateSystem.ForwardAxis));
		bValid = false;
	}
	if (Manifest.CoordinateSystem.RightAxis != TEXT("Y"))
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_RIGHT_AXIS"),
			FString::Printf(TEXT("Expected right_axis 'Y', got '%s'"), *Manifest.CoordinateSystem.RightAxis));
		bValid = false;
	}
	if (Manifest.CoordinateSystem.Handedness != TEXT("left_handed"))
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_HANDEDNESS"),
			FString::Printf(TEXT("Expected handedness 'left_handed', got '%s'"), *Manifest.CoordinateSystem.Handedness));
		bValid = false;
	}
	if (Manifest.CoordinateSystem.Unit != TEXT("centimeter"))
	{
		OutReport.AddError(
			TEXT("MANIFEST_INVALID_UNIT"),
			FString::Printf(TEXT("Expected canonical unit 'centimeter', got '%s'"), *Manifest.CoordinateSystem.Unit));
		bValid = false;
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateScene(
	const FBridgeScene& Scene,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	if (Scene.Name.IsEmpty())
	{
		OutReport.AddError(TEXT("SCENE_MISSING_NAME"), TEXT("Scene metadata 'name' is empty"));
		bValid = false;
	}

	TSet<FString> CollectionIds;
	for (const FBridgeCollection& Col : Scene.Collections)
	{
		if (Col.Id.IsEmpty())
		{
			OutReport.AddError(TEXT("COLLECTION_MISSING_ID"), TEXT("Collection is missing an ID"));
			bValid = false;
			continue;
		}

		if (CollectionIds.Contains(Col.Id))
		{
			OutReport.AddError(
				TEXT("COLLECTION_DUPLICATE_ID"),
				FString::Printf(TEXT("Duplicate collection ID detected: '%s'"), *Col.Id),
				Col.Id);
			bValid = false;
		}
		CollectionIds.Add(Col.Id);
	}

	// Validate collection parent hierarchy references
	for (const FBridgeCollection& Col : Scene.Collections)
	{
		if (!Col.ParentId.IsEmpty() && !CollectionIds.Contains(Col.ParentId))
		{
			OutReport.AddError(
				TEXT("COLLECTION_BROKEN_PARENT"),
				FString::Printf(TEXT("Collection '%s' references non-existent parent collection '%s'"), *Col.Id, *Col.ParentId),
				Col.Id);
			bValid = false;
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateObjects(
	const TArray<FBridgeObject>& Objects,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;
	TSet<FString> SeenIds;
	TMap<FString, FString> ParentMap;

	for (const FBridgeObject& Obj : Objects)
	{
		// 1. ID format and uniqueness
		if (Obj.Id.IsEmpty())
		{
			OutReport.AddError(
				TEXT("OBJECT_MISSING_ID"),
				FString::Printf(TEXT("Object '%s' is missing a Bridge ID"), *Obj.Name));
			bValid = false;
			continue;
		}

		if (!IsValidBridgeId(Obj.Id))
		{
			OutReport.AddError(
				TEXT("OBJECT_INVALID_ID_FORMAT"),
				FString::Printf(TEXT("Object '%s' has malformed Bridge ID '%s' (must be 'obj_<hex>')"), *Obj.Name, *Obj.Id),
				Obj.Id);
			bValid = false;
		}

		if (SeenIds.Contains(Obj.Id))
		{
			OutReport.AddError(
				TEXT("OBJECT_DUPLICATE_ID"),
				FString::Printf(TEXT("Duplicate Bridge ID detected: '%s' on object '%s'"), *Obj.Id, *Obj.Name),
				Obj.Id);
			bValid = false;
		}
		SeenIds.Add(Obj.Id);

		ParentMap.Add(Obj.Id, Obj.ParentId);

		// 2. Object type check
		if (Obj.Type != TEXT("STATIC_MESH") && Obj.Type != TEXT("EMPTY") && Obj.Type != TEXT("CURVE"))
		{
			OutReport.AddWarning(
				TEXT("OBJECT_UNRECOGNIZED_TYPE"),
				FString::Printf(TEXT("Object '%s' has unrecognized/future type '%s'. Preserved as empty node."), *Obj.Name, *Obj.Type),
				Obj.Id);
		}

		// 3. Transform finite numeric validation
		const FBridgeCanonicalTransform& Xform = Obj.Transform;
		if (!FMath::IsFinite(Xform.Location.X) || !FMath::IsFinite(Xform.Location.Y) || !FMath::IsFinite(Xform.Location.Z))
		{
			OutReport.AddError(
				TEXT("TRANSFORM_NON_FINITE_LOCATION"),
				FString::Printf(TEXT("Object '%s' (%s) contains non-finite location values"), *Obj.Name, *Obj.Id),
				Obj.Id);
			bValid = false;
		}

		if (!FMath::IsFinite(Xform.RotationQuaternion.X) || !FMath::IsFinite(Xform.RotationQuaternion.Y) ||
			!FMath::IsFinite(Xform.RotationQuaternion.Z) || !FMath::IsFinite(Xform.RotationQuaternion.W))
		{
			OutReport.AddError(
				TEXT("TRANSFORM_NON_FINITE_QUATERNION"),
				FString::Printf(TEXT("Object '%s' (%s) contains non-finite rotation quaternion values"), *Obj.Name, *Obj.Id),
				Obj.Id);
			bValid = false;
		}
		else
		{
			float LengthSq = Xform.RotationQuaternion.SizeSquared();
			if (FMath::Abs(LengthSq - 1.0f) > 0.05f)
			{
				OutReport.AddWarning(
					TEXT("TRANSFORM_QUATERNION_NOT_NORMALIZED"),
					FString::Printf(TEXT("Object '%s' (%s) quaternion is not normalized (length^2 = %.4f)"), *Obj.Name, *Obj.Id, LengthSq),
					Obj.Id);
			}
		}

		if (!FMath::IsFinite(Xform.Scale.X) || !FMath::IsFinite(Xform.Scale.Y) || !FMath::IsFinite(Xform.Scale.Z))
		{
			OutReport.AddError(
				TEXT("TRANSFORM_NON_FINITE_SCALE"),
				FString::Printf(TEXT("Object '%s' (%s) contains non-finite scale values"), *Obj.Name, *Obj.Id),
				Obj.Id);
			bValid = false;
		}
	}

	// 4. Hierarchy referential integrity & cycle detection
	for (const auto& Pair : ParentMap)
	{
		const FString& ChildId = Pair.Key;
		const FString& ParentId = Pair.Value;

		if (!ParentId.IsEmpty())
		{
			if (ParentId == ChildId)
			{
				OutReport.AddError(
					TEXT("OBJECT_SELF_PARENT"),
					FString::Printf(TEXT("Object '%s' cannot be its own parent"), *ChildId),
					ChildId);
				bValid = false;
			}
			else if (!SeenIds.Contains(ParentId))
			{
				OutReport.AddError(
					TEXT("OBJECT_BROKEN_PARENT_REF"),
					FString::Printf(TEXT("Object '%s' references non-existent parent '%s'"), *ChildId, *ParentId),
					ChildId);
				bValid = false;
			}
		}
	}

	// Cycle detection
	for (const FString& StartId : SeenIds)
	{
		TSet<FString> VisitedInPath;
		FString CurrentId = StartId;

		while (!CurrentId.IsEmpty())
		{
			if (VisitedInPath.Contains(CurrentId))
			{
				OutReport.AddError(
					TEXT("OBJECT_HIERARCHY_CYCLE"),
					FString::Printf(TEXT("Hierarchy cycle detected involving object '%s'"), *CurrentId),
					CurrentId);
				bValid = false;
				break;
			}
			VisitedInPath.Add(CurrentId);

			const FString* NextParent = ParentMap.Find(CurrentId);
			CurrentId = (NextParent && !NextParent->IsEmpty()) ? *NextParent : TEXT("");
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateMesh(
	const FBridgeMeshData& Mesh,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	if (Mesh.Format != TEXT("BUBRIDGE_MESH"))
	{
		OutReport.AddError(
			TEXT("MESH_INVALID_FORMAT"),
			FString::Printf(TEXT("Mesh '%s' format must be 'BUBRIDGE_MESH', got '%s'"), *Mesh.MeshId, *Mesh.Format),
			Mesh.MeshId);
		bValid = false;
	}

	if (!IsValidMeshId(Mesh.MeshId))
	{
		OutReport.AddError(
			TEXT("MESH_INVALID_ID_FORMAT"),
			FString::Printf(TEXT("Mesh '%s' has malformed Bridge Mesh ID '%s' (must be 'mesh_<hex>')"), *Mesh.Name, *Mesh.MeshId),
			Mesh.MeshId);
		bValid = false;
	}

	// Vertices check
	int32 VertCount = Mesh.Vertices.Num();
	for (int32 i = 0; i < VertCount; ++i)
	{
		const FVector3f& V = Mesh.Vertices[i];
		if (!FMath::IsFinite(V.X) || !FMath::IsFinite(V.Y) || !FMath::IsFinite(V.Z))
		{
			OutReport.AddError(
				TEXT("MESH_NON_FINITE_COORDINATE"),
				FString::Printf(TEXT("Mesh '%s' vertex %d contains non-finite coordinates"), *Mesh.MeshId, i),
				Mesh.MeshId);
			bValid = false;
			break;
		}
	}

	// Triangles check
	int32 SlotCount = Mesh.MaterialSlots.Num();
	for (int32 t = 0; t < Mesh.Triangles.Num(); ++t)
	{
		const FBridgeMeshTriangle& Tri = Mesh.Triangles[t];
		for (int32 Corner = 0; Corner < 3; ++Corner)
		{
			int32 VIdx = Tri.VertexIndices[Corner];
			if (VIdx < 0 || VIdx >= VertCount)
			{
				OutReport.AddError(
					TEXT("MESH_INDEX_OUT_OF_BOUNDS"),
					FString::Printf(TEXT("Mesh '%s' triangle %d references out-of-bounds vertex index %d (vertex count: %d)"),
						*Mesh.MeshId, t, VIdx, VertCount),
					Mesh.MeshId);
				bValid = false;
				break;
			}

			const FVector3f& N = Tri.Normals[Corner];
			if (!FMath::IsFinite(N.X) || !FMath::IsFinite(N.Y) || !FMath::IsFinite(N.Z))
			{
				OutReport.AddError(
					TEXT("MESH_NON_FINITE_NORMAL"),
					FString::Printf(TEXT("Mesh '%s' triangle %d corner %d normal is non-finite"), *Mesh.MeshId, t, Corner),
					Mesh.MeshId);
				bValid = false;
				break;
			}

			const FVector2f& UV = Tri.UVs[Corner];
			if (!FMath::IsFinite(UV.X) || !FMath::IsFinite(UV.Y))
			{
				OutReport.AddError(
					TEXT("MESH_NON_FINITE_UV"),
					FString::Printf(TEXT("Mesh '%s' triangle %d corner %d UV is non-finite"), *Mesh.MeshId, t, Corner),
					Mesh.MeshId);
				bValid = false;
				break;
			}
		}

		if (SlotCount > 0 && (Tri.MaterialSlotIndex < 0 || Tri.MaterialSlotIndex >= SlotCount))
		{
			OutReport.AddError(
				TEXT("MESH_INVALID_MATERIAL_SLOT_INDEX"),
				FString::Printf(TEXT("Mesh '%s' triangle %d references invalid material slot %d (slot count: %d)"),
					*Mesh.MeshId, t, Tri.MaterialSlotIndex, SlotCount),
				Mesh.MeshId);
			bValid = false;
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateMeshes(
	const TMap<FString, FBridgeMeshData>& Meshes,
	const TArray<FBridgeObject>& Objects,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	// Validate individual meshes
	for (const auto& Pair : Meshes)
	{
		bValid &= ValidateMesh(Pair.Value, OutReport);
	}

	// Validate object mesh references
	for (const FBridgeObject& Obj : Objects)
	{
		if (Obj.Type == TEXT("STATIC_MESH") && Obj.MeshReference.IsValid())
		{
			const FString& MeshId = Obj.MeshReference.MeshId;
			if (!Meshes.Contains(MeshId))
			{
				OutReport.AddError(
					TEXT("OBJECT_BROKEN_MESH_REF"),
					FString::Printf(TEXT("Object '%s' references non-existent mesh '%s'"), *Obj.Name, *MeshId),
					Obj.Id);
				bValid = false;
			}
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateMaterial(
	const FBridgeMaterialData& Material,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	if (Material.Format != TEXT("BUBRIDGE_MATERIAL"))
	{
		OutReport.AddError(
			TEXT("MATERIAL_INVALID_FORMAT"),
			FString::Printf(TEXT("Material '%s' format must be 'BUBRIDGE_MATERIAL', got '%s'"), *Material.MaterialId, *Material.Format),
			Material.MaterialId);
		bValid = false;
	}

	if (!IsValidMaterialId(Material.MaterialId))
	{
		OutReport.AddError(
			TEXT("MATERIAL_INVALID_ID_FORMAT"),
			FString::Printf(TEXT("Material '%s' has malformed Bridge Material ID '%s' (must be 'mat_<hex>')"), *Material.Name, *Material.MaterialId),
			Material.MaterialId);
		bValid = false;
	}

	if (Material.Model != TEXT("PBR_METALLIC_ROUGHNESS"))
	{
		OutReport.AddError(
			TEXT("MATERIAL_INVALID_MODEL"),
			FString::Printf(TEXT("Material '%s' model must be 'PBR_METALLIC_ROUGHNESS', got '%s'"), *Material.MaterialId, *Material.Model),
			Material.MaterialId);
		bValid = false;
	}

	// Base color validation
	const FLinearColor& C = Material.BaseColor;
	if (!FMath::IsFinite(C.R) || !FMath::IsFinite(C.G) || !FMath::IsFinite(C.B) || !FMath::IsFinite(C.A) ||
		C.R < 0.0f || C.R > 1.0f || C.G < 0.0f || C.G > 1.0f || C.B < 0.0f || C.B > 1.0f || C.A < 0.0f || C.A > 1.0f)
	{
		OutReport.AddError(
			TEXT("MATERIAL_OUT_OF_RANGE_BASE_COLOR"),
			FString::Printf(TEXT("Material '%s' base_color channels must be finite numbers in [0.0, 1.0]"), *Material.MaterialId),
			Material.MaterialId);
		bValid = false;
	}

	// Metallic
	if (!FMath::IsFinite(Material.Metallic) || Material.Metallic < 0.0f || Material.Metallic > 1.0f)
	{
		OutReport.AddError(
			TEXT("MATERIAL_OUT_OF_RANGE_METALLIC"),
			FString::Printf(TEXT("Material '%s' metallic must be a finite number in [0.0, 1.0], got %f"), *Material.MaterialId, Material.Metallic),
			Material.MaterialId);
		bValid = false;
	}

	// Roughness
	if (!FMath::IsFinite(Material.Roughness) || Material.Roughness < 0.0f || Material.Roughness > 1.0f)
	{
		OutReport.AddError(
			TEXT("MATERIAL_OUT_OF_RANGE_ROUGHNESS"),
			FString::Printf(TEXT("Material '%s' roughness must be a finite number in [0.0, 1.0], got %f"), *Material.MaterialId, Material.Roughness),
			Material.MaterialId);
		bValid = false;
	}

	// Specular
	if (!FMath::IsFinite(Material.Specular) || Material.Specular < 0.0f || Material.Specular > 1.0f)
	{
		OutReport.AddError(
			TEXT("MATERIAL_OUT_OF_RANGE_SPECULAR"),
			FString::Printf(TEXT("Material '%s' specular must be a finite number in [0.0, 1.0], got %f"), *Material.MaterialId, Material.Specular),
			Material.MaterialId);
		bValid = false;
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateMaterials(
	const TMap<FString, FBridgeMaterialData>& Materials,
	const TMap<FString, FBridgeMeshData>& Meshes,
	const TArray<FBridgeObject>& Objects,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	// Validate individual materials
	for (const auto& Pair : Materials)
	{
		bValid &= ValidateMaterial(Pair.Value, OutReport);
	}

	// Validate object material slot references
	for (const FBridgeObject& Obj : Objects)
	{
		for (const FBridgeMaterialSlot& Slot : Obj.MaterialSlots)
		{
			if (!Slot.MaterialId.IsEmpty() && !Materials.Contains(Slot.MaterialId))
			{
				OutReport.AddError(
					TEXT("OBJECT_BROKEN_MATERIAL_REF"),
					FString::Printf(TEXT("Object '%s' slot '%s' references non-existent material '%s'"), *Obj.Name, *Slot.SlotName, *Slot.MaterialId),
					Obj.Id);
				bValid = false;
			}
		}
	}

	// Validate mesh material slot references
	for (const auto& MeshPair : Meshes)
	{
		const FBridgeMeshData& Mesh = MeshPair.Value;
		for (const FBridgeMaterialSlot& Slot : Mesh.MaterialSlots)
		{
			if (!Slot.MaterialId.IsEmpty() && !Materials.Contains(Slot.MaterialId))
			{
				OutReport.AddError(
					TEXT("MESH_BROKEN_MATERIAL_REF"),
					FString::Printf(TEXT("Mesh '%s' slot '%s' references non-existent material '%s'"), *Mesh.MeshId, *Slot.SlotName, *Slot.MaterialId),
					Mesh.MeshId);
				bValid = false;
			}
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateTexture(
	const FBridgeTextureData& Texture,
	const FString& PackageDirectory,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	if (!IsValidTextureId(Texture.Id))
	{
		OutReport.AddError(
			TEXT("TEXTURE_INVALID_ID_FORMAT"),
			FString::Printf(TEXT("Texture '%s' has malformed Bridge Texture ID '%s' (must be 'tex_<hex>')"), *Texture.Name, *Texture.Id),
			Texture.Id);
		bValid = false;
	}

	if (!Texture.RelativePath.StartsWith(TEXT("textures/")))
	{
		OutReport.AddError(
			TEXT("TEXTURE_INVALID_PATH"),
			FString::Printf(TEXT("Texture '%s' relative path must start with 'textures/', got '%s'"), *Texture.Id, *Texture.RelativePath),
			Texture.Id);
		bValid = false;
	}

	if (Texture.ColorSpace != TEXT("sRGB") && Texture.ColorSpace != TEXT("Linear"))
	{
		OutReport.AddError(
			TEXT("TEXTURE_INVALID_COLOR_SPACE"),
			FString::Printf(TEXT("Texture '%s' color space must be 'sRGB' or 'Linear', got '%s'"), *Texture.Id, *Texture.ColorSpace),
			Texture.Id);
		bValid = false;
	}

	if (Texture.Dimensions.X <= 0 || Texture.Dimensions.Y <= 0)
	{
		OutReport.AddError(
			TEXT("TEXTURE_INVALID_DIMENSIONS"),
			FString::Printf(TEXT("Texture '%s' dimensions must be positive integers, got (%d, %d)"), *Texture.Id, Texture.Dimensions.X, Texture.Dimensions.Y),
			Texture.Id);
		bValid = false;
	}

	if (Texture.Channels < 1 || Texture.Channels > 4)
	{
		OutReport.AddError(
			TEXT("TEXTURE_INVALID_CHANNELS"),
			FString::Printf(TEXT("Texture '%s' channels must be in [1, 4], got %d"), *Texture.Id, Texture.Channels),
			Texture.Id);
		bValid = false;
	}

	if (!PackageDirectory.IsEmpty() && !Texture.RelativePath.IsEmpty())
	{
		FString FullPath = FPaths::Combine(PackageDirectory, Texture.RelativePath);
		IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
		if (!PlatformFile.FileExists(*FullPath))
		{
			OutReport.AddError(
				TEXT("TEX_FILE_NOT_FOUND"),
				FString::Printf(TEXT("Texture file not found on disk: '%s'"), *FullPath),
				Texture.Id);
			bValid = false;
		}
	}

	return bValid;
}

bool FBridgePackageValidator::ValidateTextures(
	const TMap<FString, FBridgeTextureData>& Textures,
	const TMap<FString, FBridgeMaterialData>& Materials,
	const FString& PackageDirectory,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	for (const auto& Pair : Textures)
	{
		bValid &= ValidateTexture(Pair.Value, PackageDirectory, OutReport);
	}

	// Validate material -> texture references
	for (const auto& MatPair : Materials)
	{
		const FBridgeMaterialData& Mat = MatPair.Value;
		for (const auto& TexKvp : Mat.Textures)
		{
			const FString& Channel = TexKvp.Key;
			const FString& TexId = TexKvp.Value;

			if (!TexId.IsEmpty() && !Textures.Contains(TexId))
			{
				OutReport.AddError(
					TEXT("MATERIAL_BROKEN_TEXTURE_REF"),
					FString::Printf(TEXT("Material '%s' channel '%s' references non-existent texture '%s'"),
						*Mat.MaterialId, *Channel, *TexId),
					Mat.MaterialId);
				bValid = false;
			}
		}
	}

	return bValid;
}

