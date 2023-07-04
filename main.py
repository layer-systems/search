import asyncio
import os
import websockets
import json
from elasticsearch import Elasticsearch

async def relay_websockets(inputWebsocket, kinds, es):
    while True:
        try:
            # Wait for an event on websocket 1
            event = json.loads(await inputWebsocket.recv())
            try:
                if(event[0] == "EVENT"):
                    # Remove the event ID from the event
                    del event[1]
                    print("Sending event " + str(event[1]['id']) + " (kind: "+str(event[1]['kind'])+") to elasticsearch")
                    # send event to elasticsearch
                    resp = es.index(index="nostr", id=str(event[1]['id']), document=event[1])
                    if(resp['result'] != "created"):
                        print("Failed to send event to elasticsearch: "+str(resp))
                elif(event[0] == "EOSE"):
                    print("End of stream")

            except Exception as error:
                print(f"Failed to relay event: {error}")
                if("sent 1011" in str(error)):
                    print("Got Code 1011 -> Closing websockets...")
                    websockets.close()
                continue

        except websockets.ConnectionClosed:
            # If either websocket is closed, attempt to reconnect
            print("Connection closed, attempting to reconnect...")
            await asyncio.sleep(1)
            try:
                async with websockets.connect(os.environ.get("INPUT_RELAY")) as inputWebsocket:
                    message = '["REQ", "1337", {"kinds": '+kinds+', "limit": 10}]'
                    await inputWebsocket.send(message)
                    await relay_websockets(inputWebsocket, kinds, es=es)

            except Exception as error:
                # If the reconnection attempt fails, repeat the loop and try again
                print(f"Failed to reconnect: {error}")
                continue

async def main():
    print("Scraper started...")
    # Read the websocket URLs from environment variables
    inputUrl = os.environ.get("INPUT_RELAY")
    kinds = os.environ.get("KINDS")
    ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "elastic")

    # Create the client instance
    client = Elasticsearch(
        "https://es01:9200",
        ca_certs="/app/certs/ca/ca.crt",
        basic_auth=("elastic", ELASTIC_PASSWORD)
    )

    # If the INPUT_RELAY is missing, raise an error
    if not inputUrl:
        raise ValueError("Please set the INPUT_RELAY environment variable")

    try:
        async with websockets.connect(inputUrl) as inputWebsocket:
            message = '["REQ", "1337", {"kinds": '+kinds+'}]'
            await inputWebsocket.send(message)
            await relay_websockets(inputWebsocket, kinds, es=client)

    except Exception as error:
        # If the initial connection attempt fails, attempt to reconnect immediately
        print(f"Failed to connect: {error}")
        await asyncio.sleep(1)
        await main()

# Start the script
asyncio.run(main())