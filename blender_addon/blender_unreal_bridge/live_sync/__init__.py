"""
live_sync — Blender ↔ Unreal Live Synchronization Layer (Milestone 10)
=======================================================================

This package implements the Blender side of the live synchronisation layer.

Sub-modules
-----------
protocol     : Message schema constants and builders.
transport    : TCP socket transport (client side).
session      : Session lifecycle (connect, disconnect, handshake).
change_detector : Depsgraph-based change detection and dirty tracking.
"""
