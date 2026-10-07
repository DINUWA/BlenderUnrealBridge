#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"

/**
 * Validates parsed Bridge package data structures against DATA_PROTOCOL.md specifications.
 */
class BLENDERUNREALBRIDGE_API FBridgePackageValidator
{
public:
	/**
	 * Supported protocol format name and versions.
	 */
	static const FString SupportedFormat;
	static const int32 SupportedMajorVersion;
	static const int32 SupportedMinorVersion;

	/**
	 * Validates the parsed package data model in its entirety, including meshes.
	 */
	static bool ValidatePackage(
		const FBridgePackageData& PackageData,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates manifest metadata.
	 */
	static bool ValidateManifest(
		const FBridgeManifest& Manifest,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates scene metadata.
	 */
	static bool ValidateScene(
		const FBridgeScene& Scene,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates object array, Bridge ID uniqueness, hierarchy, and transforms.
	 */
	static bool ValidateObjects(
		const TArray<FBridgeObject>& Objects,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates a single canonical mesh payload.
	 */
	static bool ValidateMesh(
		const FBridgeMeshData& Mesh,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates all loaded meshes and verifies referential integrity from objects.
	 */
	static bool ValidateMeshes(
		const TMap<FString, FBridgeMeshData>& Meshes,
		const TArray<FBridgeObject>& Objects,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates a single canonical PBR material payload.
	 */
	static bool ValidateMaterial(
		const FBridgeMaterialData& Material,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates all loaded materials and verifies referential integrity from objects and meshes.
	 */
	static bool ValidateMaterials(
		const TMap<FString, FBridgeMaterialData>& Materials,
		const TMap<FString, FBridgeMeshData>& Meshes,
		const TArray<FBridgeObject>& Objects,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates a single canonical texture entry.
	 */
	static bool ValidateTexture(
		const FBridgeTextureData& Texture,
		const FString& PackageDirectory,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates all loaded textures and verifies referential integrity from materials.
	 */
	static bool ValidateTextures(
		const TMap<FString, FBridgeTextureData>& Textures,
		const TMap<FString, FBridgeMaterialData>& Materials,
		const FString& PackageDirectory,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates a single canonical skeleton entry.
	 */
	static bool ValidateSkeleton(
		const FBridgeSkeletonData& Skeleton,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates a single canonical animation clip entry.
	 */
	static bool ValidateAnimationClip(
		const FBridgeAnimationClip& Clip,
		const TMap<FString, FBridgeSkeletonData>& Skeletons,
		FBridgeValidationReport& OutReport);

	/**
	 * Validates all loaded animations and skeletons, and verifies referential integrity with meshes and objects.
	 */
	static bool ValidateAnimations(
		const TMap<FString, FBridgeSkeletonData>& Skeletons,
		const TMap<FString, FBridgeAnimationClip>& Animations,
		const TMap<FString, FBridgeMeshData>& Meshes,
		const TArray<FBridgeObject>& Objects,
		FBridgeValidationReport& OutReport);

	static bool IsValidBridgeId(const FString& Id);
	static bool IsValidMeshId(const FString& Id);
	static bool IsValidMaterialId(const FString& Id);
	static bool IsValidTextureId(const FString& Id);
	static bool IsValidSkeletonId(const FString& Id);
	static bool IsValidBoneId(const FString& Id);
	static bool IsValidAnimationId(const FString& Id);
};
