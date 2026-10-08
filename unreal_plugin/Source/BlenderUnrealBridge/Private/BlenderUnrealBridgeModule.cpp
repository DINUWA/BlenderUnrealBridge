#include "BlenderUnrealBridgeModule.h"
#include "LiveSync/BridgeLiveSyncReceiver.h"

DEFINE_LOG_CATEGORY(LogBlenderUnrealBridge);

#define LOCTEXT_NAMESPACE "FBlenderUnrealBridgeModule"

void FBlenderUnrealBridgeModule::StartupModule()
{
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("BlenderUnrealBridge module initialized (Version 0.1.0)."));

	// Start the live-sync TCP server automatically on module startup.
	// Blender can connect at any time after this point.
	FBridgeLiveSyncReceiver::Get().StartServer(BUBRIDGE_LIVESYNC_DEFAULT_PORT);
}

void FBlenderUnrealBridgeModule::ShutdownModule()
{
	// Stop the live-sync server cleanly before the module unloads.
	FBridgeLiveSyncReceiver::Get().StopServer();

	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("BlenderUnrealBridge module shutdown."));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FBlenderUnrealBridgeModule, BlenderUnrealBridge)
