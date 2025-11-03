"""
UserAPI Client - For managing user tasks via UserAPI

Provides functionality to create, update, and delete proactive tasks
by calling the UserAPI Azure Function.
"""
import httpx
import logging
import time as time_module
from typing import Optional, Dict, Any


class UserAPIClient:
    """Client for UserAPI Azure Function"""

    def __init__(self, base_url: str, user_id: str):
        """
        Initialize UserAPI Client

        Args:
            base_url: UserAPI base URL (e.g., https://pokepal-user-api.azurewebsites.net)
            user_id: User ID for this device
        """
        self._base_url = base_url.rstrip('/')
        self._user_id = user_id
        self._logger = logging.getLogger(__name__)
        self._timeout = httpx.Timeout(10.0, connect=5.0)

    async def create_task(self, title: str, time: str, enabled: bool = True) -> bool:
        """
        Create a new proactive task

        Args:
            title: Task title (e.g., "薬を飲む")
            time: Time in HH:MM format (e.g., "08:00")
            enabled: Whether the task is enabled

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current user data (by device ID)
            user = await self._get_user()
            if not user:
                self._logger.error("Failed to get user data")
                return False

            # Extract actual user ID
            user_id = user.get("id")
            if not user_id:
                self._logger.error("User ID not found in user data")
                return False

            # Get existing tasks
            tasks = user.get("proactiveTasks", [])

            # Create new task
            new_task = {
                "id": f"task_{int(time_module.time() * 1000)}",
                "title": title,
                "time": time,
                "enabled": enabled
            }

            # Add to task list
            tasks.append(new_task)

            # Update user via UserAPI (using actual user ID)
            success = await self._update_user(user_id, {"proactiveTasks": tasks})

            if success:
                self._logger.info("Task created successfully: %s at %s", title, time)
            else:
                self._logger.error("Failed to update user with new task")

            return success

        except Exception as e:
            self._logger.error("Failed to create task: %s", e, exc_info=True)
            return False

    async def _get_user(self) -> Optional[Dict[str, Any]]:
        """
        Get user data from UserAPI by device ID

        Returns:
            User data dict, or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/api/users/by-device/{self._user_id}")
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            self._logger.error("HTTP error getting user: %s (status: %s)", e, e.response.status_code)
            return None
        except httpx.RequestError as e:
            self._logger.error("Request error getting user: %s", e)
            return None
        except Exception as e:
            self._logger.error("Unexpected error getting user: %s", e, exc_info=True)
            return None

    async def _update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user data via UserAPI

        Args:
            user_id: Actual user ID (not device ID)
            updates: Fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.put(
                    f"{self._base_url}/api/users/{user_id}",
                    json=updates
                )
                response.raise_for_status()
                self._logger.info("User updated successfully")
                return True

        except httpx.HTTPStatusError as e:
            self._logger.error("HTTP error updating user: %s (status: %s)", e, e.response.status_code)
            if e.response.status_code < 500:
                # Client error - log response body for debugging
                self._logger.error("Response body: %s", e.response.text)
            return False
        except httpx.RequestError as e:
            self._logger.error("Request error updating user: %s", e)
            return False
        except Exception as e:
            self._logger.error("Unexpected error updating user: %s", e, exc_info=True)
            return False
