#include "Material/BridgeMaterialBuilder.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"

UMaterialInterface* FBridgeMaterialBuilder::CreateMaterial(
	UObject* Outer,
	const FBridgeMaterialData& MaterialData,
	FBridgeValidationReport& OutReport,
	UMaterialInterface* MasterMaterial)
{
	if (!Outer)
	{
		Outer = GetTransientPackage();
	}

	UMaterialInterface* ParentMat = MasterMaterial;
	if (!ParentMat)
	{
		ParentMat = UMaterial::GetDefaultMaterial(MD_Surface);
	}

	if (!ParentMat)
	{
		OutReport.AddError(
			TEXT("MATERIAL_PARENT_NOT_FOUND"),
			TEXT("Failed to obtain a default surface material for dynamic material instance creation"),
			MaterialData.MaterialId);
		return nullptr;
	}

	FName MatName = !MaterialData.Name.IsEmpty() ? FName(*MaterialData.Name) : FName(*MaterialData.MaterialId);
	UMaterialInstanceDynamic* DynamicMat = UMaterialInstanceDynamic::Create(ParentMat, Outer, MatName);
	if (!DynamicMat)
	{
		OutReport.AddError(
			TEXT("MATERIAL_CREATION_FAILED"),
			FString::Printf(TEXT("Failed to create dynamic material instance for '%s'"), *MaterialData.MaterialId),
			MaterialData.MaterialId);
		return nullptr;
	}

	// Apply canonical PBR parameters
	DynamicMat->SetVectorParameterValue(FName(TEXT("BaseColor")), MaterialData.BaseColor);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Metallic")), MaterialData.Metallic);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Roughness")), MaterialData.Roughness);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Specular")), MaterialData.Specular);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Opacity")), MaterialData.Opacity);
	DynamicMat->SetScalarParameterValue(FName(TEXT("IOR")), MaterialData.IOR);

	// Diagnostic information for properties
	if (MaterialData.bTwoSided)
	{
		OutReport.AddInfo(
			TEXT("MATERIAL_TWO_SIDED"),
			FString::Printf(TEXT("Material '%s' specifies two-sided rendering"), *MaterialData.MaterialId),
			MaterialData.MaterialId);
	}

	if (MaterialData.BlendMode != TEXT("OPAQUE"))
	{
		OutReport.AddInfo(
			TEXT("MATERIAL_BLEND_MODE"),
			FString::Printf(TEXT("Material '%s' specifies blend mode '%s'"), *MaterialData.MaterialId, *MaterialData.BlendMode),
			MaterialData.MaterialId);
	}

	OutReport.AddInfo(
		TEXT("MATERIAL_BUILD_SUCCESS"),
		FString::Printf(TEXT("Successfully created dynamic material instance for '%s' (%s)"),
			*MaterialData.MaterialId, *MaterialData.Name),
		MaterialData.MaterialId);

	return DynamicMat;
}

TMap<FString, UMaterialInterface*> FBridgeMaterialBuilder::CreateMaterialsForPackage(
	UObject* Outer,
	const FBridgePackageData& PackageData,
	FBridgeValidationReport& OutReport,
	UMaterialInterface* MasterMaterial)
{
	TMap<FString, UMaterialInterface*> MaterialMap;
	MaterialMap.Reserve(PackageData.Materials.Num());

	for (const auto& Kvp : PackageData.Materials)
	{
		const FString& MatId = Kvp.Key;
		const FBridgeMaterialData& MatData = Kvp.Value;

		UMaterialInterface* Mat = CreateMaterial(Outer, MatData, OutReport, MasterMaterial);
		if (Mat)
		{
			MaterialMap.Add(MatId, Mat);
		}
	}

	return MaterialMap;
}
