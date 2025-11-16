# Loglumen
## What is Loglumen? 
- Loglumen is a SIEM that aggregates important log notifications from Windows and Linux systems, sending them to a centralized server for easy viewing.
- The client code is written in Python, and the server log-parsing front-end is written in Rust.

## How does it work? 
- Client-side code works through important Windows log files, extracting relevant information
- The information is then aggregated into a JSON event structure, and sent off to the server
- The server parses this information, tracking which devices are having specific issues and displaying information to the user 

