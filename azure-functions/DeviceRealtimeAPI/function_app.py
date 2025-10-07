import azure.functions as func
import logging
import json
import os
from datetime import datetime, timedelta
from azure.cosmos import CosmosClient

app = func.FunctionApp()

# Cosmos DB connection settings
COSMOS_ENDPOINT = os.environ["COSMOS_ENDPOINT"]
COSMOS_KEY = os.environ["COSMOS_KEY"]
COSMOS_DATABASE = "pokepal-db"
COSMOS_CONTAINER = "conversations"

# Initialize Cosmos DB client
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
database = cosmos_client.get_database_client(COSMOS_DATABASE)
container = database.get_container_client(COSMOS_CONTAINER)

# SignalR Negotiate Function
@app.route(route="negotiate", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST", "GET"])
@app.generic_input_binding(
    arg_name="connectionInfo",
    type="signalRConnectionInfo",
    hubName="deviceStatus",
    connection="AzureSignalRConnectionString"
)
def negotiate(req: func.HttpRequest, connectionInfo) -> func.HttpResponse:
    """Return SignalR connection information"""
    logging.info('SignalR negotiate request received')
    return func.HttpResponse(connectionInfo)

# Cosmos DB Change Feed Trigger
@app.function_name(name="ConversationChangeFeed")
@app.cosmos_db_trigger(
    arg_name="documents",
    database_name="pokepal-db",
    container_name="conversations",
    connection="CosmosDBConnectionString",
    lease_container_name="leases",
    create_lease_container_if_not_exists=True
)
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName="deviceStatus",
    connection="AzureSignalRConnectionString"
)
def conversation_change_feed(documents: func.DocumentList, signalRMessages: func.Out[str]):
    """
    Monitor Cosmos DB conversations container changes and notify device status updates via SignalR
    """
    if documents:
        logging.info(f'Change Feed triggered with {len(documents)} document(s)')

        # Aggregate latest conversation per device
        device_updates = {}

        for doc in documents:
            device_id = doc.get('deviceId')
            if not device_id:
                logging.warning(f'Document missing deviceId: {doc.get("id")}')
                continue

            # Process based on ConversationLogger structure
            # Each document represents a single utterance
            speaker = doc.get('speaker')
            text = doc.get('text')
            timestamp = doc.get('timestamp', datetime.utcnow().isoformat())

            if not speaker or not text:
                logging.warning(f'Document missing speaker or text: {doc.get("id")}')
                continue

            # Keep latest utterance per device (overwrites if multiple in same batch)
            device_updates[device_id] = {
                'deviceId': device_id,
                'lastConversation': {
                    'speaker': speaker,
                    'text': text,
                    'timestamp': timestamp
                },
                'lastSeen': timestamp,
                'status': 'online'  # Device is online if conversation exists
            }

        # Send SignalR message
        if device_updates:
            message = {
                'target': 'deviceUpdated',
                'arguments': [list(device_updates.values())]
            }
            signalRMessages.set(json.dumps(message))
            logging.info(f'Sent SignalR message for {len(device_updates)} device(s)')
