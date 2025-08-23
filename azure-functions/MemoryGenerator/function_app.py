import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.iot.hub import IoTHubRegistryManager
import openai

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp()


# Production: "0 10 17 * * *" (UTC 17:10 = JST 2:10 AM) 
# Test: "0 10 * * * *" (every hour at 10 minutes)
@app.timer_trigger(schedule="0 10 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=True)
def memory_generator(myTimer: func.TimerRequest) -> None:
    """Main process: Generate daily memory files and distribute to edge devices."""
    try:
        # Get current time and 24 hours ago
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=24)
        logger.info(f"Starting memory generation process (processing conversations from {start_time.strftime('%Y-%m-%d %H:%M')} to {now.strftime('%Y-%m-%d %H:%M')})")
        
        # Get configuration from environment variables
        cosmos_connection = os.environ["CosmosDBConnection"]
        storage_connection = os.environ["StorageConnectionString"]
        iothub_connection = os.environ["IoTHubConnectionString"]
        openai_api_key = os.environ["OPENAI_API_KEY"]
        
        # Initialize OpenAI client
        openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Initialize various clients
        cosmos_client = CosmosClient.from_connection_string(cosmos_connection)
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection)
        registry_manager = IoTHubRegistryManager(iothub_connection)
        
        # Get database and container references
        database = cosmos_client.get_database_client("pokepal-db")
        container = database.get_container_client("conversations")
        
        # Get device list (currently fixed, will get from IoT Hub in future)
        device_ids = ["PokepalDevice1"]  # TODO: Get from registry_manager.get_devices()
        # TODO: user_id support - identify user_id per device
        
        for device_id in device_ids:
            try:
                # 1. Get conversation data from past 24 hours
                conversations = get_daily_conversations(container, device_id, start_time, now)
                
                # 2. Generate memory file (with or without conversations)
                memory_data = generate_memory(conversations, device_id, start_time, now, openai_client, blob_service_client)
                
                # 3. Save to Blob Storage
                blob_url, sas_token = save_to_blob(blob_service_client, memory_data, device_id, start_time, now)
                
                # 4. Update Module Twin
                update_module_twin(registry_manager, device_id, blob_url, sas_token)
                
                logger.info(f"Memory generation completed for device {device_id}")
                
            except Exception as e:
                logger.error(f"Error processing device {device_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in memory generation process: {e}")
        raise

def get_daily_conversations(container, device_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """Get conversation data for specified period.
    
    NOTE: Similar to ConversationLogger's get_recent_conversations()
    but kept separate as Azure Functions are deployed independently.
    This gets past 24 hours while ConversationLogger gets since JST midnight.
    """
    start_date = start_time
    end_date = end_time
    
    query = """
        SELECT 
            c.id,
            c.timestamp,
            c.type,
            c.speaker,
            c.text,
            c.rawData
        FROM c 
        WHERE c.type = 'conversation'
        AND c.deviceId = @deviceId
        AND c.timestamp >= @startDate 
        AND c.timestamp < @endDate 
        ORDER BY c.timestamp ASC
    """
    
    parameters = [
        {"name": "@deviceId", "value": device_id},
        {"name": "@startDate", "value": start_date.isoformat()},
        {"name": "@endDate", "value": end_date.isoformat()}
    ]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    return items

def get_previous_memory(blob_service_client, device_id: str, end_time: datetime) -> Optional[Dict[str, Any]]:
    """Get the most recent memory file from past 7 days."""
    try:
        container_client = blob_service_client.get_container_client("memory-files")
        
        for days_back in range(1, 8):  # Search from 1-7 days ago
            check_date = end_time - timedelta(days=days_back)
            blob_name = f"{device_id}/memory_{check_date.strftime('%Y%m%d')}.json"
            
            try:
                blob_client = container_client.get_blob_client(blob_name)
                blob_data = blob_client.download_blob().readall()
                previous_memory = json.loads(blob_data.decode('utf-8'))
                logger.info(f"Found past memory: {blob_name}")
                return previous_memory.get("memory")
            except Exception:
                continue  # If file doesn't exist, check next day
        
        return None
    except Exception as e:
        logger.warning(f"Failed to get previous memory: {e}")
        return None

def generate_memory(conversations: List[Dict[str, Any]], device_id: str, start_time: datetime, end_time: datetime, openai_client, blob_service_client) -> Dict[str, Any]:
    """Generate memory file from conversation data with past memory context."""
    
    # Get previous memory for context (last 7 days)
    previous_memory = get_previous_memory(blob_service_client, device_id, end_time)
    
    # Create conversation text in chronological order (no pairing needed)
    if conversations:
        conversation_text = "\n".join([
            f"[{item['timestamp']}] {item['speaker'].capitalize()}: {item['text']}"
            for item in conversations
        ])
    else:
        conversation_text = "No conversations recorded during this period."
    
    # Include previous memory context if available
    previous_context = ""
    if previous_memory:
        previous_context = f"""
Previous Memory Context (inherit and update as needed):
{{
    "short_term_memory": "{previous_memory.get('short_term_memory', 'No previous memory')}",
    "medium_term_memory": {{
        "keywords": {json.dumps(previous_memory.get('medium_term_memory', {}).get('keywords', []), ensure_ascii=False)},
        "events": {json.dumps(previous_memory.get('medium_term_memory', {}).get('events', []), ensure_ascii=False)}
    }},
    "user_context": {{
        "preferences": {json.dumps(previous_memory.get('user_context', {}).get('preferences', []), ensure_ascii=False)},
        "concerns": {json.dumps(previous_memory.get('user_context', {}).get('concerns', []), ensure_ascii=False)},
        "routine": {json.dumps(previous_memory.get('user_context', {}).get('routine', []), ensure_ascii=False)}
    }}
}}
"""
    
    prompt = f"""Below is the conversation record from {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}.
Analyze this conversation and extract important information to create a memory summary for the AI assistant.
{previous_context}
Conversation Record:
{conversation_text}

Generate a JSON response with the following structure:
{{
    "short_term_memory": "A concise summary of the most recent conversations and key topics discussed. Include important context, emotional states, and immediate concerns. (max 500 characters)",
    "medium_term_memory": {{
        "keywords": ["Important topics, names, places, or concepts mentioned (up to 10 items)"],
        "events": ["Significant events, plans, or activities discussed (up to 5 items with brief descriptions)"]
    }},
    "user_context": {{
        "preferences": ["Things the user likes, dislikes, or has shown interest in"],
        "concerns": ["Current worries, problems, or topics the user is focused on"],
        "routine": ["Regular activities, habits, or patterns observed in the conversation"]
    }}
}}

Focus on information that would help the AI assistant provide more personalized and contextually relevant responses in future conversations."""
    
    # Use same defaults as EdgeSolution/modules/voice_conversation_v2/infrastructure/config/defaults.json
    # llm.model: "gpt-4o-mini"
    # TODO: Consider synchronizing configuration between Azure Functions and IoT Edge module
    #       Options:
    #       1. Keep environment variables with matching defaults (current approach)
    #       2. Use shared Azure Blob Storage for configuration
    #       3. Auto-sync defaults.json values to Azure Functions env vars during CI/CD
    model_name = os.environ.get("MEMORY_GENERATION_MODEL", "gpt-4o-mini")
    
    # Default system prompt for memory generation (different from conversation prompt)
    system_prompt = os.environ.get("MEMORY_SYSTEM_PROMPT", 
                                   "You are an assistant that extracts important information from conversations and generates structured memory data.")
    
    try:
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        memory_content = json.loads(response.choices[0].message.content)
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        memory_content = {
            "short_term_memory": "Memory generation failed",
            "medium_term_memory": {"keywords": [], "events": []},
            "user_context": {"preferences": [], "concerns": [], "routine": []}
        }
    
    # Structure memory data
    return {
        "device_id": device_id,
        "date": end_time.strftime('%Y-%m-%d'),  # Date format for filename
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conversation_count": len(conversations),
        "memory": memory_content
    }

def save_to_blob(blob_service_client, memory_data: Dict[str, Any], device_id: str, start_time: datetime, end_time: datetime) -> tuple:
    """Save memory data to Blob Storage and return URL with SAS token."""
    container_name = "memory-files"
    # Use execution date for filename (compatible with hourly execution date progression)
    blob_name = f"{device_id}/memory_{end_time.strftime('%Y%m%d')}.json"
    
    # Get container client
    container_client = blob_service_client.get_container_client(container_name)
    
    # Create container if it doesn't exist
    try:
        container_client.create_container()
    except:
        pass  # Skip if already exists
    
    # Upload to Blob
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        json.dumps(memory_data, ensure_ascii=False, indent=2),
        overwrite=True
    )
    
    # Generate SAS token (valid for 10 minutes before and after = 0-20 minutes)
    # Adjust current time to 10-minute window start (e.g., 9:14 → 9:10)
    now = datetime.now(timezone.utc)
    start_of_window = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
    
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        start=start_of_window - timedelta(minutes=10),  # Valid from 10 minutes before
        expiry=start_of_window + timedelta(minutes=10)  # Valid until 10 minutes after
    )
    
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}"
    
    return blob_url, sas_token

def update_module_twin(registry_manager, device_id: str, blob_url: str, sas_token: str) -> None:
    """Update Module Twin to notify memory file update."""
    module_id = "voice-conversation"
    
    # Get current Module Twin
    twin = registry_manager.get_module_twin(device_id, module_id)
    
    # Update desired properties
    twin_patch = {
        "properties": {
            "desired": {
                "memory_update": {
                    "url": blob_url,
                    "sas": sas_token,
                    "timestamp": datetime.now(timezone.utc).isoformat()
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
    
    logger.info(f"Module Twin update completed: {device_id}/{module_id}")
