#include "BlenderUnrealBridgeModule.h"

DEFINE_LOG_CATEGORY(LogBlenderUnrealBridge);

#define LOCTEXT_NAMESPACE "FBlenderUnrealBridgeModule"

void FBlenderUnrealBridgeModule::StartupModule()
{
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("BlenderUnrealBridge module initialized (Version 0.1.0)."));
}

void FBlenderUnrealBridgeModule::ShutdownModule()
{
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("BlenderUnrealBridge module shutdown."));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FBlenderUnrealBridgeModule, BlenderUnrealBridge)
