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
	 * Validates the parsed package data model in its entirety.
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

private:
	static bool IsValidBridgeId(const FString& Id);
};
