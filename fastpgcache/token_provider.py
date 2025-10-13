"""
Token provider for automatic credential rotation
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import threading
import time


class TokenProvider(ABC):
    """Abstract base class for token providers."""
    
    @abstractmethod
    def get_token(self) -> str:
        """Get a valid token, refreshing if necessary."""
        pass
    
    @abstractmethod
    def refresh_token(self) -> str:
        """Force token refresh."""
        pass


class DatabricksTokenProvider(TokenProvider):
    """
    Token provider for Databricks PostgreSQL instances.
    Automatically refreshes tokens before they expire.
    
    Example:
        >>> from databricks.sdk import WorkspaceClient
        >>> w = WorkspaceClient(profile="Oauth")
        >>> provider = DatabricksTokenProvider(
        ...     workspace_client=w,
        ...     instance_names=["my_instance"],
        ...     refresh_interval=3600  # Refresh every 1 hour
        ... )
        >>> token = provider.get_token()
    """
    
    def __init__(
        self,
        workspace_client,
        instance_names: list,
        refresh_interval: int = 3600,
        auto_refresh: bool = True
    ):
        """
        Initialize Databricks token provider.
        
        Args:
            workspace_client: Databricks WorkspaceClient instance
            instance_names: List of instance names to generate credentials for
            refresh_interval: Token refresh interval in seconds (default: 3600 = 1 hour)
            auto_refresh: Enable automatic background token refresh (default: True)
        """
        self.workspace_client = workspace_client
        self.instance_names = instance_names
        self.refresh_interval = refresh_interval
        self.auto_refresh = auto_refresh
        
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._lock = threading.Lock()
        self._refresh_thread: Optional[threading.Thread] = None
        self._stop_refresh = threading.Event()
        
        # Generate initial token
        self.refresh_token()
        
        # Start auto-refresh thread if enabled
        if auto_refresh:
            self._start_auto_refresh()
    
    def _generate_new_token(self) -> Dict[str, Any]:
        """Generate a new token from Databricks."""
        import uuid
        cred = self.workspace_client.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=self.instance_names
        )
        return cred
    
    def refresh_token(self) -> str:
        """
        Force refresh the token.
        
        Returns:
            The new token string
        """
        with self._lock:
            cred = self._generate_new_token()
            self._token = cred.token
            self._token_expires_at = datetime.now() + timedelta(seconds=self.refresh_interval)
            return self._token
    
    def get_token(self) -> str:
        """
        Get a valid token, refreshing if necessary.
        
        Returns:
            A valid token string
        """
        with self._lock:
            # Check if token needs refresh
            if self._token is None or self._should_refresh():
                return self.refresh_token()
            return self._token
    
    def _should_refresh(self) -> bool:
        """Check if token should be refreshed."""
        if self._token_expires_at is None:
            return True
        
        # Refresh if less than 5 minutes remaining
        buffer = timedelta(minutes=5)
        return datetime.now() + buffer >= self._token_expires_at
    
    def _start_auto_refresh(self):
        """Start background thread for automatic token refresh."""
        def refresh_loop():
            while not self._stop_refresh.is_set():
                # Sleep in small intervals to allow quick shutdown
                for _ in range(self.refresh_interval):
                    if self._stop_refresh.is_set():
                        return
                    time.sleep(1)
                
                # Refresh token
                try:
                    self.refresh_token()
                except Exception as e:
                    print(f"Warning: Failed to refresh token: {e}")
        
        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self._refresh_thread.start()
    
    def stop(self):
        """Stop automatic token refresh."""
        if self._refresh_thread:
            self._stop_refresh.set()
            self._refresh_thread.join(timeout=5)
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop()


