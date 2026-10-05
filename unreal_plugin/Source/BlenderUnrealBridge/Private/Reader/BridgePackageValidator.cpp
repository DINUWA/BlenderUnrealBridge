#include "Reader/BridgePackageValidator.h"

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

bool FBridgePackageValidator::ValidatePackage(
	const FBridgePackageData& PackageData,
	FBridgeValidationReport& OutReport)
{
	bool bValid = true;

	bValid &= ValidateManifest(PackageData.Manifest, OutReport);
	bValid &= ValidateScene(PackageData.Scene, OutReport);
	bValid &= ValidateObjects(PackageData.Objects, OutReport);

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
