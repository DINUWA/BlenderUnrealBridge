#pragma once

#include "CoreMinimal.h"
#include "Core/BridgeDataModel.h"
#include "Core/BridgeDiagnostics.h"
#include "Core/BridgeTransformConverter.h"

/**
 * Evaluated bone pose containing native Unreal local and component-space transforms.
 */
struct BLENDERUNREALBRIDGE_API FBridgeEvaluatedBoneTransform
{
	FString BoneId;
	FString BoneName;
	FTransform LocalTransform = FTransform::Identity;
	FTransform ComponentTransform = FTransform::Identity;
};

/**
 * Animation builder and evaluator for canonical skeletons and animation clips.
 * Provides native Unreal bone hierarchy reconstruction, rest pose evaluation, and keyframe track sampling.
 */
class BLENDERUNREALBRIDGE_API FBridgeAnimationBuilder
{
public:
	/**
	 * Computes the component-space rest transforms for all bones in a skeleton.
	 *
	 * @param Skeleton Canonical skeleton data
	 * @param OutBoneTransforms Map of BoneId -> evaluated bone transform
	 * @param OutReport Diagnostic report
	 * @return true if all bones were successfully evaluated
	 */
	static bool BuildSkeletonRestPose(
		const FBridgeSkeletonData& Skeleton,
		TMap<FString, FBridgeEvaluatedBoneTransform>& OutBoneTransforms,
		FBridgeValidationReport& OutReport);

	/**
	 * Samples a bone animation track at a specific time in seconds, interpolating keyframes.
	 *
	 * @param Track Bone animation track containing keyframes
	 * @param TimeSeconds Time in seconds to evaluate
	 * @param OutTransform Resulting native Unreal local bone transform
	 * @return true if track was sampled
	 */
	static bool SampleBoneTrack(
		const FBridgeBoneAnimationTrack& Track,
		float TimeSeconds,
		FTransform& OutTransform);

	/**
	 * Evaluates an entire animation clip at a specific time in seconds across all skeleton bones.
	 *
	 * @param Skeleton Canonical skeleton data
	 * @param Clip Canonical animation clip
	 * @param TimeSeconds Evaluation time in seconds
	 * @param OutPose Map of BoneId -> evaluated local & component transforms
	 * @param OutReport Diagnostic report
	 * @return true if pose was successfully evaluated
	 */
	static bool EvaluatePoseAtTime(
		const FBridgeSkeletonData& Skeleton,
		const FBridgeAnimationClip& Clip,
		float TimeSeconds,
		TMap<FString, FBridgeEvaluatedBoneTransform>& OutPose,
		FBridgeValidationReport& OutReport);
};
