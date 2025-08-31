"""Tests for SignalHandler."""
import signal
import unittest
from unittest.mock import MagicMock, patch
from adapters.input.signal_handler import SignalHandler


class TestSignalHandler(unittest.TestCase):
    """Test class for SignalHandler."""
    
    def setUp(self):
        """Test setup."""
        self.handler = SignalHandler()
        self.callback = MagicMock()
    
    def tearDown(self):
        """Test cleanup."""
        # Restore handlers
        self.handler.restore()
    
    def test_register(self):
        """Test callback registration."""
        self.handler.register(signal.SIGTERM, self.callback)
        
        self.assertIn(signal.SIGTERM, self.handler.callbacks)
        self.assertEqual(self.handler.callbacks[signal.SIGTERM], self.callback)
    
    def test_setup_stores_original_handlers(self):
        """Test that setup() stores original handlers."""
        original_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, original_handler)  # Restore
        
        self.handler.register(signal.SIGTERM, self.callback)
        self.handler.setup()
        
        self.assertIn(signal.SIGTERM, self.handler.original_handlers)
        self.assertEqual(self.handler.original_handlers[signal.SIGTERM], original_handler)
    
    def test_restore(self):
        """Test that restore() restores original handlers."""
        original_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, original_handler)  # Restore
        
        self.handler.register(signal.SIGTERM, self.callback)
        self.handler.setup()
        self.handler.restore()
        
        # original_handlers is cleared
        self.assertEqual(len(self.handler.original_handlers), 0)
    
    def test_handle_signal_calls_callback(self):
        """Test that signal handling calls callback."""
        self.handler.register(signal.SIGTERM, self.callback)
        
        # Call _handle_signal directly
        self.handler._handle_signal(signal.SIGTERM, None)
        
        self.callback.assert_called_once_with(signal.SIGTERM)
        self.assertTrue(self.handler._shutdown_requested)
    
    def test_handle_signal_with_error(self):
        """Test when callback raises an error."""
        error_callback = MagicMock(side_effect=Exception("Test error"))
        self.handler.register(signal.SIGTERM, error_callback)
        
        # No crash even if error occurs
        self.handler._handle_signal(signal.SIGTERM, None)
        
        error_callback.assert_called_once_with(signal.SIGTERM)
        self.assertTrue(self.handler._shutdown_requested)
    
    def test_double_signal_handling(self):
        """Test handling of double signal reception."""
        self.handler.register(signal.SIGTERM, self.callback)
        
        # First signal
        self.handler._handle_signal(signal.SIGTERM, None)
        self.assertEqual(self.callback.call_count, 1)
        
        # Second signal (force quit)
        with patch.object(self.handler, 'restore') as mock_restore:
            self.handler._handle_signal(signal.SIGTERM, None)
            mock_restore.assert_called_once()
            # Callback is not called again
            self.assertEqual(self.callback.call_count, 1)
    
    def test_is_shutdown_requested(self):
        """Test shutdown request status check."""
        self.assertFalse(self.handler._shutdown_requested)
        
        self.handler.register(signal.SIGTERM, self.callback)
        self.handler._handle_signal(signal.SIGTERM, None)
        
        self.assertTrue(self.handler._shutdown_requested)
    
    def test_multiple_signals(self):
        """Test that multiple signals can be registered."""
        callback2 = MagicMock()
        
        self.handler.register(signal.SIGTERM, self.callback)
        self.handler.register(signal.SIGINT, callback2)
        self.handler.setup()
        
        self.assertIn(signal.SIGTERM, self.handler.callbacks)
        self.assertIn(signal.SIGINT, self.handler.callbacks)
        self.assertIn(signal.SIGTERM, self.handler.original_handlers)
        self.assertIn(signal.SIGINT, self.handler.original_handlers)


if __name__ == '__main__':
    unittest.main()