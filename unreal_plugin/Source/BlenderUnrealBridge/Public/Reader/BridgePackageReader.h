#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"
#include "Core/BridgeTransformConverter.h"
#include "Reader/BridgePackageValidator.h"

/**
 * High-level package reader for .bubridge data packages.
 *
 * Responsibilities:
 * 1. Locate and inspect .bubridge package structure
 * 2. Parse manifest.json, scene.json, objects.json, and meshes/*.json using Unreal JSON APIs
 * 3. Validate package schema, referential integrity, meshes, and transforms
 * 4. Construct complete FBridgePackageData model
 * 5. Provide authoritative Unreal-native transforms for all objects
 */
class BLENDERUNREALBRIDGE_API FBridgePackageReader
{
public:
	/**
	 * Reads, parses, and validates a .bubridge package from disk.
	 *
	 * @param PackageDirectory Path to the .bubridge directory
	 * @param OutPackageData Reconstructed in-memory package data
	 * @param OutReport Diagnostic report collecting any warnings or errors
	 * @return true if the package was successfully read and passed validation without errors
	 */
	static bool LoadPackage(
		const FString& PackageDirectory,
		FBridgePackageData& OutPackageData,
		FBridgeValidationReport& OutReport);

	/**
	 * Resolves the native Unreal local transform for an object.
	 */
	static FTransform GetUnrealLocalTransform(const FBridgeObject& Object);

	/**
	 * Computes the native Unreal world transform for an object by traversing up its parent hierarchy.
	 */
	static FTransform GetUnrealWorldTransform(
		const FBridgePackageData& PackageData,
		const FBridgeObject& Object);

	/**
	 * Returns all root objects in the package (objects where ParentId is empty).
	 */
	static void GetRootObjects(
		const FBridgePackageData& PackageData,
		TArray<const FBridgeObject*>& OutRoots);

	/**
	 * Returns all immediate children of a given parent object.
	 */
	static void GetChildrenOf(
		const FBridgePackageData& PackageData,
		const FString& ParentId,
		TArray<const FBridgeObject*>& OutChildren);

	/**
	 * Returns all objects in topological order (parents before children).
	 */
	static bool GetTopologicalObjectOrder(
		const FBridgePackageData& PackageData,
		TArray<const FBridgeObject*>& OutOrderedObjects);

	/**
	 * Builds the hierarchical folder path for a collection (e.g. "Environment/Props").
	 */
	static FString BuildCollectionFolderPath(
		const FBridgePackageData& PackageData,
		const FString& CollectionId);

private:
	static bool VerifyPackageStructure(
		const FString& PackageDirectory,
		FBridgeValidationReport& OutReport);

	static bool ReadJsonFile(
		const FString& FilePath,
		TSharedPtr<class FJsonObject>& OutJsonObject,
		FBridgeValidationReport& OutReport);

	static bool ParseManifest(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeManifest& OutManifest,
		FBridgeValidationReport& OutReport);

	static bool ParseScene(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeScene& OutScene,
		FBridgeValidationReport& OutReport);

	static bool ParseObjects(
		const TSharedPtr<class FJsonObject>& JsonObject,
		TArray<FBridgeObject>& OutObjects,
		FBridgeValidationReport& OutReport);

	static bool ParseTransform(
		const TSharedPtr<class FJsonObject>& JsonObject,
		const FString& ObjectId,
		const FString& ObjectName,
		FBridgeCanonicalTransform& OutTransform,
		FBridgeValidationReport& OutReport);

	static bool ParseMesh(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeMeshData& OutMesh,
		FBridgeValidationReport& OutReport);

	static bool LoadMeshes(
		const FString& PackageDirectory,
		const TArray<FBridgeObject>& Objects,
		TMap<FString, FBridgeMeshData>& OutMeshes,
		FBridgeValidationReport& OutReport);

	static bool ParseMaterial(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeMaterialData& OutMaterial,
		FBridgeValidationReport& OutReport);

	static bool LoadMaterials(
		const FString& PackageDirectory,
		TMap<FString, FBridgeMaterialData>& OutMaterials,
		FBridgeValidationReport& OutReport);

	static bool ParseTexture(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeTextureData& OutTexture,
		FBridgeValidationReport& OutReport);

	static bool LoadTextures(
		const FString& PackageDirectory,
		TMap<FString, FBridgeTextureData>& OutTextures,
		FBridgeValidationReport& OutReport);

	static bool ParseSkeleton(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeSkeletonData& OutSkeleton,
		FBridgeValidationReport& OutReport);

	static bool ParseAnimationClip(
		const TSharedPtr<class FJsonObject>& JsonObject,
		FBridgeAnimationClip& OutClip,
		FBridgeValidationReport& OutReport);

	static bool LoadAnimations(
		const FString& PackageDirectory,
		TMap<FString, FBridgeSkeletonData>& OutSkeletons,
		TMap<FString, FBridgeAnimationClip>& OutAnimations,
		FBridgeValidationReport& OutReport);
};
