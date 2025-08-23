"""Azure Functions for receiving conversation and telemetry data from IoT Hub and storing in Cosmos DB."""
import os
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.iot.hub import IoTHubRegistryManager
from azure.core.exceptions import AzureError

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp()

# Initialize Cosmos DB connection (created once outside functions)
cosmos_connection = os.environ.get("CosmosDBConnection")
cosmos_client = None
conversations_container = None
telemetry_container = None

if cosmos_connection:
    try:
        cosmos_client = CosmosClient.from_connection_string(cosmos_connection)
        # TODO: Make database name configurable via environment variable (when creating ARM template)
        database = cosmos_client.get_database_client("pokepal-db")
        
        # Verify connection (early error detection)
        database.read()
        
        conversations_container = database.get_container_client("conversations")
        telemetry_container = database.get_container_client("telemetry")
        logger.info("Cosmos DB clients initialized successfully")
        
    except AzureError as e:
        # Azure-specific errors (authentication, network, etc.)
        logger.error(f"Azure service error initializing Cosmos DB: {e}")
        # Keep clients as None, check in subsequent processing
        
    except ValueError as e:
        # Connection string format error
        logger.error(f"Invalid connection string format: {e}")
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error initializing Cosmos DB: {e}")
else:
    logger.warning("CosmosDBConnection not configured - running without database")


@app.function_name("conversation_logger")
@app.event_hub_message_trigger(arg_name="events",
                               event_hub_name="YOUR_IOT_HUB_NAME",
                               connection="EventHubConnectionString",
                               consumer_group="conversationlogger")
def conversation_logger(events: func.EventHubEvent) -> None:
    """Process conversation messages from IoT Hub and save to Cosmos DB."""
    # Convert to list if single event
    if not isinstance(events, list):
        events = [events]
    
    logger.info(f'Processing {len(events)} messages from IoT Hub')
    
    for index, event in enumerate(events):
        try:
            # TODO: Eliminate duplicate message decoding logic (shared with telemetry_logger)
            # Note: Need to verify common function behavior in Azure Functions environment
            # Decode message
            message_data = None
            if hasattr(event, 'get_body'):
                body = event.get_body()
                if isinstance(body, bytes):
                    decoded_string = body.decode('utf-8')
                    message_data = json.loads(decoded_string)
                else:
                    message_data = json.loads(body)
            else:
                # Treat as string
                message_data = json.loads(event)
            
            logger.info(f'Message {index}: {json.dumps(message_data)[:200]}...')
            
            # Extract information from message
            message_type = message_data.get('messageType') or message_data.get('type', 'unknown')
            timestamp = message_data.get('timestamp', datetime.now(timezone.utc).isoformat())
            
            # Get device info (prioritize from message body)
            device_id = message_data.get('device_id', 'unknown')
            module_id = message_data.get('module_id', 'unknown')
            
            # Try to get from system properties if not in message body
            if device_id == 'unknown':
                try:
                    # Get from EventHubEvent system properties
                    if hasattr(event, 'system_properties'):
                        system_props = event.system_properties
                        device_id = system_props.get('iothub-connection-device-id', device_id)
                        module_id = system_props.get('iothub-connection-module-id', module_id)
                        logger.info(f'Device info from system properties: device_id={device_id}, module_id={module_id}')
                except Exception as e:
                    logger.warning(f'Failed to get device info from system properties: {e}')
            
            # Create document for Cosmos DB
            document = {
                'id': f'{message_type}_{int(datetime.now(timezone.utc).timestamp())}_{datetime.now(timezone.utc).strftime("%f")}',
                'deviceId': device_id,
                'moduleId': module_id,
                'timestamp': timestamp,
                'type': message_type,
                'receivedAt': datetime.now(timezone.utc).isoformat()
            }
            
            # Extract important fields to top level by message type
            if message_type == 'conversation':
                # Conversation data from voice-conversation
                if 'data' in message_data:
                    speaker = message_data['data'].get('speaker')
                    # Convert "ai" to "assistant" (align with OpenAI API standard)
                    if speaker == 'ai':
                        speaker = 'assistant'
                    document['speaker'] = speaker
                    document['text'] = message_data['data'].get('text')
            else:
                # Currently only process conversation type
                logger.info(f'Skipping non-conversation message type: {message_type}')
                continue
            
            # Keep original data (for debugging and future analysis)
            document['rawData'] = message_data
            
            # Save directly to Cosmos DB
            if conversations_container:
                try:
                    conversations_container.create_item(body=document)
                    logger.info(f'Saved document: id={document["id"]}, type={document["type"]}, '
                               f'speaker={document.get("speaker")}, '
                               f'text={document.get("text", "")[:50] if document.get("text") else None}...')
                except Exception as e:
                    logger.error(f'Failed to save document to Cosmos DB: {e}')
            else:
                logger.error('Cosmos DB container not initialized')
                
        except Exception as e:
            logger.error(f'Error processing message {index}: {e}')
            logger.exception(e)
    
    logger.info(f'Completed processing {len(events)} messages')


@app.function_name("telemetry_logger")
@app.event_hub_message_trigger(arg_name="events",
                               event_hub_name="YOUR_IOT_HUB_NAME",
                               connection="EventHubConnectionString",
                               consumer_group="telemetrylogger")
def telemetry_logger(events: func.EventHubEvent) -> None:
    """Process telemetry messages from IoT Hub and save to Cosmos DB."""
    # Convert to list if single event
    if not isinstance(events, list):
        events = [events]
    
    logger.info(f'Processing {len(events)} telemetry messages from IoT Hub')
    
    for index, event in enumerate(events):
        try:
            # Decode message
            message_data = None
            if hasattr(event, 'get_body'):
                body = event.get_body()
                if isinstance(body, bytes):
                    decoded_string = body.decode('utf-8')
                    message_data = json.loads(decoded_string)
                else:
                    message_data = json.loads(body)
            else:
                # Treat as string
                message_data = json.loads(event)
            
            # Process only system_telemetry messages
            if message_data.get('type') != 'system_telemetry':
                continue
            
            logger.info(f'Telemetry message {index}: {json.dumps(message_data)[:200]}...')
            
            # Get device info (prioritize from message body)
            device_id = message_data.get('device_id', 'unknown')
            module_id = message_data.get('module_id', 'unknown')
            
            # Try to get from system properties if not in message body
            if device_id == 'unknown':
                try:
                    # Get from EventHubEvent system properties
                    if hasattr(event, 'system_properties'):
                        system_props = event.system_properties
                        device_id = system_props.get('iothub-connection-device-id', device_id)
                        module_id = system_props.get('iothub-connection-module-id', module_id)
                        logger.info(f'Device info from system properties: device_id={device_id}, module_id={module_id}')
                except Exception as e:
                    logger.warning(f'Failed to get device info from system properties: {e}')
            
            # Create document for Cosmos DB
            document = {
                'id': str(uuid.uuid4()),
                'deviceId': device_id,
                'moduleId': module_id,
                'type': message_data.get('type'),
                'timestamp': message_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                'diskUsagePercent': message_data.get('disk_usage_percent', 0),
                'receivedAt': datetime.now(timezone.utc).isoformat()
            }
            
            # Add cleanup information if available
            if 'cleanup_performed' in message_data:
                document['cleanupPerformed'] = message_data['cleanup_performed']
                document['diskUsageAfterCleanup'] = message_data.get('disk_usage_after_cleanup', 0)
            
            # Save directly to Cosmos DB
            if telemetry_container:
                try:
                    telemetry_container.create_item(body=document)
                    logger.info(f'Saved telemetry document: id={document["id"]}, '
                               f'disk_usage={document["diskUsagePercent"]}%')
                except Exception as e:
                    logger.error(f'Failed to save telemetry document to Cosmos DB: {e}')
            else:
                logger.error('Cosmos DB telemetry container not initialized')
                
        except Exception as e:
            logger.error(f'Error processing telemetry message {index}: {e}')
            logger.exception(e)
    
    logger.info(f'Completed processing {len(events)} telemetry messages')


@app.function_name("conversation_restorer")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="YOUR_IOT_HUB_NAME",
    connection="EventHubConnectionString",
    consumer_group="conversation-restore-group",
    cardinality="one"
)
def conversation_restorer(event: func.EventHubEvent) -> None:
    """Monitor Module Twin updates and send conversation history on startup notification.
    
    # TODO: Add automatic retry functionality
    # [Mechanism] Combination of timeout-based + one-time check
    # 1. Start 30-second timer after sending conversation_restore
    # 2. Monitor conversation_restore_status reported properties
    #    - success: true → Stop timer, complete
    #    - success: false → Resend immediately
    #    - timeout → Resend (for notification failure)
    # 3. Max 3 retries (exponential backoff: 1s, 2s, 4s)
    # 4. Prevent duplicate execution via device-side one-time check
    # [Benefit] Handles notification failures, ensures reliability and safety
    
    # TODO: Implement conversation_restore deletion feature (added 2025/08/02)
    # - Monitor reported.conversation_restore_processed
    # - Delete desired.conversation_restore after completion confirmation
    # - Currently desired properties remain indefinitely
    """
    try:
        # Get event data
        event_body = event.get_body().decode('utf-8')
        event_data = json.loads(event_body)
        
        # Log all events for debugging
        logger.info(f"conversation_restorer received event: {json.dumps(event_data)[:500]}...")
        
        # Check properties directly for Twin change events
        # Module Twin change events may not have opType
        if "properties" in event_data and "reported" in event_data.get("properties", {}):
            # Check reported properties updates
            twin = event_data.get("properties", {}).get("reported", {})
            startup_info = twin.get("startup", {})
            
            logger.info(f"Twin update detected: reported={bool(twin)}, startup={bool(startup_info)}")
            
            # Get device_id and module_id from startup info
            device_id = startup_info.get("device_id", "PokepalDevice1")
            module_id = startup_info.get("module_id", "voice-conversation")
        else:
            logger.info(f"No reported properties found in event")
            return
        
        logger.info(f"Twin update for {device_id}/{module_id}: reported={bool(twin)}, startup={bool(startup_info)}")
        
        # Check if startup notification
        if not startup_info.get("request_conversation_restore"):
            logger.info("No request_conversation_restore flag found")
            return
            
        logger.info(f"Processing conversation restore for device {device_id}")
        
        # Initialize IoT Hub Registry Manager
        iothub_connection = os.environ["IoTHubConnectionString"]
        registry_manager = IoTHubRegistryManager(iothub_connection)
        
        # Get conversation history (from same Cosmos DB)
        conversations = get_recent_conversations(device_id)
        
        if conversations:
            # Send conversation history via Module Twin
            update_module_twin_with_conversations(
                registry_manager, 
                device_id, 
                module_id, 
                conversations
            )
            logger.info(f"Sent {len(conversations)} conversations to device {device_id}")
        else:
            logger.info(f"No recent conversations found for device {device_id}")
            
    except Exception as e:
        logger.error(f"Error processing conversation restore: {e}")
        logger.exception(e)

def get_recent_conversations(device_id: str) -> List[Dict[str, Any]]:
    """Get conversation history since midnight today (JST based).
    
    NOTE: Similar to MemoryGenerator's get_daily_conversations()
    but kept separate as Azure Functions are deployed independently.
    This gets since JST midnight while MemoryGenerator gets past 24 hours.
    """
    try:
        # Use Cosmos DB connection initialized outside function
        if not conversations_container:
            logger.error("Cosmos DB container not initialized")
            return []
        
        # Get conversations from JST 0:00 (UTC 15:00 = JST 0:00)
        # Previous day's UTC 15:00 is today's JST 0:00
        from datetime import timedelta
        now_utc = datetime.now(timezone.utc)
        # Express JST today's 0:00 in UTC
        jst_today_midnight_utc = now_utc.replace(hour=15, minute=0, second=0, microsecond=0)
        # If current time is before UTC 15:00, use previous day's 15:00
        if now_utc.hour < 15:
            jst_today_midnight_utc = jst_today_midnight_utc - timedelta(days=1)
        
        # Execute query
        query = """
            SELECT 
                c.timestamp,
                c.speaker,
                c.text
            FROM c 
            WHERE c.type = 'conversation'
            AND c.deviceId = @deviceId
            AND c.timestamp >= @sinceTime
            ORDER BY c.timestamp ASC
        """
        
        parameters = [
            {"name": "@deviceId", "value": device_id},
            {"name": "@sinceTime", "value": jst_today_midnight_utc.isoformat()}
        ]
        
        items = list(conversations_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        # Extract only required fields
        conversations = []
        for item in items:
            conversations.append({
                "timestamp": item["timestamp"],
                "speaker": item["speaker"],
                "text": item["text"]
            })
        
        logger.info(f"Retrieved {len(conversations)} conversations since JST midnight ({jst_today_midnight_utc.isoformat()}Z)")
        return conversations
        
    except Exception as e:
        logger.error(f"Failed to get recent conversations: {e}")
        return []

def update_module_twin_with_conversations(
    registry_manager, 
    device_id: str, 
    module_id: str, 
    conversations: List[Dict[str, Any]]
) -> None:
    """Send conversation history to Module Twin."""
    try:
        # Get current Module Twin
        twin = registry_manager.get_module_twin(device_id, module_id)
        
        # Update desired properties
        twin_patch = {
            "properties": {
                "desired": {
                    "conversation_restore": {
                        "messages": conversations,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "count": len(conversations)
                    }
                }
            }
        }
        
        # Update Twin
        registry_manager.update_module_twin(
            device_id,
            module_id,
            twin_patch,
            twin.etag
        )
        
        logger.info(f"Updated Module Twin with {len(conversations)} conversations")
        
    except Exception as e:
        logger.error(f"Failed to update module twin: {e}")
