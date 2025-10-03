"""Device Status API for PokePal Admin Dashboard."""
import os
import json
import logging
from datetime import datetime, timezone
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.core.exceptions import AzureError

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp()

# Initialize Cosmos DB connection (created once outside functions)
cosmos_connection = os.environ.get("CosmosDBConnection")
cosmos_client = None
conversations_container = None

if cosmos_connection:
    try:
        cosmos_client = CosmosClient.from_connection_string(cosmos_connection)
        database = cosmos_client.get_database_client("pokepal-db")
        database.read()  # Verify connection
        conversations_container = database.get_container_client("conversations")
        logger.info("Cosmos DB clients initialized successfully")
    except AzureError as e:
        logger.error("Azure service error initializing Cosmos DB: %s", e)
    except ValueError as e:
        logger.error("Invalid connection string format: %s", e)
    except Exception as e:
        logger.error("Unexpected error initializing Cosmos DB: %s", e)
else:
    logger.warning("CosmosDBConnection not configured - running without database")


def get_latest_conversation(device_id: str):
    """Get the latest conversation for a device.

    Args:
        device_id: Device ID (e.g., 'PokepalDevice1')

    Returns:
        dict: Latest conversation data or None if not found
    """
    try:
        # Query CosmosDB for the latest conversation
        query = """
            SELECT TOP 1
                c.timestamp,
                c.speaker,
                c.text
            FROM c
            WHERE c.type = 'conversation'
              AND c.deviceId = @deviceId
            ORDER BY c.timestamp DESC
        """

        parameters = [
            {"name": "@deviceId", "value": device_id}
        ]

        items = list(conversations_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        if items:
            return items[0]
        return None

    except Exception as e:
        logger.error("Failed to get latest conversation for %s: %s", device_id, e)
        return None


@app.route(route="devices", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def devices(req: func.HttpRequest) -> func.HttpResponse:
    """Get device status and latest conversation.

    Returns:
        JSON response with device information
    """
    # Check CosmosDB connection
    if not conversations_container:
        logger.warning("Database not available")
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    # Device list
    device_ids = ["PokepalDevice1", "PokepalDevice2"] #TODO: hardcoded for now, will be dynamic in the future
    devices_data = []

    for device_id in device_ids:
        # Get latest conversation
        latest_conv = get_latest_conversation(device_id)

        if latest_conv:
            # Has conversation data
            last_seen_str = latest_conv['timestamp']
            last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
            # If no timezone info, assume UTC
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            minutes_ago = (now - last_seen).total_seconds() / 60

            # Determine status (online if within 5 minutes)
            status = "online" if minutes_ago < 5 else "offline"

            devices_data.append({
                "deviceId": device_id,
                "status": status,
                "lastSeen": last_seen_str,
                "lastConversation": {
                    "speaker": latest_conv['speaker'],
                    "text": latest_conv['text'],
                    "timestamp": latest_conv['timestamp']
                }
            })
        else: #TODO: logic should be checked
            # No conversation data
            devices_data.append({
                "deviceId": device_id,
                "status": "unknown",
                "lastSeen": None,
                "lastConversation": None
            })

    # Return JSON response
    return func.HttpResponse(
        json.dumps({"devices": devices_data}),
        mimetype="application/json",
        status_code=200
    )