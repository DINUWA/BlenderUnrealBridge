#pragma once

#include "CoreMinimal.h"
#include "LiveSync/BridgeLiveSyncProtocol.h"
#include "Core/BridgeDiagnostics.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "Containers/Ticker.h"

/**
 * BridgeLiveSyncReceiver.h — Unreal TCP Server for Live Sync (Milestone 10)
 * =========================================================================
 *
 * Listens on localhost:27284 for incoming connections from Blender.
 *
 * Architecture
 * ------------
 * - A background FRunnableThread runs the accept/read loop.
 * - Incoming messages are placed into a thread-safe queue.
 * - The game-thread Tick() (via FTicker) drains the queue and applies
 *   actor transform updates, which MUST happen on the game thread to
 *   safely access UObjects.
 * - Only one Blender connection is supported at a time (editor bridge).
 * - The receiver shuts down cleanly when StopServer() is called or
 *   when the module shuts down.
 *
 * Object lookup
 * -------------
 * The SpawnedActors map (object_id -> AActor*) is set by calling
 * SetSpawnedActors() after a full package import via FBridgeSceneBuilder.
 * Live-sync updates apply transforms directly to those actors.
 *
 * Usage
 * -----
 *   FBridgeLiveSyncReceiver::Get().SetSpawnedActors(SceneResult.SpawnedActors);
 *   FBridgeLiveSyncReceiver::Get().StartServer();
 *   ...
 *   FBridgeLiveSyncReceiver::Get().StopServer();
 */
class BLENDERUNREALBRIDGE_API FBridgeLiveSyncReceiver : public FRunnable
{
public:
	FBridgeLiveSyncReceiver();
	virtual ~FBridgeLiveSyncReceiver();

	// -----------------------------------------------------------------------
	// Singleton access
	// -----------------------------------------------------------------------

	/** Module-level singleton getter. */
	static FBridgeLiveSyncReceiver& Get();

	// -----------------------------------------------------------------------
	// Server lifecycle
	// -----------------------------------------------------------------------

	/**
	 * Start the TCP listener on the given port.
	 *
	 * @param Port  TCP port to listen on (default: BUBRIDGE_LIVESYNC_DEFAULT_PORT).
	 * @return true if the server started successfully.
	 */
	bool StartServer(int32 Port = BUBRIDGE_LIVESYNC_DEFAULT_PORT);

	/**
	 * Stop the server, close all connections, and join the background thread.
	 * Safe to call multiple times.
	 */
	void StopServer();

	/** Returns true if the server is currently listening. */
	bool IsRunning() const;

	/** Returns true if a Blender session is currently connected and handshook. */
	bool IsSessionConnected() const;

	/** Returns the current active session ID, or empty string if none. */
	FString GetSessionId() const;

	// -----------------------------------------------------------------------
	// Object registry
	// -----------------------------------------------------------------------

	/**
	 * Register the map of Bridge Object ID -> AActor* after a full package import.
	 * The receiver uses this to look up actors by bubridge_id.
	 *
	 * @param InSpawnedActors  TMap<FString, AActor*> from FBridgeSpawnedScene.
	 */
	void SetSpawnedActors(const TMap<FString, AActor*>& InSpawnedActors);

	/** Clear all actor references (e.g. when a new level is loaded). */
	void ClearSpawnedActors();

	// -----------------------------------------------------------------------
	// FRunnable interface (background thread)
	// -----------------------------------------------------------------------

	virtual bool Init() override;
	virtual uint32 Run() override;
	virtual void Stop() override;
	virtual void Exit() override;

	// -----------------------------------------------------------------------
	// Message parsing and validation (public for engine-independent testing)
	// -----------------------------------------------------------------------

	/**
	 * Decode and validate one raw JSON line.
	 *
	 * @param RawLine    UTF-8 JSON string (one line).
	 * @param SessionId  Expected session ID (empty = any).
	 * @return           Validation result with parsed payload.
	 */
	static FBridgeLiveSyncValidationResult ParseAndValidateMessage(
		const FString& RawLine,
		const FString& SessionId = TEXT(""));

private:
	// -----------------------------------------------------------------------
	// Server socket
	// -----------------------------------------------------------------------

	class FSocket* ListenSocket = nullptr;
	class FSocket* ClientSocket = nullptr;

	FString       ActiveSessionId;
	volatile bool bRunning    = false;
	volatile bool bConnected  = false;

	FRunnableThread* Thread = nullptr;

	// Critical section protecting SpawnedActors and the pending update queue
	mutable FCriticalSection ActorMutex;

	/** Map of Bridge Object ID -> AActor* (populated after full import). */
	TMap<FString, TWeakObjectPtr<AActor>> SpawnedActors;

	// -----------------------------------------------------------------------
	// Pending transform update queue (produced on background thread,
	// consumed on game thread via Tick).
	// -----------------------------------------------------------------------

	struct FPendingTransformUpdate
	{
		FString  ObjectId;
		FVector  Location;
		FQuat    Rotation;
		FVector  Scale;
	};

	TArray<FPendingTransformUpdate> PendingUpdates;
	FCriticalSection                PendingUpdatesMutex;

	// -----------------------------------------------------------------------
	// Ticker handle for game-thread update application
	// -----------------------------------------------------------------------

	FTSTicker::FDelegateHandle TickerHandle;

	// -----------------------------------------------------------------------
	// Internal helpers
	// -----------------------------------------------------------------------

	bool HandleClientConnection(class FSocket* Socket);
	bool ReadLine(class FSocket* Socket, FString& OutLine);
	void EnqueueTransformUpdate(const FBridgeLiveSyncTransformUpdate& Update);
	bool DrainPendingUpdates(float DeltaTime);
	void CloseClientSocket();
	void SendLine(class FSocket* Socket, const FString& JsonLine);

	// -----------------------------------------------------------------------
	// Singleton instance
	// -----------------------------------------------------------------------
	static FBridgeLiveSyncReceiver* Instance;
};
