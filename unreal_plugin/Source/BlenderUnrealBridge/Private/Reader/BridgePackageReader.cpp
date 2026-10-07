#include "Reader/BridgePackageReader.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformFileManager.h"

bool FBridgePackageReader::LoadPackage(
	const FString& PackageDirectory,
	FBridgePackageData& OutPackageData,
	FBridgeValidationReport& OutReport)
{
	OutReport.AddInfo(TEXT("PACKAGE_LOAD_START"), FString::Printf(TEXT("Loading Bridge package from '%s'"), *PackageDirectory));

	// 1. Verify directory and required files
	if (!VerifyPackageStructure(PackageDirectory, OutReport))
	{
		return false;
	}

	OutPackageData.PackageDirectory = PackageDirectory;

	// 2. Parse manifest.json
	FString ManifestPath = FPaths::Combine(PackageDirectory, TEXT("manifest.json"));
	TSharedPtr<FJsonObject> ManifestJson;
	if (!ReadJsonFile(ManifestPath, ManifestJson, OutReport) || !ParseManifest(ManifestJson, OutPackageData.Manifest, OutReport))
	{
		return false;
	}

	// 3. Parse scene.json
	FString ScenePath = FPaths::Combine(PackageDirectory, TEXT("scene.json"));
	TSharedPtr<FJsonObject> SceneJson;
	if (!ReadJsonFile(ScenePath, SceneJson, OutReport) || !ParseScene(SceneJson, OutPackageData.Scene, OutReport))
	{
		return false;
	}

	// 4. Parse objects.json
	FString ObjectsPath = FPaths::Combine(PackageDirectory, TEXT("objects.json"));
	TSharedPtr<FJsonObject> ObjectsJson;
	if (!ReadJsonFile(ObjectsPath, ObjectsJson, OutReport) || !ParseObjects(ObjectsJson, OutPackageData.Objects, OutReport))
	{
		return false;
	}

	// 5. Load referenced mesh assets from meshes/
	LoadMeshes(PackageDirectory, OutPackageData.Objects, OutPackageData.Meshes, OutReport);

	// 6. Load material assets from materials/
	LoadMaterials(PackageDirectory, OutPackageData.Materials, OutReport);

	// 7. Build fast lookup ID map
	OutPackageData.RebuildIdMap();

	// 8. Execute full protocol validation
	if (!FBridgePackageValidator::ValidatePackage(OutPackageData, OutReport))
	{
		OutReport.AddError(TEXT("PACKAGE_VALIDATION_FAILED"), TEXT("Package metadata, meshes, materials, or hierarchy failed validation"));
		return false;
	}

	OutReport.AddInfo(TEXT("PACKAGE_LOAD_SUCCESS"), FString::Printf(TEXT("Successfully loaded package '%s' with %d objects, %d meshes, and %d materials"),
		*OutPackageData.Scene.Name, OutPackageData.Objects.Num(), OutPackageData.Meshes.Num(), OutPackageData.Materials.Num()));

	return true;
}

bool FBridgePackageReader::VerifyPackageStructure(
	const FString& PackageDirectory,
	FBridgeValidationReport& OutReport)
{
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	if (!PlatformFile.DirectoryExists(*PackageDirectory))
	{
		OutReport.AddError(
			TEXT("PACKAGE_DIR_NOT_FOUND"),
			FString::Printf(TEXT("Package directory does not exist: '%s'"), *PackageDirectory));
		return false;
	}

	const TCHAR* RequiredFiles[] = {
		TEXT("manifest.json"),
		TEXT("scene.json"),
		TEXT("objects.json")
	};

	bool bAllExist = true;
	for (const TCHAR* Filename : RequiredFiles)
	{
		FString FullPath = FPaths::Combine(PackageDirectory, Filename);
		if (!PlatformFile.FileExists(*FullPath))
		{
			OutReport.AddError(
				TEXT("PACKAGE_MISSING_FILE"),
				FString::Printf(TEXT("Required package file missing: '%s'"), Filename));
			bAllExist = false;
		}
	}

	return bAllExist;
}

bool FBridgePackageReader::ReadJsonFile(
	const FString& FilePath,
	TSharedPtr<FJsonObject>& OutJsonObject,
	FBridgeValidationReport& OutReport)
{
	FString JsonString;
	if (!FFileHelper::LoadFileToString(JsonString, *FilePath))
	{
		OutReport.AddError(
			TEXT("FILE_READ_FAILED"),
			FString::Printf(TEXT("Failed to read file: '%s'"), *FilePath));
		return false;
	}

	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
	if (!FJsonSerializer::Deserialize(Reader, OutJsonObject) || !OutJsonObject.IsValid())
	{
		OutReport.AddError(
			TEXT("JSON_PARSE_FAILED"),
			FString::Printf(TEXT("Failed to parse JSON file: '%s'"), *FilePath));
		return false;
	}

	return true;
}

bool FBridgePackageReader::ParseManifest(
	const TSharedPtr<FJsonObject>& JsonObject,
	FBridgeManifest& OutManifest,
	FBridgeValidationReport& OutReport)
{
	if (!JsonObject->TryGetStringField(TEXT("format"), OutManifest.Format))
	{
		OutReport.AddError(TEXT("MANIFEST_MISSING_FIELD"), TEXT("manifest.json is missing 'format'"));
		return false;
	}

	if (!JsonObject->TryGetStringField(TEXT("version"), OutManifest.Version))
	{
		OutReport.AddError(TEXT("MANIFEST_MISSING_FIELD"), TEXT("manifest.json is missing 'version'"));
		return false;
	}

	JsonObject->TryGetStringField(TEXT("created_at"), OutManifest.CreatedAt);

	// Generator
	const TSharedPtr<FJsonObject>* GenObj;
	if (JsonObject->TryGetObjectField(TEXT("generator"), GenObj) && GenObj)
	{
		(*GenObj)->TryGetStringField(TEXT("name"), OutManifest.GeneratorName);
		(*GenObj)->TryGetStringField(TEXT("version"), OutManifest.GeneratorVersion);
	}

	// Source
	const TSharedPtr<FJsonObject>* SourceObj;
	if (JsonObject->TryGetObjectField(TEXT("source"), SourceObj) && SourceObj)
	{
		(*SourceObj)->TryGetStringField(TEXT("application"), OutManifest.SourceApplication);
		(*SourceObj)->TryGetStringField(TEXT("version"), OutManifest.SourceVersion);
		(*SourceObj)->TryGetStringField(TEXT("scene_name"), OutManifest.SourceSceneName);
		(*SourceObj)->TryGetStringField(TEXT("unit_length"), OutManifest.SourceUnitLength);
		double ScaleVal = 1.0;
		if ((*SourceObj)->TryGetNumberField(TEXT("unit_scale"), ScaleVal))
		{
			OutManifest.SourceUnitScale = static_cast<float>(ScaleVal);
		}
	}

	// Coordinate System
	const TSharedPtr<FJsonObject>* CoordObj;
	if (JsonObject->TryGetObjectField(TEXT("coordinate_system"), CoordObj) && CoordObj)
	{
		(*CoordObj)->TryGetStringField(TEXT("up_axis"), OutManifest.CoordinateSystem.UpAxis);
		(*CoordObj)->TryGetStringField(TEXT("forward_axis"), OutManifest.CoordinateSystem.ForwardAxis);
		(*CoordObj)->TryGetStringField(TEXT("right_axis"), OutManifest.CoordinateSystem.RightAxis);
		(*CoordObj)->TryGetStringField(TEXT("handedness"), OutManifest.CoordinateSystem.Handedness);
		(*CoordObj)->TryGetStringField(TEXT("unit"), OutManifest.CoordinateSystem.Unit);
	}

	// Content summary
	const TSharedPtr<FJsonObject>* SummaryObj;
	if (JsonObject->TryGetObjectField(TEXT("content_summary"), SummaryObj) && SummaryObj)
	{
		(*SummaryObj)->TryGetNumberField(TEXT("object_count"), OutManifest.ContentSummary.ObjectCount);
		(*SummaryObj)->TryGetNumberField(TEXT("mesh_count"), OutManifest.ContentSummary.MeshCount);
		(*SummaryObj)->TryGetNumberField(TEXT("material_count"), OutManifest.ContentSummary.MaterialCount);
		(*SummaryObj)->TryGetNumberField(TEXT("texture_count"), OutManifest.ContentSummary.TextureCount);
	}

	return true;
}

bool FBridgePackageReader::ParseScene(
	const TSharedPtr<FJsonObject>& JsonObject,
	FBridgeScene& OutScene,
	FBridgeValidationReport& OutReport)
{
	if (!JsonObject->TryGetStringField(TEXT("name"), OutScene.Name))
	{
		OutReport.AddError(TEXT("SCENE_MISSING_FIELD"), TEXT("scene.json is missing 'name'"));
		return false;
	}

	// Collections
	const TArray<TSharedPtr<FJsonValue>>* ColArray;
	if (JsonObject->TryGetArrayField(TEXT("collections"), ColArray) && ColArray)
	{
		for (const TSharedPtr<FJsonValue>& ColVal : *ColArray)
		{
			const TSharedPtr<FJsonObject>& ColObj = ColVal->AsObject();
			if (ColObj.IsValid())
			{
				FBridgeCollection Col;
				ColObj->TryGetStringField(TEXT("id"), Col.Id);
				ColObj->TryGetStringField(TEXT("name"), Col.Name);
				ColObj->TryGetStringField(TEXT("parent_id"), Col.ParentId);
				ColObj->TryGetStringField(TEXT("color_tag"), Col.ColorTag);
				OutScene.Collections.Add(Col);
			}
		}
	}

	return true;
}

bool FBridgePackageReader::ParseObjects(
	const TSharedPtr<FJsonObject>& JsonObject,
	TArray<FBridgeObject>& OutObjects,
	FBridgeValidationReport& OutReport)
{
	const TArray<TSharedPtr<FJsonValue>>* ObjsArray;
	if (!JsonObject->TryGetArrayField(TEXT("objects"), ObjsArray) || !ObjsArray)
	{
		OutReport.AddError(TEXT("OBJECTS_MISSING_ARRAY"), TEXT("objects.json is missing 'objects' array"));
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Item : *ObjsArray)
	{
		const TSharedPtr<FJsonObject>& ObjEntry = Item->AsObject();
		if (!ObjEntry.IsValid())
		{
			continue;
		}

		FBridgeObject BridgeObj;
		ObjEntry->TryGetStringField(TEXT("id"), BridgeObj.Id);
		ObjEntry->TryGetStringField(TEXT("name"), BridgeObj.Name);
		ObjEntry->TryGetStringField(TEXT("type"), BridgeObj.Type);
		ObjEntry->TryGetBoolField(TEXT("visible"), BridgeObj.bVisible);
		ObjEntry->TryGetStringField(TEXT("collection_id"), BridgeObj.CollectionId);
		ObjEntry->TryGetStringField(TEXT("parent_id"), BridgeObj.ParentId);

		const TSharedPtr<FJsonObject>* XformObj;
		if (ObjEntry->TryGetObjectField(TEXT("transform"), XformObj) && XformObj)
		{
			ParseTransform(*XformObj, BridgeObj.Id, BridgeObj.Name, BridgeObj.Transform, OutReport);
		}
		else
		{
			OutReport.AddError(
				TEXT("OBJECT_MISSING_TRANSFORM"),
				FString::Printf(TEXT("Object '%s' (%s) missing 'transform' block"), *BridgeObj.Name, *BridgeObj.Id),
				BridgeObj.Id);
		}

		// Parse mesh reference if present
		const TSharedPtr<FJsonObject>* MeshRefObj;
		if (ObjEntry->TryGetObjectField(TEXT("mesh_reference"), MeshRefObj) && MeshRefObj && (*MeshRefObj).IsValid())
		{
			(*MeshRefObj)->TryGetStringField(TEXT("mesh_id"), BridgeObj.MeshReference.MeshId);
			(*MeshRefObj)->TryGetStringField(TEXT("file"), BridgeObj.MeshReference.File);
			(*MeshRefObj)->TryGetNumberField(TEXT("submesh_index"), BridgeObj.MeshReference.SubmeshIndex);
		}

		// Parse material slots if present
		const TArray<TSharedPtr<FJsonValue>>* MatSlotsArray;
		if (ObjEntry->TryGetArrayField(TEXT("material_slots"), MatSlotsArray) && MatSlotsArray)
		{
			for (const TSharedPtr<FJsonValue>& SlotVal : *MatSlotsArray)
			{
				const TSharedPtr<FJsonObject>& SlotObj = SlotVal->AsObject();
				if (SlotObj.IsValid())
				{
					FBridgeMaterialSlot Slot;
					SlotObj->TryGetNumberField(TEXT("slot_index"), Slot.SlotIndex);
					SlotObj->TryGetStringField(TEXT("slot_name"), Slot.SlotName);
					SlotObj->TryGetStringField(TEXT("material_id"), Slot.MaterialId);
					BridgeObj.MaterialSlots.Add(Slot);
				}
			}
		}

		OutObjects.Add(BridgeObj);
	}

	return true;
}

bool FBridgePackageReader::ParseTransform(
	const TSharedPtr<FJsonObject>& JsonObject,
	const FString& ObjectId,
	const FString& ObjectName,
	FBridgeCanonicalTransform& OutTransform,
	FBridgeValidationReport& OutReport)
{
	// Location [X, Y, Z]
	const TArray<TSharedPtr<FJsonValue>>* LocArray;
	if (JsonObject->TryGetArrayField(TEXT("location"), LocArray) && LocArray && LocArray->Num() == 3)
	{
		OutTransform.Location.X = static_cast<float>((*LocArray)[0]->AsNumber());
		OutTransform.Location.Y = static_cast<float>((*LocArray)[1]->AsNumber());
		OutTransform.Location.Z = static_cast<float>((*LocArray)[2]->AsNumber());
	}
	else
	{
		OutReport.AddError(
			TEXT("TRANSFORM_MALFORMED_LOCATION"),
			FString::Printf(TEXT("Object '%s' (%s) transform has malformed 'location'"), *ObjectName, *ObjectId),
			ObjectId);
	}

	// Quaternion [X, Y, Z, W]
	const TArray<TSharedPtr<FJsonValue>>* QuatArray;
	if (JsonObject->TryGetArrayField(TEXT("rotation_quaternion"), QuatArray) && QuatArray && QuatArray->Num() == 4)
	{
		OutTransform.RotationQuaternion.X = static_cast<float>((*QuatArray)[0]->AsNumber());
		OutTransform.RotationQuaternion.Y = static_cast<float>((*QuatArray)[1]->AsNumber());
		OutTransform.RotationQuaternion.Z = static_cast<float>((*QuatArray)[2]->AsNumber());
		OutTransform.RotationQuaternion.W = static_cast<float>((*QuatArray)[3]->AsNumber());
	}
	else
	{
		OutReport.AddError(
			TEXT("TRANSFORM_MALFORMED_QUATERNION"),
			FString::Printf(TEXT("Object '%s' (%s) transform has malformed 'rotation_quaternion'"), *ObjectName, *ObjectId),
			ObjectId);
	}

	// Euler
	const TArray<TSharedPtr<FJsonValue>>* EulerArray;
	if (JsonObject->TryGetArrayField(TEXT("rotation_euler"), EulerArray) && EulerArray && EulerArray->Num() == 3)
	{
		OutTransform.RotationEuler.X = static_cast<float>((*EulerArray)[0]->AsNumber());
		OutTransform.RotationEuler.Y = static_cast<float>((*EulerArray)[1]->AsNumber());
		OutTransform.RotationEuler.Z = static_cast<float>((*EulerArray)[2]->AsNumber());
	}

	JsonObject->TryGetStringField(TEXT("rotation_mode"), OutTransform.RotationMode);

	// Scale
	const TArray<TSharedPtr<FJsonValue>>* ScaleArray;
	if (JsonObject->TryGetArrayField(TEXT("scale"), ScaleArray) && ScaleArray && ScaleArray->Num() == 3)
	{
		OutTransform.Scale.X = static_cast<float>((*ScaleArray)[0]->AsNumber());
		OutTransform.Scale.Y = static_cast<float>((*ScaleArray)[1]->AsNumber());
		OutTransform.Scale.Z = static_cast<float>((*ScaleArray)[2]->AsNumber());
	}
	else
	{
		OutReport.AddError(
			TEXT("TRANSFORM_MALFORMED_SCALE"),
			FString::Printf(TEXT("Object '%s' (%s) transform has malformed 'scale'"), *ObjectName, *ObjectId),
			ObjectId);
	}

	JsonObject->TryGetBoolField(TEXT("has_negative_scale"), OutTransform.bHasNegativeScale);

	return true;
}

bool FBridgePackageReader::ParseMesh(
	const TSharedPtr<FJsonObject>& JsonObject,
	FBridgeMeshData& OutMesh,
	FBridgeValidationReport& OutReport)
{
	JsonObject->TryGetStringField(TEXT("format"), OutMesh.Format);
	JsonObject->TryGetStringField(TEXT("version"), OutMesh.Version);
	JsonObject->TryGetStringField(TEXT("mesh_id"), OutMesh.MeshId);
	JsonObject->TryGetStringField(TEXT("name"), OutMesh.Name);

	// Counts
	const TSharedPtr<FJsonObject>* CountsObj;
	if (JsonObject->TryGetObjectField(TEXT("counts"), CountsObj) && CountsObj)
	{
		(*CountsObj)->TryGetNumberField(TEXT("vertex_count"), OutMesh.VertexCount);
		(*CountsObj)->TryGetNumberField(TEXT("triangle_count"), OutMesh.TriangleCount);
		(*CountsObj)->TryGetNumberField(TEXT("uv_layer_count"), OutMesh.UVLayerCount);
		(*CountsObj)->TryGetNumberField(TEXT("material_slot_count"), OutMesh.MaterialSlotCount);
	}

	// Bounds
	const TSharedPtr<FJsonObject>* BoundsObj;
	if (JsonObject->TryGetObjectField(TEXT("bounds"), BoundsObj) && BoundsObj)
	{
		const TArray<TSharedPtr<FJsonValue>>* MinArray;
		if ((*BoundsObj)->TryGetArrayField(TEXT("min"), MinArray) && MinArray && MinArray->Num() == 3)
		{
			OutMesh.Bounds.Min = FVector3f(
				static_cast<float>((*MinArray)[0]->AsNumber()),
				static_cast<float>((*MinArray)[1]->AsNumber()),
				static_cast<float>((*MinArray)[2]->AsNumber()));
		}
		const TArray<TSharedPtr<FJsonValue>>* MaxArray;
		if ((*BoundsObj)->TryGetArrayField(TEXT("max"), MaxArray) && MaxArray && MaxArray->Num() == 3)
		{
			OutMesh.Bounds.Max = FVector3f(
				static_cast<float>((*MaxArray)[0]->AsNumber()),
				static_cast<float>((*MaxArray)[1]->AsNumber()),
				static_cast<float>((*MaxArray)[2]->AsNumber()));
		}
	}

	// Vertices
	const TArray<TSharedPtr<FJsonValue>>* VertArray;
	if (JsonObject->TryGetArrayField(TEXT("vertices"), VertArray) && VertArray)
	{
		OutMesh.Vertices.Reserve(VertArray->Num());
		for (const TSharedPtr<FJsonValue>& VVal : *VertArray)
		{
			const TArray<TSharedPtr<FJsonValue>>* CoArray;
			if (VVal->TryGetArray(CoArray) && CoArray && CoArray->Num() == 3)
			{
				OutMesh.Vertices.Add(FVector3f(
					static_cast<float>((*CoArray)[0]->AsNumber()),
					static_cast<float>((*CoArray)[1]->AsNumber()),
					static_cast<float>((*CoArray)[2]->AsNumber())));
			}
		}
	}

	// Triangles
	const TArray<TSharedPtr<FJsonValue>>* TriArray;
	if (JsonObject->TryGetArrayField(TEXT("triangles"), TriArray) && TriArray)
	{
		OutMesh.Triangles.Reserve(TriArray->Num());
		for (const TSharedPtr<FJsonValue>& TVal : *TriArray)
		{
			const TSharedPtr<FJsonObject>& TriObj = TVal->AsObject();
			if (!TriObj.IsValid()) continue;

			FBridgeMeshTriangle Tri;
			TriObj->TryGetNumberField(TEXT("material_slot_index"), Tri.MaterialSlotIndex);

			const TArray<TSharedPtr<FJsonValue>>* IdxArray;
			if (TriObj->TryGetArrayField(TEXT("vertex_indices"), IdxArray) && IdxArray && IdxArray->Num() == 3)
			{
				Tri.VertexIndices[0] = static_cast<int32>((*IdxArray)[0]->AsNumber());
				Tri.VertexIndices[1] = static_cast<int32>((*IdxArray)[1]->AsNumber());
				Tri.VertexIndices[2] = static_cast<int32>((*IdxArray)[2]->AsNumber());
			}

			const TArray<TSharedPtr<FJsonValue>>* NormArray;
			if (TriObj->TryGetArrayField(TEXT("normals"), NormArray) && NormArray && NormArray->Num() == 3)
			{
				for (int32 c = 0; c < 3; ++c)
				{
					const TArray<TSharedPtr<FJsonValue>>* NCo;
					if ((*NormArray)[c]->TryGetArray(NCo) && NCo && NCo->Num() == 3)
					{
						Tri.Normals[c] = FVector3f(
							static_cast<float>((*NCo)[0]->AsNumber()),
							static_cast<float>((*NCo)[1]->AsNumber()),
							static_cast<float>((*NCo)[2]->AsNumber()));
					}
				}
			}

			const TArray<TSharedPtr<FJsonValue>>* UVArray;
			if (TriObj->TryGetArrayField(TEXT("uvs"), UVArray) && UVArray && UVArray->Num() == 3)
			{
				for (int32 c = 0; c < 3; ++c)
				{
					const TArray<TSharedPtr<FJsonValue>>* UVCo;
					if ((*UVArray)[c]->TryGetArray(UVCo) && UVCo && UVCo->Num() == 2)
					{
						Tri.UVs[c] = FVector2f(
							static_cast<float>((*UVCo)[0]->AsNumber()),
							static_cast<float>((*UVCo)[1]->AsNumber()));
					}
				}
			}

			OutMesh.Triangles.Add(Tri);
		}
	}

	// Material slots
	const TArray<TSharedPtr<FJsonValue>>* SlotArray;
	if (JsonObject->TryGetArrayField(TEXT("material_slots"), SlotArray) && SlotArray)
	{
		for (const TSharedPtr<FJsonValue>& SVal : *SlotArray)
		{
			const TSharedPtr<FJsonObject>& SObj = SVal->AsObject();
			if (SObj.IsValid())
			{
				FBridgeMaterialSlot Slot;
				SObj->TryGetNumberField(TEXT("slot_index"), Slot.SlotIndex);
				SObj->TryGetStringField(TEXT("slot_name"), Slot.SlotName);
				SObj->TryGetStringField(TEXT("material_id"), Slot.MaterialId);
				OutMesh.MaterialSlots.Add(Slot);
			}
		}
	}

	return true;
}

bool FBridgePackageReader::LoadMeshes(
	const FString& PackageDirectory,
	const TArray<FBridgeObject>& Objects,
	TMap<FString, FBridgeMeshData>& OutMeshes,
	FBridgeValidationReport& OutReport)
{
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	// Find all unique mesh references in objects
	TSet<FString> MeshFilesToLoad;
	for (const FBridgeObject& Obj : Objects)
	{
		if (Obj.Type == TEXT("STATIC_MESH") && Obj.MeshReference.IsValid())
		{
			MeshFilesToLoad.Add(Obj.MeshReference.File);
		}
	}

	for (const FString& RelFile : MeshFilesToLoad)
	{
		FString FullPath = FPaths::Combine(PackageDirectory, RelFile);
		if (!PlatformFile.FileExists(*FullPath))
		{
			OutReport.AddError(
				TEXT("MESH_FILE_NOT_FOUND"),
				FString::Printf(TEXT("Referenced mesh file not found: '%s'"), *FullPath));
			continue;
		}

		TSharedPtr<FJsonObject> MeshJson;
		if (ReadJsonFile(FullPath, MeshJson, OutReport))
		{
			FBridgeMeshData MeshData;
			if (ParseMesh(MeshJson, MeshData, OutReport))
			{
				OutMeshes.Add(MeshData.MeshId, MeshData);
			}
		}
	}

	return true;
}

FTransform FBridgePackageReader::GetUnrealLocalTransform(const FBridgeObject& Object)
{
	return FBridgeTransformConverter::ToUnrealLocalTransform(Object.Transform);
}

FTransform FBridgePackageReader::GetUnrealWorldTransform(
	const FBridgePackageData& PackageData,
	const FBridgeObject& Object)
{
	// Build hierarchy chain from root to object
	TArray<const FBridgeObject*> Chain;
	const FBridgeObject* Curr = &Object;

	TSet<FString> Visited;
	while (Curr)
	{
		if (Visited.Contains(Curr->Id))
		{
			// Safeguard against cycle
			break;
		}
		Visited.Add(Curr->Id);
		Chain.Insert(Curr, 0);

		if (Curr->HasParent())
		{
			Curr = PackageData.FindObjectById(Curr->ParentId);
		}
		else
		{
			Curr = nullptr;
		}
	}

	// Accumulate transforms from root down to this object
	FTransform AccumulatedTransform = FTransform::Identity;
	for (const FBridgeObject* Node : Chain)
	{
		FTransform LocalTransform = FBridgeTransformConverter::ToUnrealLocalTransform(Node->Transform);
		AccumulatedTransform = FBridgeTransformConverter::ComputeWorldTransform(LocalTransform, &AccumulatedTransform);
	}

	return AccumulatedTransform;
}

bool FBridgePackageReader::ParseMaterial(
	const TSharedPtr<FJsonObject>& JsonObject,
	FBridgeMaterialData& OutMaterial,
	FBridgeValidationReport& OutReport)
{
	if (!JsonObject.IsValid())
	{
		return false;
	}

	JsonObject->TryGetStringField(TEXT("format"), OutMaterial.Format);
	JsonObject->TryGetStringField(TEXT("version"), OutMaterial.Version);
	JsonObject->TryGetStringField(TEXT("material_id"), OutMaterial.MaterialId);
	JsonObject->TryGetStringField(TEXT("name"), OutMaterial.Name);
	JsonObject->TryGetStringField(TEXT("model"), OutMaterial.Model);

	// Base color
	const TArray<TSharedPtr<FJsonValue>>* BaseColorArray = nullptr;
	if (JsonObject->TryGetArrayField(TEXT("base_color"), BaseColorArray) && BaseColorArray && BaseColorArray->Num() >= 3)
	{
		float R = static_cast<float>((*BaseColorArray)[0]->AsNumber());
		float G = static_cast<float>((*BaseColorArray)[1]->AsNumber());
		float B = static_cast<float>((*BaseColorArray)[2]->AsNumber());
		float A = BaseColorArray->Num() >= 4 ? static_cast<float>((*BaseColorArray)[3]->AsNumber()) : 1.0f;
		OutMaterial.BaseColor = FLinearColor(R, G, B, A);
	}

	double Val = 0.0;
	if (JsonObject->TryGetNumberField(TEXT("metallic"), Val))
	{
		OutMaterial.Metallic = static_cast<float>(Val);
	}
	if (JsonObject->TryGetNumberField(TEXT("roughness"), Val))
	{
		OutMaterial.Roughness = static_cast<float>(Val);
	}
	if (JsonObject->TryGetNumberField(TEXT("specular"), Val))
	{
		OutMaterial.Specular = static_cast<float>(Val);
	}
	if (JsonObject->TryGetNumberField(TEXT("ior"), Val))
	{
		OutMaterial.IOR = static_cast<float>(Val);
	}
	if (JsonObject->TryGetNumberField(TEXT("opacity"), Val))
	{
		OutMaterial.Opacity = static_cast<float>(Val);
	}

	JsonObject->TryGetStringField(TEXT("blend_mode"), OutMaterial.BlendMode);
	JsonObject->TryGetBoolField(TEXT("two_sided"), OutMaterial.bTwoSided);

	return true;
}

bool FBridgePackageReader::LoadMaterials(
	const FString& PackageDirectory,
	TMap<FString, FBridgeMaterialData>& OutMaterials,
	FBridgeValidationReport& OutReport)
{
	FString MaterialsDir = FPaths::Combine(PackageDirectory, TEXT("materials"));
	IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

	if (!PlatformFile.DirectoryExists(*MaterialsDir))
	{
		return true;
	}

	TArray<FString> MaterialFiles;
	IFileManager::Get().FindFiles(MaterialFiles, *FPaths::Combine(MaterialsDir, TEXT("*.json")), true, false);

	for (const FString& Filename : MaterialFiles)
	{
		FString FullPath = FPaths::Combine(MaterialsDir, Filename);
		TSharedPtr<FJsonObject> MatJson;
		if (ReadJsonFile(FullPath, MatJson, OutReport))
		{
			FBridgeMaterialData MatData;
			if (ParseMaterial(MatJson, MatData, OutReport))
			{
				OutMaterials.Add(MatData.MaterialId, MatData);
			}
		}
	}

	return true;
}
