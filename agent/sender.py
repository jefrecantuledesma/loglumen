"""
Event Sender for Loglumen Agent

Sends collected events to the Loglumen server via HTTP/HTTPS.
Includes retry logic, batching, and error handling.
"""

import json
import time
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

# Try to import requests library
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    # Fall back to urllib if requests not available
    try:
        import urllib.request
        import urllib.error
        URLLIB_AVAILABLE = True
    except ImportError:
        URLLIB_AVAILABLE = False


class SenderError(Exception):
    """Raised when sending events fails."""
    pass


class EventSender:
    """
    Sends events to the Loglumen server.

    Handles batching, retries, and error recovery.
    """

    def __init__(self, server_config: Dict[str, Any]):
        """
        Initialize the event sender.

        Args:
            server_config: Dictionary with server configuration
                Required keys: server_ip, server_port
                Optional keys: use_https, api_path, api_key, timeout,
                              max_retries, retry_delay
        """
        self.server_ip = server_config['server_ip']
        self.server_port = server_config['server_port']
        self.use_https = server_config.get('use_https', False)
        self.api_path = server_config.get('api_path', '/api/events')
        self.api_key = server_config.get('api_key', None)
        self.timeout = server_config.get('timeout', 30)
        self.max_retries = server_config.get('max_retries', 3)
        self.retry_delay = server_config.get('retry_delay', 5)

        # Build server URL
        protocol = "https" if self.use_https else "http"
        self.server_url = f"{protocol}://{self.server_ip}:{self.server_port}{self.api_path}"

        # Statistics
        self.total_sent = 0
        self.total_failed = 0

        # Check if we have a way to send HTTP requests
        if not REQUESTS_AVAILABLE and not URLLIB_AVAILABLE:
            raise SenderError(
                "No HTTP library available. Install requests: pip install requests"
            )

    def send_events(self, events: List[Dict[str, Any]], batch_size: int = 500) -> bool:
        """
        Send events to the server.

        Args:
            events: List of event dictionaries
            batch_size: Maximum events per batch

        Returns:
            bool: True if all events sent successfully
        """
        if not events:
            print("[INFO] No events to send")
            return True

        # Split into batches if needed
        batches = self._create_batches(events, batch_size)

        print(f"[INFO] Sending {len(events)} events in {len(batches)} batch(es)")

        all_success = True
        for i, batch in enumerate(batches, 1):
            print(f"[INFO] Sending batch {i}/{len(batches)} ({len(batch)} events)...",
                  end="", flush=True)

            success = self._send_batch_with_retry(batch)

            if success:
                print(" [OK]")
                self.total_sent += len(batch)
            else:
                print(" [FAILED]")
                self.total_failed += len(batch)
                all_success = False

        return all_success

    def _create_batches(self, events: List[Dict[str, Any]],
                       batch_size: int) -> List[List[Dict[str, Any]]]:
        """Split events into batches."""
        batches = []
        for i in range(0, len(events), batch_size):
            batches.append(events[i:i + batch_size])
        return batches

    def _send_batch_with_retry(self, batch: List[Dict[str, Any]]) -> bool:
        """Send a batch with retry logic."""
        for attempt in range(self.max_retries):
            try:
                return self._send_batch(batch)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"\n[WARN] Attempt {attempt + 1} failed: {e}")
                    print(f"[INFO] Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"\n[ERROR] All {self.max_retries} attempts failed: {e}")
                    return False

        return False

    def _send_batch(self, batch: List[Dict[str, Any]]) -> bool:
        """Send a single batch to the server."""
        # Prepare JSON payload
        payload = json.dumps(batch)

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Loglumen-Agent/1.0'
        }

        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            # Also support X-API-Key header
            headers['X-API-Key'] = self.api_key

        # Send using available HTTP library
        if REQUESTS_AVAILABLE:
            return self._send_with_requests(payload, headers)
        elif URLLIB_AVAILABLE:
            return self._send_with_urllib(payload, headers)
        else:
            raise SenderError("No HTTP library available")

    def _send_with_requests(self, payload: str, headers: Dict[str, str]) -> bool:
        """Send using the requests library."""
        try:
            response = requests.post(
                self.server_url,
                data=payload,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return True
            else:
                print(f"\n[ERROR] Server returned status {response.status_code}")
                if response.text:
                    print(f"[ERROR] Response: {response.text[:200]}")
                return False

        except requests.exceptions.Timeout:
            print(f"\n[ERROR] Connection timeout after {self.timeout} seconds")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"\n[ERROR] Connection failed: {e}")
            return False
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")
            return False

    def _send_with_urllib(self, payload: str, headers: Dict[str, str]) -> bool:
        """Send using urllib (fallback if requests not available)."""
        try:
            # Convert payload to bytes
            payload_bytes = payload.encode('utf-8')

            # Create request
            req = urllib.request.Request(
                self.server_url,
                data=payload_bytes,
                headers=headers,
                method='POST'
            )

            # Send request
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    return True
                else:
                    print(f"\n[ERROR] Server returned status {response.status}")
                    return False

        except urllib.error.URLError as e:
            print(f"\n[ERROR] Connection failed: {e}")
            return False
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        """Get sender statistics."""
        return {
            'total_sent': self.total_sent,
            'total_failed': self.total_failed
        }

    def test_connection(self) -> bool:
        """
        Test connection to the server.

        Sends a small test payload to verify connectivity.

        Returns:
            bool: True if server is reachable
        """
        print(f"[INFO] Testing connection to {self.server_url}...", end="",
              flush=True)

        test_event = [{
            "schema_version": 1,
            "category": "test",
            "event_type": "connection_test",
            "time": datetime.utcnow().isoformat() + "Z",
            "host": "test",
            "host_ipv4": "127.0.0.1",
            "os": "linux",
            "source": "agent",
            "severity": "info",
            "message": "Connection test from Loglumen agent",
            "data": {}
        }]

        try:
            success = self._send_batch(test_event)
            if success:
                print(" [OK]")
                return True
            else:
                print(" [FAILED]")
                return False
        except Exception as e:
            print(f" [FAILED] {e}")
            return False


def send_events_to_server(events: List[Dict[str, Any]],
                          server_config: Dict[str, Any]) -> bool:
    """
    Convenience function to send events.

    Args:
        events: List of event dictionaries
        server_config: Server configuration dictionary

    Returns:
        bool: True if successful

    Example:
        server_config = {
            'server_ip': '192.168.0.254',
            'server_port': 8080,
            'use_https': False
        }
        success = send_events_to_server(events, server_config)
    """
    sender = EventSender(server_config)
    return sender.send_events(events)


if __name__ == "__main__":
    """Test the sender module."""
    print("=" * 70)
    print("Event Sender Test")
    print("=" * 70)

    # Load configuration
    try:
        from config_loader import load_config
        config = load_config()
        server_config = config.get_server_config()
    except Exception as e:
        print(f"\n[ERROR] Could not load configuration: {e}")
        print("[INFO] Using default test configuration")
        server_config = {
            'server_ip': '192.168.0.254',
            'server_port': 8080,
            'use_https': False,
            'api_path': '/api/events',
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 5
        }

    print(f"\nServer: {server_config['server_ip']}:{server_config['server_port']}")
    print(f"HTTPS: {server_config.get('use_https', False)}")

    # Create sender
    try:
        sender = EventSender(server_config)
    except SenderError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    # Test connection
    print("\n--- Connection Test ---")
    connection_ok = sender.test_connection()

    if not connection_ok:
        print("\n[WARN] Connection test failed.")
        print("[INFO] This is expected if the server is not running yet.")
        print("[INFO] The sender is ready to use once the server is started.")

    # Create sample events for testing
    print("\n--- Sample Event Test ---")
    sample_events = [
        {
            "schema_version": 1,
            "category": "auth",
            "event_type": "ssh_login_success",
            "time": "2025-11-16T15:00:00Z",
            "host": "test-host",
            "host_ipv4": "192.168.0.100",
            "os": "linux",
            "source": "auth.log",
            "severity": "info",
            "message": "Test SSH login event",
            "data": {
                "username": "test_user",
                "remote_ip": "192.168.0.50",
                "auth_method": "publickey"
            }
        },
        {
            "schema_version": 1,
            "category": "software",
            "event_type": "software_installed",
            "time": "2025-11-16T15:01:00Z",
            "host": "test-host",
            "host_ipv4": "192.168.0.100",
            "os": "linux",
            "source": "dpkg",
            "severity": "info",
            "message": "Test package installation",
            "data": {
                "package_name": "test-package",
                "version": "1.0.0",
                "action": "install"
            }
        }
    ]

    print(f"[INFO] Attempting to send {len(sample_events)} sample events...")
    success = sender.send_events(sample_events)

    if success:
        print("\n[SUCCESS] Sample events sent successfully!")
    else:
        print("\n[INFO] Sample events could not be sent.")
        print("[INFO] This is normal if the server is not running yet.")

    # Show statistics
    print("\n--- Sender Statistics ---")
    stats = sender.get_stats()
    print(f"Total sent: {stats['total_sent']}")
    print(f"Total failed: {stats['total_failed']}")

    print("\n" + "=" * 70)
    print("[INFO] Sender module is ready to use!")
    print("[INFO] Start the Rust server on 192.168.0.254:8080 to receive events.")
    print("=" * 70)
