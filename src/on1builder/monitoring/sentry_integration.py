"""
Sentry Integration for ON1Builder MEV Bot.

Provides error tracking, performance monitoring, and alerting.
"""

import logging
import os
import sys
from typing import Dict, Any, Optional
from functools import wraps

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None

logger = logging.getLogger(__name__)

class SentryMonitor:
    """
    Sentry integration for error tracking and monitoring.
    """
    
    def __init__(self, dsn: Optional[str] = None, environment: str = "development"):
        self.dsn = dsn or os.getenv("SENTRY_DSN")
        self.environment = environment
        self.initialized = False
        
        if SENTRY_AVAILABLE and self.dsn:
            self._initialize_sentry()
        else:
            logger.warning("Sentry not available or DSN not configured")
    
    def _initialize_sentry(self):
        """Initialize Sentry SDK."""
        try:
            # Configure Sentry
            sentry_sdk.init(
                dsn=self.dsn,
                environment=self.environment,
                traces_sample_rate=0.1,  # Sample 10% of transactions
                profiles_sample_rate=0.1,  # Sample 10% of profiles
                
                # Integrations
                integrations=[
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR
                    ),
                    AsyncioIntegration(),
                    AioHttpIntegration(),
                ],
                
                # Custom tags
                default_tags={
                    "bot_version": "1.0.0",
                    "component": "mev_bot"
                },
                
                # Before send filter
                before_send=self._before_send_filter,
                
                # Before breadcrumb filter
                before_breadcrumb=self._before_breadcrumb_filter
            )
            
            self.initialized = True
            logger.info("Sentry initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")
    
    def _before_send_filter(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter events before sending to Sentry."""
        try:
            # Don't send events for certain error types
            if 'exception' in event:
                exception = event['exception']
                if exception and 'values' in exception:
                    for value in exception['values']:
                        if 'type' in value:
                            error_type = value['type']
                            
                            # Filter out certain error types
                            if error_type in [
                                'ConnectionError',
                                'TimeoutError',
                                'RateLimitError'
                            ]:
                                return None
            
            # Add custom context
            event.setdefault('tags', {}).update({
                'bot_component': 'mev_bot',
                'error_category': self._categorize_error(event)
            })
            
            return event
            
        except Exception as e:
            logger.error(f"Error in Sentry before_send filter: {e}")
            return event
    
    def _before_breadcrumb_filter(self, breadcrumb: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter breadcrumbs before sending to Sentry."""
        try:
            # Don't send breadcrumbs for certain categories
            if breadcrumb.get('category') in [
                'http',
                'console',
                'navigation'
            ]:
                return None
            
            # Add custom context to breadcrumbs
            breadcrumb.setdefault('data', {}).update({
                'bot_context': 'mev_operation'
            })
            
            return breadcrumb
            
        except Exception as e:
            logger.error(f"Error in Sentry before_breadcrumb filter: {e}")
            return breadcrumb
    
    def _categorize_error(self, event: Dict[str, Any]) -> str:
        """Categorize errors for better organization."""
        try:
            if 'exception' in event and event['exception']:
                exception = event['exception']
                if 'values' in exception and exception['values']:
                    error_type = exception['values'][0].get('type', '')
                    
                    if 'Connection' in error_type or 'Timeout' in error_type:
                        return 'network_error'
                    elif 'Validation' in error_type or 'Value' in error_type:
                        return 'validation_error'
                    elif 'Gas' in error_type or 'Transaction' in error_type:
                        return 'transaction_error'
                    elif 'Flashbots' in error_type or 'Bundle' in error_type:
                        return 'flashbots_error'
                    else:
                        return 'general_error'
            
            return 'unknown_error'
            
        except Exception:
            return 'unknown_error'
    
    def capture_exception(self, exception: Exception, context: Optional[Dict[str, Any]] = None):
        """Capture an exception with context."""
        if not self.initialized:
            logger.error(f"Exception not captured (Sentry not initialized): {exception}")
            return
        
        try:
            if context:
                sentry_sdk.set_context("mev_bot", context)
            
            sentry_sdk.capture_exception(exception)
            
        except Exception as e:
            logger.error(f"Failed to capture exception in Sentry: {e}")
    
    def capture_message(self, message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
        """Capture a message with context."""
        if not self.initialized:
            logger.log(getattr(logging, level.upper()), message)
            return
        
        try:
            if context:
                sentry_sdk.set_context("mev_bot", context)
            
            sentry_sdk.capture_message(message, level=level)
            
        except Exception as e:
            logger.error(f"Failed to capture message in Sentry: {e}")
    
    def set_user(self, user_id: str, user_data: Optional[Dict[str, Any]] = None):
        """Set user context for tracking."""
        if not self.initialized:
            return
        
        try:
            sentry_sdk.set_user({
                "id": user_id,
                **(user_data or {})
            })
            
        except Exception as e:
            logger.error(f"Failed to set user in Sentry: {e}")
    
    def set_tag(self, key: str, value: str):
        """Set a tag for tracking."""
        if not self.initialized:
            return
        
        try:
            sentry_sdk.set_tag(key, value)
            
        except Exception as e:
            logger.error(f"Failed to set tag in Sentry: {e}")
    
    def set_context(self, name: str, data: Dict[str, Any]):
        """Set context data for tracking."""
        if not self.initialized:
            return
        
        try:
            sentry_sdk.set_context(name, data)
            
        except Exception as e:
            logger.error(f"Failed to set context in Sentry: {e}")
    
    def start_transaction(self, name: str, operation: str = "mev.operation") -> Optional[Any]:
        """Start a performance transaction."""
        if not self.initialized:
            return None
        
        try:
            return sentry_sdk.start_transaction(
                name=name,
                op=operation
            )
        except Exception as e:
            logger.error(f"Failed to start Sentry transaction: {e}")
            return None
    
    def add_breadcrumb(self, message: str, category: str = "mev", level: str = "info", data: Optional[Dict[str, Any]] = None):
        """Add a breadcrumb for tracking."""
        if not self.initialized:
            return
        
        try:
            sentry_sdk.add_breadcrumb(
                message=message,
                category=category,
                level=level,
                data=data or {}
            )
            
        except Exception as e:
            logger.error(f"Failed to add breadcrumb in Sentry: {e}")
    
    def monitor_function(self, name: Optional[str] = None):
        """Decorator to monitor function performance and errors."""
        def decorator(func):
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.initialized:
                    return func(*args, **kwargs)
                
                transaction_name = name or f"{func.__module__}.{func.__name__}"
                
                with sentry_sdk.start_transaction(
                    name=transaction_name,
                    op="mev.function"
                ) as transaction:
                    try:
                        result = func(*args, **kwargs)
                        transaction.set_status("ok")
                        return result
                    except Exception as e:
                        transaction.set_status("internal_error")
                        self.capture_exception(e, {
                            "function": func.__name__,
                            "module": func.__module__,
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys())
                        })
                        raise
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.initialized:
                    return await func(*args, **kwargs)
                
                transaction_name = name or f"{func.__module__}.{func.__name__}"
                
                with sentry_sdk.start_transaction(
                    name=transaction_name,
                    op="mev.function"
                ) as transaction:
                    try:
                        result = await func(*args, **kwargs)
                        transaction.set_status("ok")
                        return result
                    except Exception as e:
                        transaction.set_status("internal_error")
                        self.capture_exception(e, {
                            "function": func.__name__,
                            "module": func.__module__,
                            "args_count": len(args),
                            "kwargs_keys": list(kwargs.keys())
                        })
                        raise
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def track_mev_opportunity(self, opportunity_data: Dict[str, Any]):
        """Track MEV opportunity detection."""
        if not self.initialized:
            return
        
        try:
            self.add_breadcrumb(
                message=f"MEV opportunity detected: {opportunity_data.get('token_pair', 'unknown')}",
                category="mev.opportunity",
                level="info",
                data=opportunity_data
            )
            
        except Exception as e:
            logger.error(f"Failed to track MEV opportunity: {e}")
    
    def track_trade_execution(self, trade_data: Dict[str, Any]):
        """Track trade execution."""
        if not self.initialized:
            return
        
        try:
            self.add_breadcrumb(
                message=f"Trade executed: {trade_data.get('profit', 0):.6f} ETH",
                category="mev.trade",
                level="info",
                data=trade_data
            )
            
        except Exception as e:
            logger.error(f"Failed to track trade execution: {e}")
    
    def track_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Track errors with context."""
        if not self.initialized:
            logger.error(f"Error tracked: {error}")
            return
        
        try:
            self.capture_exception(error, context)
            
        except Exception as e:
            logger.error(f"Failed to track error: {e}")
    
    def close(self):
        """Close Sentry client."""
        if self.initialized:
            try:
                sentry_sdk.flush()
                logger.info("Sentry client closed")
            except Exception as e:
                logger.error(f"Failed to close Sentry client: {e}")

# Global Sentry instance
sentry_monitor = SentryMonitor()

# Convenience functions
def capture_exception(exception: Exception, context: Optional[Dict[str, Any]] = None):
    """Capture an exception with context."""
    sentry_monitor.capture_exception(exception, context)

def capture_message(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
    """Capture a message with context."""
    sentry_monitor.capture_message(message, level, context)

def monitor_function(name: Optional[str] = None):
    """Decorator to monitor function performance and errors."""
    return sentry_monitor.monitor_function(name)

def track_mev_opportunity(opportunity_data: Dict[str, Any]):
    """Track MEV opportunity detection."""
    sentry_monitor.track_mev_opportunity(opportunity_data)

def track_trade_execution(trade_data: Dict[str, Any]):
    """Track trade execution."""
    sentry_monitor.track_trade_execution(trade_data)

def track_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    """Track errors with context."""
    sentry_monitor.track_error(error, context) 