"""User API for PokePal Admin Dashboard."""
import os
import json
import logging
from datetime import datetime, timezone
import azure.functions as func
from azure.cosmos import CosmosClient, exceptions
from azure.core.exceptions import AzureError

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp()

# Initialize Cosmos DB connection
cosmos_connection = os.environ.get("CosmosDBConnection")
cosmos_client = None
users_container = None

if cosmos_connection:
    try:
        cosmos_client = CosmosClient.from_connection_string(cosmos_connection)
        database = cosmos_client.get_database_client("pokepal-db")
        database.read()  # Verify connection
        users_container = database.get_container_client("users")
        logger.info("Cosmos DB clients initialized successfully")
    except AzureError as e:
        logger.error("Azure service error initializing Cosmos DB: %s", e)
    except ValueError as e:
        logger.error("Invalid connection string format: %s", e)
    except Exception as e:
        logger.error("Unexpected error initializing Cosmos DB: %s", e)
else:
    logger.warning("CosmosDBConnection not configured - running without database")


@app.route(route="users", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_users(req: func.HttpRequest) -> func.HttpResponse:
    """List all users.

    Returns:
        JSON response with user list
    """
    if not users_container:
        logger.warning("Database not available")
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    try:
        # Query all active users (soft delete: filter out isActive = false)
        query = "SELECT * FROM c WHERE c.isActive = true"
        items = list(users_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        return func.HttpResponse(
            json.dumps({"users": items}),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logger.error("Failed to get users: %s", e)
        return func.HttpResponse(
            json.dumps({"error": "Failed to retrieve users"}),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="users/{id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_user_by_id(req: func.HttpRequest) -> func.HttpResponse:
    """Get a specific user by ID.

    Args:
        id: User ID from route parameter

    Returns:
        JSON response with user data
    """
    if not users_container:
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    user_id = req.route_params.get('id')
    if not user_id:
        return func.HttpResponse(
            json.dumps({"error": "User ID is required"}),
            mimetype="application/json",
            status_code=400
        )

    try:
        # Read user by ID
        user = users_container.read_item(item=user_id, partition_key=user_id)
        return func.HttpResponse(
            json.dumps(user),
            mimetype="application/json",
            status_code=200
        )
    except exceptions.CosmosResourceNotFoundError:
        return func.HttpResponse(
            json.dumps({"error": "User not found"}),
            mimetype="application/json",
            status_code=404
        )
    except Exception as e:
        logger.error("Failed to get user %s: %s", user_id, e)
        return func.HttpResponse(
            json.dumps({"error": "Failed to retrieve user"}),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="users", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName="deviceStatus",
    connection="AzureSignalRConnectionString"
)
def create_user(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """Create a new user.

    Request body:
        JSON with user data (id, name, nickname, roomNumber, deviceId, proactiveTasks, notes)

    Returns:
        JSON response with created user data
    """
    if not users_container:
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            mimetype="application/json",
            status_code=400
        )

    # Validate required fields
    required_fields = ["id", "name", "nickname", "deviceId"]
    for field in required_fields:
        if field not in req_body:
            return func.HttpResponse(
                json.dumps({"error": f"Missing required field: {field}"}),
                mimetype="application/json",
                status_code=400
            )

    # Add timestamp and active status
    req_body["createdAt"] = datetime.now(timezone.utc).isoformat()
    req_body["isActive"] = True

    # Set defaults for optional fields
    if "roomNumber" not in req_body:
        req_body["roomNumber"] = ""
    if "proactiveTasks" not in req_body:
        req_body["proactiveTasks"] = []
    if "notes" not in req_body:
        req_body["notes"] = ""

    try:
        # Create user in Cosmos DB
        created_user = users_container.create_item(body=req_body)
        logger.info("User created: %s", req_body["id"])

        # Send SignalR notification
        signalr_message = {
            'target': 'userUpdated',
            'arguments': [created_user]
        }
        signalRMessages.set(json.dumps(signalr_message))
        logger.info("Sent SignalR notification for user creation: %s", req_body["id"])

        return func.HttpResponse(
            json.dumps(created_user),
            mimetype="application/json",
            status_code=201
        )
    except exceptions.CosmosResourceExistsError:
        return func.HttpResponse(
            json.dumps({"error": "User already exists"}),
            mimetype="application/json",
            status_code=409
        )
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        return func.HttpResponse(
            json.dumps({"error": "Failed to create user"}),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="users/{id}", methods=["PUT"], auth_level=func.AuthLevel.ANONYMOUS)
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName="deviceStatus",
    connection="AzureSignalRConnectionString"
)
def update_user(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """Update an existing user.

    Args:
        id: User ID from route parameter

    Request body:
        JSON with updated user data

    Returns:
        JSON response with updated user data
    """
    if not users_container:
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    user_id = req.route_params.get('id')
    if not user_id:
        return func.HttpResponse(
            json.dumps({"error": "User ID is required"}),
            mimetype="application/json",
            status_code=400
        )

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON"}),
            mimetype="application/json",
            status_code=400
        )

    try:
        # Read existing user
        existing_user = users_container.read_item(item=user_id, partition_key=user_id)

        # Merge update with existing data (partial update)
        # This preserves fields not included in the request (e.g., proactiveTasks)
        # Protected fields: id, createdAt, deviceId, name, isActive
        for key, value in req_body.items():
            if key not in ["id", "createdAt", "deviceId", "name", "isActive"]:
                existing_user[key] = value

        existing_user["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Replace user in Cosmos DB
        updated_user = users_container.replace_item(item=user_id, body=existing_user)
        logger.info("User updated: %s", user_id)

        # Send SignalR notification
        signalr_message = {
            'target': 'userUpdated',
            'arguments': [updated_user]
        }
        signalRMessages.set(json.dumps(signalr_message))
        logger.info("Sent SignalR notification for user update: %s", user_id)

        return func.HttpResponse(
            json.dumps(updated_user),
            mimetype="application/json",
            status_code=200
        )
    except exceptions.CosmosResourceNotFoundError:
        return func.HttpResponse(
            json.dumps({"error": "User not found"}),
            mimetype="application/json",
            status_code=404
        )
    except Exception as e:
        logger.error("Failed to update user %s: %s", user_id, e)
        return func.HttpResponse(
            json.dumps({"error": "Failed to update user"}),
            mimetype="application/json",
            status_code=500
        )


@app.route(route="users/{id}", methods=["DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
@app.generic_output_binding(
    arg_name="signalRMessages",
    type="signalR",
    hubName="deviceStatus",
    connection="AzureSignalRConnectionString"
)
def delete_user(req: func.HttpRequest, signalRMessages: func.Out[str]) -> func.HttpResponse:
    """Soft delete a user (set isActive to false).

    Args:
        id: User ID from route parameter

    Returns:
        JSON response confirming soft deletion
    """
    if not users_container:
        return func.HttpResponse(
            json.dumps({"error": "Database not available"}),
            mimetype="application/json",
            status_code=503
        )

    user_id = req.route_params.get('id')
    if not user_id:
        return func.HttpResponse(
            json.dumps({"error": "User ID is required"}),
            mimetype="application/json",
            status_code=400
        )

    try:
        # Read existing user
        existing_user = users_container.read_item(item=user_id, partition_key=user_id)

        # Soft delete: set isActive to false
        existing_user["isActive"] = False
        existing_user["deletedAt"] = datetime.now(timezone.utc).isoformat()

        # Update user in Cosmos DB
        updated_user = users_container.replace_item(item=user_id, body=existing_user)
        logger.info("User soft deleted: %s", user_id)

        # Send SignalR notification
        signalr_message = {
            'target': 'userDeleted',
            'arguments': [{'id': user_id}]
        }
        signalRMessages.set(json.dumps(signalr_message))
        logger.info("Sent SignalR notification for user deletion: %s", user_id)

        return func.HttpResponse(
            json.dumps({"message": "User deleted successfully"}),
            mimetype="application/json",
            status_code=200
        )
    except exceptions.CosmosResourceNotFoundError:
        return func.HttpResponse(
            json.dumps({"error": "User not found"}),
            mimetype="application/json",
            status_code=404
        )
    except Exception as e:
        logger.error("Failed to delete user %s: %s", user_id, e)
        return func.HttpResponse(
            json.dumps({"error": "Failed to delete user"}),
            mimetype="application/json",
            status_code=500
        )
