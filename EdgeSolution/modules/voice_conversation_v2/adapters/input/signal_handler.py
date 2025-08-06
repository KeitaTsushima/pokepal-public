"""
System Signal Processing Adapter

Receives system signals like SIGTERM and SIGINT,
and executes appropriate callbacks.

TODO: Signal Handler Quality Improvements (Low Priority)
1. Signal masking support (prevent interruption during high-priority signal processing)
2. Audio processing interruption signal (process_conversation interruption support)
3. Configuration externalization (timeout values, force exit flags)
"""
import signal
import logging
import threading
import os
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)


class SignalHandler:
    """Adapter for processing system signals"""
    
    DEFAULT_GRACEFUL_TIMEOUT = 30

    def __init__(self):
        self.callbacks: Dict[int, Callable] = {}
        self.original_handlers: Dict[int, Any] = {}
        self._shutdown_requested = False
        
        self._signal_names = {
            signal.SIGTERM: "SIGTERM",
            signal.SIGINT: "SIGINT"
        }

    def register(self, signum: int, callback: Callable) -> None:
        self.callbacks[signum] = callback
        signal_name = self._get_signal_name(signum)
        logger.info(f"Registered callback for signal {signal_name} ({signum})")

    def setup(self) -> None:
        for signum in self.callbacks:
            try:
                original_handler = signal.signal(signum, self._handle_signal)
                self.original_handlers[signum] = original_handler
                signal_name = self._get_signal_name(signum)
                logger.info(f"Setup handler for signal {signal_name} ({signum})")
            except (OSError, ValueError) as e:
                signal_name = self._get_signal_name(signum)
                logger.error(f"Failed to setup handler for signal {signal_name}: {e}")

    def restore(self) -> None:
        for signum, original_handler in self.original_handlers.items():
            try:
                signal.signal(signum, original_handler)
                signal_name = self._get_signal_name(signum)
                logger.info(f"Restored original handler for signal {signal_name} ({signum})")
            except (OSError, ValueError) as e:
                signal_name = self._get_signal_name(signum)
                logger.error(f"Failed to restore handler for signal {signal_name}: {e}")
        self.original_handlers.clear()

    def _handle_signal(self, signum: int, frame: Any) -> None:
        signal_name = self._get_signal_name(signum)
        
        if self._shutdown_requested:
            logger.warning(f"Signal {signal_name} received again. Force exiting...")
            self._force_exit(signum, frame)
            return

        self._shutdown_requested = True
        logger.info(f"Signal {signal_name} received. Starting shutdown process...")

        self._run_graceful_shutdown(signum)

    def _execute_callback(self, signum: int) -> None:
        if signum not in self.callbacks:
            logger.warning(f"No callback registered for signal {signum}")
            return
            
        try:
            self.callbacks[signum](signum)
            logger.info(f"Signal callback executed successfully for {self._get_signal_name(signum)}")
        except Exception as e:
            signal_name = self._get_signal_name(signum)
            logger.error(f"Error in signal callback for {signal_name}: {e}", exc_info=True)

    def _run_graceful_shutdown(self, signum: int, timeout: int = DEFAULT_GRACEFUL_TIMEOUT) -> None:
        signal_name = self._get_signal_name(signum)
        logger.info(f"Starting graceful shutdown with {timeout}s timeout")
        
        thread = threading.Thread(
            target=lambda: self._execute_callback(signum),
            name=f"GracefulShutdown-{signal_name}",
            daemon=True
        )
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            logger.warning(f"Graceful shutdown timeout ({timeout}s), forcing exit...")
            self._force_exit(signum, None)
        else:
            logger.info("Graceful shutdown completed")

    def _force_exit(self, signum: int, frame: Any) -> None:
        logger.error("Force exit: graceful shutdown failed")        
        self.restore()
        os._exit(1)

    def _get_signal_name(self, signum: int) -> str:
        return self._signal_names.get(signum, "UNKNOWN")
