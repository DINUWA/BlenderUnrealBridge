#include "Material/BridgeMaterialBuilder.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/Paths.h"

UMaterialInterface* FBridgeMaterialBuilder::CreateMaterial(
	UObject* Outer,
	const FBridgeMaterialData& MaterialData,
	FBridgeValidationReport& OutReport,
	UMaterialInterface* MasterMaterial,
	const FBridgePackageData* PackageData,
	TMap<FString, UTexture2D*>* TextureCache)
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

	// 1. Apply canonical PBR scalar/color parameters (Milestone 6 baseline)
	DynamicMat->SetVectorParameterValue(FName(TEXT("BaseColor")), MaterialData.BaseColor);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Metallic")), MaterialData.Metallic);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Roughness")), MaterialData.Roughness);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Specular")), MaterialData.Specular);
	DynamicMat->SetScalarParameterValue(FName(TEXT("Opacity")), MaterialData.Opacity);
	DynamicMat->SetScalarParameterValue(FName(TEXT("IOR")), MaterialData.IOR);

	// 2. Apply texture parameters (Milestone 7 extension)
	if (PackageData && MaterialData.Textures.Num() > 0)
	{
		for (const auto& TexKvp : MaterialData.Textures)
		{
			const FString& Channel = TexKvp.Key;
			const FString& TexId = TexKvp.Value;

			if (TexId.IsEmpty())
			{
				continue;
			}

			UTexture2D* Texture = nullptr;
			if (TextureCache && TextureCache->Contains(TexId))
			{
				Texture = (*TextureCache)[TexId];
			}
			else
			{
				const FBridgeTextureData* TexData = PackageData->FindTextureById(TexId);
				if (TexData && !TexData->RelativePath.IsEmpty())
				{
					FString FullPath = FPaths::Combine(PackageData->PackageDirectory, TexData->RelativePath);
					Texture = FImageUtils::ImportFileAsTexture2D(FullPath);
					if (Texture)
					{
						if (Channel == TEXT("normal"))
						{
							Texture->CompressionSettings = TC_Normalmap;
							Texture->SRGB = false;
							Texture->UpdateResource();
						}
						else if (Channel == TEXT("roughness") || Channel == TEXT("metallic"))
						{
							Texture->SRGB = false;
							Texture->UpdateResource();
						}
						else if (Channel == TEXT("base_color"))
						{
							Texture->SRGB = true;
							Texture->UpdateResource();
						}

						if (TextureCache)
						{
							TextureCache->Add(TexId, Texture);
						}
					}
					else
					{
						OutReport.AddWarning(
							TEXT("TEXTURE_IMPORT_FAILED"),
							FString::Printf(TEXT("Failed to import texture file '%s' for channel '%s'"), *FullPath, *Channel),
							TexId);
					}
				}
			}

			if (Texture)
			{
				if (Channel == TEXT("base_color"))
				{
					DynamicMat->SetTextureParameterValue(FName(TEXT("BaseColorTexture")), Texture);
					DynamicMat->SetTextureParameterValue(FName(TEXT("BaseColor")), Texture);
				}
				else if (Channel == TEXT("roughness"))
				{
					DynamicMat->SetTextureParameterValue(FName(TEXT("RoughnessTexture")), Texture);
					DynamicMat->SetTextureParameterValue(FName(TEXT("Roughness")), Texture);
				}
				else if (Channel == TEXT("metallic"))
				{
					DynamicMat->SetTextureParameterValue(FName(TEXT("MetallicTexture")), Texture);
					DynamicMat->SetTextureParameterValue(FName(TEXT("Metallic")), Texture);
				}
				else if (Channel == TEXT("normal"))
				{
					DynamicMat->SetTextureParameterValue(FName(TEXT("NormalTexture")), Texture);
					DynamicMat->SetTextureParameterValue(FName(TEXT("NormalMap")), Texture);
					DynamicMat->SetTextureParameterValue(FName(TEXT("Normal")), Texture);
				}
			}
		}
	}

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

	TMap<FString, UTexture2D*> TextureCache;

	for (const auto& Kvp : PackageData.Materials)
	{
		const FString& MatId = Kvp.Key;
		const FBridgeMaterialData& MatData = Kvp.Value;

		UMaterialInterface* Mat = CreateMaterial(Outer, MatData, OutReport, MasterMaterial, &PackageData, &TextureCache);
		if (Mat)
		{
			MaterialMap.Add(MatId, Mat);
		}
	}

	return MaterialMap;
}
