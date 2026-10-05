#pragma once

#include "CoreMinimal.h"
#include "BridgeDataModel.h"

/**
 * Authoritative Unreal-side transform converter.
 * Converts canonical Bridge transforms into native Unreal Engine representations:
 *   - FVector (Location in Unreal units / cm)
 *   - FQuat (Unit rotation quaternion)
 *   - FRotator (Pitch/Yaw/Roll in degrees)
 *   - FTransform (Native Unreal local or world transform)
 *
 * Mathematical Foundations:
 * ------------------------
 * Canonical Bridge Space (from DATA_PROTOCOL.md §3 and Milestone 2):
 *   Up Axis    : +Z
 *   Forward    : +X
 *   Right      : +Y
 *   Handedness : Left-Handed
 *   Unit       : Centimeter
 *
 * Unreal Engine Native Space:
 *   Up Axis    : +Z
 *   Forward    : +X
 *   Right      : +Y
 *   Handedness : Left-Handed
 *   Unit       : Centimeter (1 uu = 1 cm)
 *
 * Because Milestone 2 performed the authoritative conversion from Blender (RH meters)
 * into Bridge Canonical (LH centimeters), the Canonical Bridge transform maps directly
 * and precisely onto Unreal's coordinate basis without secondary axis swaps.
 */
class BLENDERUNREALBRIDGE_API FBridgeTransformConverter
{
public:
	/**
	 * Converts canonical Bridge location array into Unreal FVector (in centimeters).
	 */
	static FVector ToUnrealLocation(const FVector& CanonicalLocation);

	/**
	 * Converts canonical Bridge quaternion [x, y, z, w] into normalized Unreal FQuat.
	 */
	static FQuat ToUnrealRotation(const FQuat& CanonicalQuaternion);

	/**
	 * Converts canonical Bridge quaternion into native Unreal FRotator.
	 */
	static FRotator ToUnrealRotator(const FQuat& CanonicalQuaternion);

	/**
	 * Converts canonical Bridge scale vector into Unreal FVector scale.
	 * Faithfully preserves negative scale signs for reflection handling.
	 */
	static FVector ToUnrealScale(const FVector& CanonicalScale);

	/**
	 * Converts a full FBridgeCanonicalTransform into a native Unreal local FTransform.
	 */
	static FTransform ToUnrealLocalTransform(const FBridgeCanonicalTransform& CanonicalTransform);

	/**
	 * Computes the world transform of an object given its local transform and parent's world transform.
	 * In Unreal Engine: WorldTransform = LocalTransform * ParentWorldTransform.
	 */
	static FTransform ComputeWorldTransform(
		const FTransform& LocalTransform,
		const FTransform* ParentWorldTransform = nullptr);
};
