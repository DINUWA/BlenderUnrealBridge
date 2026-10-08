#pragma once

#include "CoreMinimal.h"

/**
 * BridgeLiveSyncProtocol.h — Live Sync Protocol Constants (Milestone 10)
 * =======================================================================
 *
 * Shared protocol constants for the BUBRIDGE_LIVESYNC v0.1.0 protocol.
 *
 * Message types, protocol version, and default port mirror the Blender-side
 * protocol.py definitions.  Any change to the protocol version must be
 * updated in both places.
 *
 * Wire format: newline-delimited UTF-8 JSON over TCP (localhost default port 27284).
 *
 * All values are absolute canonical Bridge transforms (LH, +Z Up, +X Forward,
 * +Y Right, centimetres) — no secondary conversion is performed.
 */

/** Protocol version string embedded in every live-sync message. */
#define BUBRIDGE_LIVESYNC_PROTOCOL_VERSION TEXT("0.1.0")

/** Default TCP port the Unreal server listens on. */
#define BUBRIDGE_LIVESYNC_DEFAULT_PORT 27284

/** Default host (localhost) */
#define BUBRIDGE_LIVESYNC_DEFAULT_HOST TEXT("127.0.0.1")

// ---------------------------------------------------------------------------
// Message type string constants
// ---------------------------------------------------------------------------
#define LIVESYNC_MSG_HELLO                     TEXT("HELLO")
#define LIVESYNC_MSG_HELLO_ACK                 TEXT("HELLO_ACK")
#define LIVESYNC_MSG_GOODBYE                   TEXT("GOODBYE")
#define LIVESYNC_MSG_KEEPALIVE                 TEXT("KEEPALIVE")
#define LIVESYNC_MSG_OBJECT_TRANSFORM_UPDATE   TEXT("OBJECT_TRANSFORM_UPDATE")

// ---------------------------------------------------------------------------
// Parsed transform update payload
// ---------------------------------------------------------------------------

/**
 * Decoded payload from an OBJECT_TRANSFORM_UPDATE message.
 * All values are in canonical Bridge space (LH centimetres).
 */
struct BLENDERUNREALBRIDGE_API FBridgeLiveSyncTransformUpdate
{
	FString ObjectId;
	FVector Location    = FVector::ZeroVector;
	FQuat   Rotation    = FQuat::Identity;
	FVector Scale       = FVector::OneVector;
	bool    bHasNegativeScale = false;
};

// ---------------------------------------------------------------------------
// Validation result for a decoded live-sync message
// ---------------------------------------------------------------------------

struct BLENDERUNREALBRIDGE_API FBridgeLiveSyncValidationResult
{
	bool    bValid = false;
	FString MessageType;
	FString ErrorMessage;

	/** Only populated for OBJECT_TRANSFORM_UPDATE messages when bValid is true. */
	TOptional<FBridgeLiveSyncTransformUpdate> TransformUpdate;
};
