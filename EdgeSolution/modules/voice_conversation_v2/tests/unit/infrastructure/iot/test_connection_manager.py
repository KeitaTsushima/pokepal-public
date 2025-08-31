"""
Unit tests for IoTConnectionManager

Tests IoT Hub connection management without requiring actual IoT Hub environment.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import pytest

from infrastructure.iot.connection_manager import IoTConnectionManager


class TestIoTConnectionManager(unittest.TestCase):
    """Test cases for IoTConnectionManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.connection_manager = IoTConnectionManager()
    
    def test_initial_state(self):
        """Test initial state of connection manager"""
        self.assertFalse(self.connection_manager.is_connected)
        self.assertIsNone(self.connection_manager.module_client)
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_initialize_client_success(self, mock_iot_client_class):
        """Test successful client initialization"""
        # Setup mock
        mock_client = Mock()
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        
        # Execute
        result = self.connection_manager.initialize_client()
        
        # Verify
        self.assertTrue(result)
        self.assertEqual(self.connection_manager.module_client, mock_client)
        mock_iot_client_class.create_from_edge_environment.assert_called_once()
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_initialize_client_failure(self, mock_iot_client_class):
        """Test client initialization failure"""
        # Setup mock to raise exception
        mock_iot_client_class.create_from_edge_environment.side_effect = Exception("IoT Hub unavailable")
        
        # Execute
        result = self.connection_manager.initialize_client()
        
        # Verify
        self.assertFalse(result)
        self.assertIsNone(self.connection_manager.module_client)
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_connect_success(self, mock_iot_client_class):
        """Test successful connection"""
        # Setup mock
        mock_client = Mock()
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        
        # Execute
        result = self.connection_manager.connect()
        
        # Verify
        self.assertTrue(result)
        self.assertTrue(self.connection_manager.is_connected)
        mock_client.connect.assert_called_once()
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_connect_failure(self, mock_iot_client_class):
        """Test connection failure"""
        # Setup mock
        mock_client = Mock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        
        # Execute
        result = self.connection_manager.connect()
        
        # Verify
        self.assertFalse(result)
        self.assertFalse(self.connection_manager.is_connected)
        self.assertIsNone(self.connection_manager.module_client)
    
    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected"""
        # Should not raise any exception
        self.connection_manager.disconnect()
        self.assertFalse(self.connection_manager.is_connected)
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_disconnect_success(self, mock_iot_client_class):
        """Test successful disconnect"""
        # Setup: establish connection first
        mock_client = Mock()
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        self.connection_manager.connect()
        
        # Execute
        self.connection_manager.disconnect()
        
        # Verify
        self.assertFalse(self.connection_manager.is_connected)
        self.assertIsNone(self.connection_manager.module_client)
        mock_client.disconnect.assert_called_once()
    
    def test_get_client_when_not_connected(self):
        """Test getting client when not connected"""
        result = self.connection_manager.get_client()
        self.assertIsNone(result)
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_get_client_when_connected(self, mock_iot_client_class):
        """Test getting client when connected"""
        # Setup: establish connection
        mock_client = Mock()
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        self.connection_manager.connect()
        
        # Execute
        result = self.connection_manager.get_client()
        
        # Verify
        self.assertEqual(result, mock_client)
    
    @patch('infrastructure.iot.connection_manager.IoTHubModuleClient')
    def test_ensure_connection_when_connected(self, mock_iot_client_class):
        """Test ensure_connection when already connected"""
        # Setup: establish connection
        mock_client = Mock()
        mock_iot_client_class.create_from_edge_environment.return_value = mock_client
        self.connection_manager.connect()
        
        # Execute
        result = self.connection_manager.ensure_connection()
        
        # Verify
        self.assertTrue(result)
        # connect() should not be called again
        mock_client.connect.assert_called_once()  # Only from initial setup
    
    def test_ensure_connection_when_not_connected(self):
        """Test ensure_connection when not connected"""
        with patch.object(self.connection_manager, 'connect', return_value=True) as mock_connect:
            result = self.connection_manager.ensure_connection()
            
            self.assertTrue(result)
            mock_connect.assert_called_once()
    
    def test_cleanup(self):
        """Test cleanup functionality"""
        with patch.object(self.connection_manager, 'disconnect') as mock_disconnect:
            self.connection_manager.cleanup()
            mock_disconnect.assert_called_once()


if __name__ == '__main__':
    unittest.main()