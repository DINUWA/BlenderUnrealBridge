#include "Core/BridgeTransformConverter.h"

FVector FBridgeTransformConverter::ToUnrealLocation(const FVector& CanonicalLocation)
{
	// Canonical Bridge space: +X Forward, +Y Right, +Z Up in centimeters.
	// Unreal Engine space:    +X Forward, +Y Right, +Z Up in centimeters.
	return CanonicalLocation;
}

FQuat FBridgeTransformConverter::ToUnrealRotation(const FQuat& CanonicalQuaternion)
{
	// The canonical quaternion is stored as [x, y, z, w] with left-handed basis.
	// Ensure unit normalization for numerical stability in Unreal.
	FQuat Result = CanonicalQuaternion;
	Result.Normalize();
	return Result;
}

FRotator FBridgeTransformConverter::ToUnrealRotator(const FQuat& CanonicalQuaternion)
{
	FQuat NormalizedQuat = ToUnrealRotation(CanonicalQuaternion);
	return NormalizedQuat.Rotator();
}

FVector FBridgeTransformConverter::ToUnrealScale(const FVector& CanonicalScale)
{
	// Scales map 1:1 along canonical axes, preserving negative reflection signs.
	return CanonicalScale;
}

FTransform FBridgeTransformConverter::ToUnrealLocalTransform(const FBridgeCanonicalTransform& CanonicalTransform)
{
	FVector Location = ToUnrealLocation(CanonicalTransform.Location);
	FQuat Rotation = ToUnrealRotation(CanonicalTransform.RotationQuaternion);
	FVector Scale = ToUnrealScale(CanonicalTransform.Scale);

	return FTransform(Rotation, Location, Scale);
}

FTransform FBridgeTransformConverter::ComputeWorldTransform(
	const FTransform& LocalTransform,
	const FTransform* ParentWorldTransform)
{
	if (!ParentWorldTransform)
	{
		return LocalTransform;
	}

	// In Unreal Engine, ChildWorld = ChildLocal * ParentWorld
	return LocalTransform * (*ParentWorldTransform);
}
