#include "LiveSync/BridgeLiveSyncReceiver.h"
#include "BlenderUnrealBridgeModule.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
#include "Misc/ScopeLock.h"
#include "Async/Async.h"
#include "Containers/Ticker.h"
#include "GameFramework/Actor.h"

// Unreal networking (using raw platform sockets for simplicity and no extra module dependencies)
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "IPAddress.h"

// ---------------------------------------------------------------------------
// Singleton instance
// ---------------------------------------------------------------------------

FBridgeLiveSyncReceiver* FBridgeLiveSyncReceiver::Instance = nullptr;

FBridgeLiveSyncReceiver& FBridgeLiveSyncReceiver::Get()
{
	if (!Instance)
	{
		Instance = new FBridgeLiveSyncReceiver();
	}
	return *Instance;
}

// ---------------------------------------------------------------------------
// Constructor / Destructor
// ---------------------------------------------------------------------------

FBridgeLiveSyncReceiver::FBridgeLiveSyncReceiver()
{
}

FBridgeLiveSyncReceiver::~FBridgeLiveSyncReceiver()
{
	StopServer();
}

// ---------------------------------------------------------------------------
// Server lifecycle
// ---------------------------------------------------------------------------

bool FBridgeLiveSyncReceiver::StartServer(int32 Port)
{
	if (bRunning)
	{
		UE_LOG(LogBlenderUnrealBridge, Warning, TEXT("[LiveSync] Server already running on port %d."), Port);
		return true;
	}

	ISocketSubsystem* SocketSub = ISocketSubsystem::Get(NAME_None);
	if (!SocketSub)
	{
		UE_LOG(LogBlenderUnrealBridge, Error, TEXT("[LiveSync] No socket subsystem available."));
		return false;
	}

	ListenSocket = SocketSub->CreateSocket(NAME_Stream, TEXT("BridgeLiveSyncListener"), false);
	if (!ListenSocket)
	{
		UE_LOG(LogBlenderUnrealBridge, Error, TEXT("[LiveSync] Failed to create listen socket."));
		return false;
	}

	// Allow address reuse so quick restarts work
	ListenSocket->SetReuseAddr(true);
	ListenSocket->SetNonBlocking(false);

	TSharedRef<FInternetAddr> Addr = SocketSub->CreateInternetAddr();
	bool bAddrValid = false;
	Addr->SetIp(TEXT("127.0.0.1"), bAddrValid);
	Addr->SetPort(Port);

	if (!bAddrValid)
	{
		UE_LOG(LogBlenderUnrealBridge, Error, TEXT("[LiveSync] Failed to parse listen address."));
		SocketSub->DestroySocket(ListenSocket);
		ListenSocket = nullptr;
		return false;
	}

	if (!ListenSocket->Bind(*Addr))
	{
		UE_LOG(LogBlenderUnrealBridge, Error, TEXT("[LiveSync] Failed to bind on port %d. Is another process already using it?"), Port);
		SocketSub->DestroySocket(ListenSocket);
		ListenSocket = nullptr;
		return false;
	}

	if (!ListenSocket->Listen(1))
	{
		UE_LOG(LogBlenderUnrealBridge, Error, TEXT("[LiveSync] Failed to listen on port %d."), Port);
		SocketSub->DestroySocket(ListenSocket);
		ListenSocket = nullptr;
		return false;
	}

	bRunning = true;
	Thread = FRunnableThread::Create(this, TEXT("BridgeLiveSyncThread"), 0, TPri_Normal);

	// Register game-thread ticker to drain pending updates
	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateRaw(this, &FBridgeLiveSyncReceiver::DrainPendingUpdates),
		0.016f); // ~60 fps drain rate

	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Server started on port %d."), Port);
	return true;
}

void FBridgeLiveSyncReceiver::StopServer()
{
	if (!bRunning)
	{
		return;
	}

	bRunning = false;
	bConnected = false;

	// Remove game-thread ticker
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}

	// Close client socket first (this unblocks any blocking recv)
	CloseClientSocket();

	// Close listen socket
	ISocketSubsystem* SocketSub = ISocketSubsystem::Get(NAME_None);
	if (ListenSocket && SocketSub)
	{
		ListenSocket->Close();
		SocketSub->DestroySocket(ListenSocket);
		ListenSocket = nullptr;
	}

	// Wait for background thread
	if (Thread)
	{
		Thread->WaitForCompletion();
		delete Thread;
		Thread = nullptr;
	}

	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Server stopped."));
}

bool FBridgeLiveSyncReceiver::IsRunning() const
{
	return bRunning;
}

bool FBridgeLiveSyncReceiver::IsSessionConnected() const
{
	return bConnected;
}

FString FBridgeLiveSyncReceiver::GetSessionId() const
{
	FScopeLock Lock(&ActorMutex);
	return ActiveSessionId;
}

// ---------------------------------------------------------------------------
// Object registry
// ---------------------------------------------------------------------------

void FBridgeLiveSyncReceiver::SetSpawnedActors(const TMap<FString, AActor*>& InSpawnedActors)
{
	FScopeLock Lock(&ActorMutex);
	SpawnedActors.Empty(InSpawnedActors.Num());
	for (const auto& Pair : InSpawnedActors)
	{
		if (Pair.Value)
		{
			SpawnedActors.Add(Pair.Key, TWeakObjectPtr<AActor>(Pair.Value));
		}
	}
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Registered %d actors for live sync."), SpawnedActors.Num());
}

void FBridgeLiveSyncReceiver::ClearSpawnedActors()
{
	FScopeLock Lock(&ActorMutex);
	SpawnedActors.Empty();
}

// ---------------------------------------------------------------------------
// FRunnable — Background Thread
// ---------------------------------------------------------------------------

bool FBridgeLiveSyncReceiver::Init()
{
	return true;
}

uint32 FBridgeLiveSyncReceiver::Run()
{
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Background accept thread running."));

	while (bRunning)
	{
		if (!ListenSocket)
		{
			break;
		}

		// Set a short timeout on the listen socket so we can check bRunning
		bool bHasPendingConnection = false;
		if (!ListenSocket->HasPendingConnection(bHasPendingConnection))
		{
			FPlatformProcess::Sleep(0.05f);
			continue;
		}

		if (!bHasPendingConnection)
		{
			FPlatformProcess::Sleep(0.05f);
			continue;
		}

		ISocketSubsystem* SocketSub = ISocketSubsystem::Get(NAME_None);
		TSharedRef<FInternetAddr> ClientAddr = SocketSub->CreateInternetAddr();
		FSocket* NewClientSocket = ListenSocket->Accept(*ClientAddr, TEXT("BridgeLiveSyncClient"));

		if (!NewClientSocket)
		{
			continue;
		}

		if (bConnected)
		{
			// Already have a client — reject new connections politely
			UE_LOG(LogBlenderUnrealBridge, Warning, TEXT("[LiveSync] Rejecting additional connection — already connected."));
			NewClientSocket->Close();
			SocketSub->DestroySocket(NewClientSocket);
			continue;
		}

		ClientSocket = NewClientSocket;
		ClientSocket->SetNonBlocking(false);
		int32 NewSize = 0;
		ClientSocket->SetReceiveBufferSize(65536, NewSize);

		FString ClientAddrStr = ClientAddr->ToString(true);
		UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Blender connected from %s."), *ClientAddrStr);

		HandleClientConnection(ClientSocket);

		CloseClientSocket();
		bConnected = false;
		{
			FScopeLock Lock(&ActorMutex);
			ActiveSessionId.Empty();
		}
		UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Blender connection closed."));
	}

	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Background accept thread exiting."));
	return 0;
}

void FBridgeLiveSyncReceiver::Stop()
{
	bRunning = false;
	CloseClientSocket();
}

void FBridgeLiveSyncReceiver::Exit()
{
}

// ---------------------------------------------------------------------------
// HandleClientConnection — read loop for one connected Blender session
// ---------------------------------------------------------------------------

bool FBridgeLiveSyncReceiver::HandleClientConnection(FSocket* Socket)
{
	// --- Handshake: expect HELLO ---
	FString HelloLine;
	if (!ReadLine(Socket, HelloLine))
	{
		UE_LOG(LogBlenderUnrealBridge, Warning, TEXT("[LiveSync] Failed to read HELLO."));
		return false;
	}

	FBridgeLiveSyncValidationResult HelloResult = ParseAndValidateMessage(HelloLine);
	if (!HelloResult.bValid || HelloResult.MessageType != LIVESYNC_MSG_HELLO)
	{
		UE_LOG(LogBlenderUnrealBridge, Warning, TEXT("[LiveSync] Invalid HELLO: %s"), *HelloResult.ErrorMessage);

		// Parse session ID for the rejection ACK (best-effort)
		TSharedPtr<FJsonObject> HelloJson;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(HelloLine);
		FJsonSerializer::Deserialize(Reader, HelloJson);
		FString RejectSessionId = HelloJson.IsValid() ? HelloJson->GetStringField(TEXT("session_id")) : TEXT("unknown");

		FString RejectAck = FString::Printf(
			TEXT("{\"message_type\":\"HELLO_ACK\",\"protocol_version\":\"%s\",\"session_id\":\"%s\",\"accepted\":false,\"reason\":\"%s\",\"sequence\":0}\n"),
			BUBRIDGE_LIVESYNC_PROTOCOL_VERSION, *RejectSessionId, *HelloResult.ErrorMessage.Replace(TEXT("\""), TEXT("'")));
		SendLine(Socket, RejectAck);
		return false;
	}

	// Parse session ID from HELLO
	TSharedPtr<FJsonObject> HelloJson;
	TSharedRef<TJsonReader<>> HelloReader = TJsonReaderFactory<>::Create(HelloLine);
	FJsonSerializer::Deserialize(HelloReader, HelloJson);
	FString SessionId = HelloJson.IsValid() ? HelloJson->GetStringField(TEXT("session_id")) : TEXT("");
	{
		FScopeLock Lock(&ActorMutex);
		ActiveSessionId = SessionId;
	}

	// --- Send HELLO_ACK ---
	FString HelloAck = FString::Printf(
		TEXT("{\"message_type\":\"HELLO_ACK\",\"protocol_version\":\"%s\",\"session_id\":\"%s\",\"accepted\":true,\"sequence\":0}\n"),
		BUBRIDGE_LIVESYNC_PROTOCOL_VERSION, *SessionId);
	SendLine(Socket, HelloAck);

	bConnected = true;
	UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] Handshake complete. Session: %s"), *SessionId);

	// --- Main receive loop ---
	while (bRunning && bConnected)
	{
		FString Line;
		if (!ReadLine(Socket, Line))
		{
			// Connection closed or error
			break;
		}

		if (Line.IsEmpty())
		{
			continue;
		}

		FBridgeLiveSyncValidationResult Result = ParseAndValidateMessage(Line, SessionId);
		if (!Result.bValid)
		{
			UE_LOG(LogBlenderUnrealBridge, Warning,
				TEXT("[LiveSync] Dropping invalid message: %s"), *Result.ErrorMessage);
			continue;
		}

		if (Result.MessageType == LIVESYNC_MSG_GOODBYE)
		{
			UE_LOG(LogBlenderUnrealBridge, Log, TEXT("[LiveSync] GOODBYE received."));
			break;
		}
		else if (Result.MessageType == LIVESYNC_MSG_KEEPALIVE)
		{
			// Nothing to do — keepalive noted
		}
		else if (Result.MessageType == LIVESYNC_MSG_OBJECT_TRANSFORM_UPDATE)
		{
			if (Result.TransformUpdate.IsSet())
			{
				EnqueueTransformUpdate(Result.TransformUpdate.GetValue());
			}
		}
	}

	return true;
}

// ---------------------------------------------------------------------------
// ReadLine — blocking read of one newline-terminated UTF-8 line
// ---------------------------------------------------------------------------

bool FBridgeLiveSyncReceiver::ReadLine(FSocket* Socket, FString& OutLine)
{
	OutLine.Empty();
	TArray<uint8> Buffer;

	while (bRunning)
	{
		uint8 Byte = 0;
		int32 BytesRead = 0;

		// Set a short timeout so we can check bRunning
		bool bHasData = false;
		if (Socket->HasPendingData(*(uint32*)&BytesRead))
		{
			// There's data waiting
		}
		else
		{
			// Poll: check every 50ms
			FPlatformProcess::Sleep(0.05f);
			continue;
		}

		if (!Socket->Recv(&Byte, 1, BytesRead) || BytesRead == 0)
		{
			return false; // Connection closed
		}

		if (Byte == '\n')
		{
			break;
		}
		Buffer.Add(Byte);
	}

	if (!bRunning)
	{
		return false;
	}

	OutLine = FString(Buffer.Num(), (const char*)Buffer.GetData());
	return true;
}

// ---------------------------------------------------------------------------
// SendLine
// ---------------------------------------------------------------------------

void FBridgeLiveSyncReceiver::SendLine(FSocket* Socket, const FString& JsonLine)
{
	if (!Socket)
	{
		return;
	}

	FTCHARToUTF8 Converter(*JsonLine);
	int32 BytesSent = 0;
	Socket->Send(
		reinterpret_cast<const uint8*>(Converter.Get()),
		Converter.Length(),
		BytesSent);
}

// ---------------------------------------------------------------------------
// Pending update queue
// ---------------------------------------------------------------------------

void FBridgeLiveSyncReceiver::EnqueueTransformUpdate(const FBridgeLiveSyncTransformUpdate& Update)
{
	FScopeLock Lock(&PendingUpdatesMutex);

	// Overwrite any existing pending update for the same object (keep only latest)
	for (FPendingTransformUpdate& Existing : PendingUpdates)
	{
		if (Existing.ObjectId == Update.ObjectId)
		{
			Existing.Location = Update.Location;
			Existing.Rotation = Update.Rotation;
			Existing.Scale    = Update.Scale;
			return;
		}
	}

	FPendingTransformUpdate Entry;
	Entry.ObjectId = Update.ObjectId;
	Entry.Location = Update.Location;
	Entry.Rotation = Update.Rotation;
	Entry.Scale    = Update.Scale;
	PendingUpdates.Add(Entry);
}

bool FBridgeLiveSyncReceiver::DrainPendingUpdates(float DeltaTime)
{
	TArray<FPendingTransformUpdate> LocalUpdates;
	{
		FScopeLock Lock(&PendingUpdatesMutex);
		LocalUpdates = MoveTemp(PendingUpdates);
		PendingUpdates.Empty();
	}

	if (LocalUpdates.IsEmpty())
	{
		return true; // Keep ticker alive
	}

	FScopeLock Lock(&ActorMutex);

	for (const FPendingTransformUpdate& Update : LocalUpdates)
	{
		TWeakObjectPtr<AActor>* FoundActor = SpawnedActors.Find(Update.ObjectId);
		if (!FoundActor || !FoundActor->IsValid())
		{
			UE_LOG(LogBlenderUnrealBridge, Warning,
				TEXT("[LiveSync] OBJECT_TRANSFORM_UPDATE: object_id '%s' not found in spawned actors. Update ignored."),
				*Update.ObjectId);
			continue;
		}

		AActor* Actor = FoundActor->Get();
		if (!IsValid(Actor))
		{
			continue;
		}

		// Build the Unreal FTransform from the canonical Bridge values.
		// Canonical == Unreal coordinate space (no additional conversion needed).
		FTransform NewTransform(Update.Rotation, Update.Location, Update.Scale);

		if (Actor->GetAttachParentActor())
		{
			// Child actor: apply as relative transform
			if (Actor->GetRootComponent())
			{
				Actor->GetRootComponent()->SetRelativeTransform(NewTransform);
			}
		}
		else
		{
			// Root actor: apply as world transform
			Actor->SetActorTransform(NewTransform);
		}
	}

	return true; // Keep ticker alive
}

// ---------------------------------------------------------------------------
// CloseClientSocket
// ---------------------------------------------------------------------------

void FBridgeLiveSyncReceiver::CloseClientSocket()
{
	if (ClientSocket)
	{
		ISocketSubsystem* SocketSub = ISocketSubsystem::Get(NAME_None);
		ClientSocket->Close();
		if (SocketSub)
		{
			SocketSub->DestroySocket(ClientSocket);
		}
		ClientSocket = nullptr;
	}
}

// ---------------------------------------------------------------------------
// ParseAndValidateMessage — public, engine-independent, testable
// ---------------------------------------------------------------------------

FBridgeLiveSyncValidationResult FBridgeLiveSyncReceiver::ParseAndValidateMessage(
	const FString& RawLine,
	const FString& SessionId)
{
	FBridgeLiveSyncValidationResult Result;

	// Parse JSON
	TSharedPtr<FJsonObject> Json;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawLine.TrimEnd());
	if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid())
	{
		Result.bValid = false;
		Result.ErrorMessage = TEXT("Failed to parse JSON.");
		return Result;
	}

	// --- Required fields: message_type, protocol_version, session_id ---
	FString MsgType, ProtoVersion, MsgSessionId;

	if (!Json->TryGetStringField(TEXT("message_type"), MsgType) || MsgType.IsEmpty())
	{
		Result.bValid = false;
		Result.ErrorMessage = TEXT("Missing or empty 'message_type'.");
		return Result;
	}

	if (!Json->TryGetStringField(TEXT("protocol_version"), ProtoVersion))
	{
		Result.bValid = false;
		Result.ErrorMessage = TEXT("Missing 'protocol_version'.");
		return Result;
	}

	if (ProtoVersion != BUBRIDGE_LIVESYNC_PROTOCOL_VERSION)
	{
		Result.bValid = false;
		Result.ErrorMessage = FString::Printf(
			TEXT("Unsupported protocol version '%s'. Expected '%s'."),
			*ProtoVersion, BUBRIDGE_LIVESYNC_PROTOCOL_VERSION);
		return Result;
	}

	if (!Json->TryGetStringField(TEXT("session_id"), MsgSessionId) || MsgSessionId.IsEmpty())
	{
		Result.bValid = false;
		Result.ErrorMessage = TEXT("Missing or empty 'session_id'.");
		return Result;
	}

	// Session ID check (skip for HELLO which establishes the session)
	if (!SessionId.IsEmpty() && MsgType != LIVESYNC_MSG_HELLO && MsgSessionId != SessionId)
	{
		Result.bValid = false;
		Result.ErrorMessage = FString::Printf(
			TEXT("Session ID mismatch: expected '%s', got '%s'."),
			*SessionId, *MsgSessionId);
		return Result;
	}

	Result.MessageType = MsgType;

	// --- Message-type specific validation ---
	static const TSet<FString> KnownTypes = {
		LIVESYNC_MSG_HELLO,
		LIVESYNC_MSG_HELLO_ACK,
		LIVESYNC_MSG_GOODBYE,
		LIVESYNC_MSG_KEEPALIVE,
		LIVESYNC_MSG_OBJECT_TRANSFORM_UPDATE,
	};

	if (!KnownTypes.Contains(MsgType))
	{
		Result.bValid = false;
		Result.ErrorMessage = FString::Printf(TEXT("Unknown message_type '%s'."), *MsgType);
		return Result;
	}

	if (MsgType == LIVESYNC_MSG_OBJECT_TRANSFORM_UPDATE)
	{
		// object_id
		FString ObjId;
		if (!Json->TryGetStringField(TEXT("object_id"), ObjId) || ObjId.IsEmpty())
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: Missing 'object_id'.");
			return Result;
		}

		// Validate object_id format: "obj_XXXXXXXX" (12 chars)
		if (!ObjId.StartsWith(TEXT("obj_")) || ObjId.Len() != 12)
		{
			Result.bValid = false;
			Result.ErrorMessage = FString::Printf(
				TEXT("OBJECT_TRANSFORM_UPDATE: Invalid object_id format '%s'. Expected 'obj_<8 hex>'."),
				*ObjId);
			return Result;
		}

		// transform block
		const TSharedPtr<FJsonObject>* TransformObj = nullptr;
		if (!Json->TryGetObjectField(TEXT("transform"), TransformObj) || !TransformObj || !TransformObj->IsValid())
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: Missing 'transform' block.");
			return Result;
		}

		const TArray<TSharedPtr<FJsonValue>>* LocArr = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* RotArr = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* ScaleArr = nullptr;

		if (!(*TransformObj)->TryGetArrayField(TEXT("location"), LocArr) || !LocArr || LocArr->Num() != 3)
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'transform.location' must be [x, y, z].");
			return Result;
		}

		if (!(*TransformObj)->TryGetArrayField(TEXT("rotation"), RotArr) || !RotArr || RotArr->Num() != 4)
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'transform.rotation' must be [x, y, z, w].");
			return Result;
		}

		if (!(*TransformObj)->TryGetArrayField(TEXT("scale"), ScaleArr) || !ScaleArr || ScaleArr->Num() != 3)
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'transform.scale' must be [sx, sy, sz].");
			return Result;
		}

		// Build the payload
		FBridgeLiveSyncTransformUpdate Payload;
		Payload.ObjectId  = ObjId;
		Payload.Location  = FVector(
			(float)(*LocArr)[0]->AsNumber(),
			(float)(*LocArr)[1]->AsNumber(),
			(float)(*LocArr)[2]->AsNumber());
		Payload.Rotation  = FQuat(
			(float)(*RotArr)[0]->AsNumber(),
			(float)(*RotArr)[1]->AsNumber(),
			(float)(*RotArr)[2]->AsNumber(),
			(float)(*RotArr)[3]->AsNumber());
		Payload.Scale     = FVector(
			(float)(*ScaleArr)[0]->AsNumber(),
			(float)(*ScaleArr)[1]->AsNumber(),
			(float)(*ScaleArr)[2]->AsNumber());

		bool bNegScale = false;
		(*TransformObj)->TryGetBoolField(TEXT("has_negative_scale"), bNegScale);
		Payload.bHasNegativeScale = bNegScale;

		// Validate finiteness
		if (!FMath::IsFinite(Payload.Location.X) || !FMath::IsFinite(Payload.Location.Y) || !FMath::IsFinite(Payload.Location.Z))
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'location' contains non-finite value.");
			return Result;
		}
		if (!FMath::IsFinite(Payload.Rotation.X) || !FMath::IsFinite(Payload.Rotation.Y) ||
			!FMath::IsFinite(Payload.Rotation.Z) || !FMath::IsFinite(Payload.Rotation.W))
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'rotation' contains non-finite value.");
			return Result;
		}
		if (!FMath::IsFinite(Payload.Scale.X) || !FMath::IsFinite(Payload.Scale.Y) || !FMath::IsFinite(Payload.Scale.Z))
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'scale' contains non-finite value.");
			return Result;
		}
		if (FMath::IsNearlyZero(Payload.Scale.X) || FMath::IsNearlyZero(Payload.Scale.Y) || FMath::IsNearlyZero(Payload.Scale.Z))
		{
			Result.bValid = false;
			Result.ErrorMessage = TEXT("OBJECT_TRANSFORM_UPDATE: 'scale' must not contain zero components.");
			return Result;
		}

		Result.TransformUpdate = Payload;
	}

	Result.bValid = true;
	return Result;
}
