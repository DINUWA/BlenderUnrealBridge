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
 * 2. Parse manifest.json, scene.json, objects.json using Unreal JSON APIs
 * 3. Validate package schema, referential integrity, and transforms
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
};
