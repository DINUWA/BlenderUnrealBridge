#pragma once

#include "CoreMinimal.h"

/**
 * Diagnostic severity levels conforming to DATA_PROTOCOL.md §5.
 */
enum class EBridgeDiagnosticLevel : uint8
{
	Info,
	Warning,
	Error
};

/**
 * Single diagnostic entry for package validation or ingestion.
 */
struct BLENDERUNREALBRIDGE_API FBridgeDiagnosticMessage
{
	EBridgeDiagnosticLevel Level;
	FString Code;
	FString Message;
	FString TargetId;

	FBridgeDiagnosticMessage()
		: Level(EBridgeDiagnosticLevel::Info)
	{
	}

	FBridgeDiagnosticMessage(EBridgeDiagnosticLevel InLevel, const FString& InCode, const FString& InMessage, const FString& InTargetId = TEXT(""))
		: Level(InLevel)
		, Code(InCode)
		, Message(InMessage)
		, TargetId(InTargetId)
	{
	}

	FString GetLevelString() const
	{
		switch (Level)
		{
		case EBridgeDiagnosticLevel::Info:    return TEXT("INFO");
		case EBridgeDiagnosticLevel::Warning: return TEXT("WARNING");
		case EBridgeDiagnosticLevel::Error:   return TEXT("ERROR");
		default:                              return TEXT("UNKNOWN");
		}
	}
};

/**
 * Complete validation and diagnostic report for a package read operation.
 */
struct BLENDERUNREALBRIDGE_API FBridgeValidationReport
{
	TArray<FBridgeDiagnosticMessage> Messages;

	bool IsValid() const
	{
		for (const FBridgeDiagnosticMessage& Msg : Messages)
		{
			if (Msg.Level == EBridgeDiagnosticLevel::Error)
			{
				return false;
			}
		}
		return true;
	}

	int32 GetErrorCount() const
	{
		int32 Count = 0;
		for (const FBridgeDiagnosticMessage& Msg : Messages)
		{
			if (Msg.Level == EBridgeDiagnosticLevel::Error)
			{
				Count++;
			}
		}
		return Count;
	}

	int32 GetWarningCount() const
	{
		int32 Count = 0;
		for (const FBridgeDiagnosticMessage& Msg : Messages)
		{
			if (Msg.Level == EBridgeDiagnosticLevel::Warning)
			{
				Count++;
			}
		}
		return Count;
	}

	int32 GetInfoCount() const
	{
		int32 Count = 0;
		for (const FBridgeDiagnosticMessage& Msg : Messages)
		{
			if (Msg.Level == EBridgeDiagnosticLevel::Info)
			{
				Count++;
			}
		}
		return Count;
	}

	void AddInfo(const FString& Code, const FString& Message, const FString& TargetId = TEXT(""))
	{
		Messages.Emplace(EBridgeDiagnosticLevel::Info, Code, Message, TargetId);
	}

	void AddWarning(const FString& Code, const FString& Message, const FString& TargetId = TEXT(""))
	{
		Messages.Emplace(EBridgeDiagnosticLevel::Warning, Code, Message, TargetId);
	}

	void AddError(const FString& Code, const FString& Message, const FString& TargetId = TEXT(""))
	{
		Messages.Emplace(EBridgeDiagnosticLevel::Error, Code, Message, TargetId);
	}
};
