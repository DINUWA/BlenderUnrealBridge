#include "Animation/BridgeAnimationBuilder.h"

bool FBridgeAnimationBuilder::BuildSkeletonRestPose(
	const FBridgeSkeletonData& Skeleton,
	TMap<FString, FBridgeEvaluatedBoneTransform>& OutBoneTransforms,
	FBridgeValidationReport& OutReport)
{
	OutBoneTransforms.Empty(Skeleton.Bones.Num());

	// Map of BoneId -> index in Skeleton.Bones
	TMap<FString, int32> BoneMap;
	for (int32 Idx = 0; Idx < Skeleton.Bones.Num(); ++Idx)
	{
		BoneMap.Add(Skeleton.Bones[Idx].Id, Idx);
	}

	for (const FBridgeBoneData& Bone : Skeleton.Bones)
	{
		FBridgeEvaluatedBoneTransform Eval;
		Eval.BoneId = Bone.Id;
		Eval.BoneName = Bone.Name;
		Eval.LocalTransform = FBridgeTransformConverter::ToUnrealLocalTransform(Bone.RestTransform);

		if (Bone.ParentId.IsEmpty())
		{
			// Root bone
			Eval.ComponentTransform = Eval.LocalTransform;
		}
		else
		{
			const FBridgeEvaluatedBoneTransform* ParentEval = OutBoneTransforms.Find(Bone.ParentId);
			if (ParentEval)
			{
				Eval.ComponentTransform = FBridgeTransformConverter::ComputeWorldTransform(
					Eval.LocalTransform, &ParentEval->ComponentTransform);
			}
			else
			{
				// In case bones are not strictly parent-first, fallback
				Eval.ComponentTransform = Eval.LocalTransform;
			}
		}

		OutBoneTransforms.Add(Bone.Id, Eval);
	}

	return true;
}

bool FBridgeAnimationBuilder::SampleBoneTrack(
	const FBridgeBoneAnimationTrack& Track,
	float TimeSeconds,
	FTransform& OutTransform)
{
	FVector OutLocation = FVector::ZeroVector;
	FQuat OutRotation = FQuat::Identity;
	FVector OutScale = FVector::OneVector;

	// 1. Location interpolation
	if (Track.LocationKeys.Num() == 1)
	{
		OutLocation = Track.LocationKeys[0].Value;
	}
	else if (Track.LocationKeys.Num() > 1)
	{
		if (TimeSeconds <= Track.LocationKeys[0].Time)
		{
			OutLocation = Track.LocationKeys[0].Value;
		}
		else if (TimeSeconds >= Track.LocationKeys.Last().Time)
		{
			OutLocation = Track.LocationKeys.Last().Value;
		}
		else
		{
			for (int32 i = 0; i < Track.LocationKeys.Num() - 1; ++i)
			{
				const auto& K0 = Track.LocationKeys[i];
				const auto& K1 = Track.LocationKeys[i + 1];
				if (TimeSeconds >= K0.Time && TimeSeconds <= K1.Time)
				{
					float Range = K1.Time - K0.Time;
					float Alpha = (Range > KINDA_SMALL_NUMBER) ? (TimeSeconds - K0.Time) / Range : 0.0f;
					OutLocation = FMath::Lerp(K0.Value, K1.Value, FMath::Clamp(Alpha, 0.0f, 1.0f));
					break;
				}
			}
		}
	}

	// 2. Rotation interpolation (Spherical linear interpolation)
	if (Track.RotationKeys.Num() == 1)
	{
		OutRotation = Track.RotationKeys[0].Value;
	}
	else if (Track.RotationKeys.Num() > 1)
	{
		if (TimeSeconds <= Track.RotationKeys[0].Time)
		{
			OutRotation = Track.RotationKeys[0].Value;
		}
		else if (TimeSeconds >= Track.RotationKeys.Last().Time)
		{
			OutRotation = Track.RotationKeys.Last().Value;
		}
		else
		{
			for (int32 i = 0; i < Track.RotationKeys.Num() - 1; ++i)
			{
				const auto& K0 = Track.RotationKeys[i];
				const auto& K1 = Track.RotationKeys[i + 1];
				if (TimeSeconds >= K0.Time && TimeSeconds <= K1.Time)
				{
					float Range = K1.Time - K0.Time;
					float Alpha = (Range > KINDA_SMALL_NUMBER) ? (TimeSeconds - K0.Time) / Range : 0.0f;
					OutRotation = FQuat::Slerp(K0.Value, K1.Value, FMath::Clamp(Alpha, 0.0f, 1.0f));
					break;
				}
			}
		}
	}

	// 3. Scale interpolation
	if (Track.ScaleKeys.Num() == 1)
	{
		OutScale = Track.ScaleKeys[0].Value;
	}
	else if (Track.ScaleKeys.Num() > 1)
	{
		if (TimeSeconds <= Track.ScaleKeys[0].Time)
		{
			OutScale = Track.ScaleKeys[0].Value;
		}
		else if (TimeSeconds >= Track.ScaleKeys.Last().Time)
		{
			OutScale = Track.ScaleKeys.Last().Value;
		}
		else
		{
			for (int32 i = 0; i < Track.ScaleKeys.Num() - 1; ++i)
			{
				const auto& K0 = Track.ScaleKeys[i];
				const auto& K1 = Track.ScaleKeys[i + 1];
				if (TimeSeconds >= K0.Time && TimeSeconds <= K1.Time)
				{
					float Range = K1.Time - K0.Time;
					float Alpha = (Range > KINDA_SMALL_NUMBER) ? (TimeSeconds - K0.Time) / Range : 0.0f;
					OutScale = FMath::Lerp(K0.Value, K1.Value, FMath::Clamp(Alpha, 0.0f, 1.0f));
					break;
				}
			}
		}
	}

	OutTransform = FTransform(OutRotation, OutLocation, OutScale);
	return true;
}

bool FBridgeAnimationBuilder::EvaluatePoseAtTime(
	const FBridgeSkeletonData& Skeleton,
	const FBridgeAnimationClip& Clip,
	float TimeSeconds,
	TMap<FString, FBridgeEvaluatedBoneTransform>& OutPose,
	FBridgeValidationReport& OutReport)
{
	OutPose.Empty(Skeleton.Bones.Num());

	// Build track lookup
	TMap<FString, const FBridgeBoneAnimationTrack*> TrackMap;
	for (const FBridgeBoneAnimationTrack& Track : Clip.Tracks)
	{
		TrackMap.Add(Track.BoneId, &Track);
	}

	for (const FBridgeBoneData& Bone : Skeleton.Bones)
	{
		FBridgeEvaluatedBoneTransform Eval;
		Eval.BoneId = Bone.Id;
		Eval.BoneName = Bone.Name;

		const FBridgeBoneAnimationTrack* const* FoundTrack = TrackMap.Find(Bone.Id);
		if (FoundTrack && *FoundTrack)
		{
			SampleBoneTrack(**FoundTrack, TimeSeconds, Eval.LocalTransform);
		}
		else
		{
			// Default to rest transform if no track for this bone
			Eval.LocalTransform = FBridgeTransformConverter::ToUnrealLocalTransform(Bone.RestTransform);
		}

		if (Bone.ParentId.IsEmpty())
		{
			Eval.ComponentTransform = Eval.LocalTransform;
		}
		else
		{
			const FBridgeEvaluatedBoneTransform* ParentEval = OutPose.Find(Bone.ParentId);
			if (ParentEval)
			{
				Eval.ComponentTransform = FBridgeTransformConverter::ComputeWorldTransform(
					Eval.LocalTransform, &ParentEval->ComponentTransform);
			}
			else
			{
				Eval.ComponentTransform = Eval.LocalTransform;
			}
		}

		OutPose.Add(Bone.Id, Eval);
	}

	return true;
}
