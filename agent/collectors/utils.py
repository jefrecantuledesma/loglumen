"""
Utility functions shared across all collectors

These helper functions make it easier to create standardized events
without repeating code in every collector.
"""

import socket
from datetime import datetime
from typing import Dict, Any


def get_hostname() -> str:
    """
    Get the hostname of this machine.

    Returns:
        str: The hostname (e.g., "webserver-01")
    """
    return socket.gethostname()


def get_local_ip() -> str:
    """
    Get the primary IPv4 address of this machine.

    Returns:
        str: IPv4 address (e.g., "192.168.1.100")

    Note:
        This gets the IP by creating a temporary UDP connection.
        It doesn't actually send any data, just figures out which
        network interface would be used to reach the internet.
    """
    try:
        # Create a socket to figure out which IP we'd use
        # We use Google's DNS (8.8.8.8) as the destination, but don't actually connect
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # If that fails, try to get hostname's IP
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            # Last resort - return localhost
            return "127.0.0.1"


def create_event(
    category: str,
    event_type: str,
    severity: str,
    message: str,
    source: str,
    os: str,
    data: Dict[str, Any],
    hostname: str = None,
    host_ip: str = None,
    timestamp: datetime = None
) -> Dict[str, Any]:
    """
    Create a standardized event dictionary that matches the Loglumen JSON schema.

    Args:
        category: Event category (auth, privilege, system, service, software, remote)
        event_type: Specific event type (login_success, login_failed, sudo_used, etc.)
        severity: Severity level (info, warning, error, critical)
        message: Human-readable description of the event
        source: Log source/file (e.g., "auth.log", "Security")
        os: Operating system ("linux" or "windows")
        data: Dictionary of event-specific details
        hostname: Hostname (if None, will auto-detect)
        host_ip: IPv4 address (if None, will auto-detect)
        timestamp: Event timestamp (if None, uses current UTC time)

    Returns:
        dict: Standardized event dictionary ready to be converted to JSON

    Example:
        event = create_event(
            category="auth",
            event_type="login_failed",
            severity="warning",
            message="Failed SSH login for user bob",
            source="auth.log",
            os="linux",
            data={"username": "bob", "remote_ip": "192.168.1.50"}
        )
    """
    # Auto-detect hostname and IP if not provided
    if hostname is None:
        hostname = get_hostname()
    if host_ip is None:
        host_ip = get_local_ip()
    if timestamp is None:
        timestamp = datetime.utcnow()

    # Create the event following the standard schema
    return {
        "schema_version": 1,
        "category": category,
        "event_type": event_type,
        "time": timestamp.isoformat() + "Z",  # ISO 8601 format with Z for UTC
        "host": hostname,
        "host_ipv4": host_ip,
        "os": os,
        "source": source,
        "severity": severity,
        "message": message,
        "data": data
    }


def parse_syslog_timestamp(log_line: str, year: int = None) -> datetime:
    """
    Parse a syslog-format timestamp from a log line.

    Syslog format: "Nov 16 14:30:25"

    Args:
        log_line: The log line containing the timestamp at the start
        year: The year to use (syslog doesn't include year). If None, uses current year.

    Returns:
        datetime: Parsed timestamp in UTC

    Example:
        timestamp = parse_syslog_timestamp("Nov 16 14:30:25 hostname sshd[123]: ...")
        # Returns: datetime(2025, 11, 16, 14, 30, 25)
    """
    if year is None:
        year = datetime.utcnow().year

    try:
        # Extract first 15 characters: "Nov 16 14:30:25"
        timestamp_str = log_line[:15]
        # Parse the timestamp
        dt = datetime.strptime(f"{year} {timestamp_str}", "%Y %b %d %H:%M:%S")
        return dt
    except Exception:
        # If parsing fails, return current time
        return datetime.utcnow()
