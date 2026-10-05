#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogBlenderUnrealBridge, Log, All);

class FBlenderUnrealBridgeModule : public IModuleInterface
{
public:
	/** IModuleInterface implementation */
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

	/** Returns the singleton module instance */
	static FBlenderUnrealBridgeModule& Get()
	{
		return FModuleManager::LoadModuleChecked<FBlenderUnrealBridgeModule>("BlenderUnrealBridge");
	}

	/** Checks if the module is loaded and ready */
	static bool IsAvailable()
	{
		return FModuleManager::Get().IsModuleLoaded("BlenderUnrealBridge");
	}
};
