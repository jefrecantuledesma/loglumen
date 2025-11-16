# Deployment

This folder contains scripts, configuration files, and instructions for deploying Loglumen in various environments.

## Deployment Options

Loglumen can be deployed in several ways:

1. **Manual Installation** - Direct installation on servers (good for testing)
2. **Docker** - Containerized deployment (recommended for production)
3. **Systemd Service** - Run agent/server as system services on Linux
4. **Windows Service** - Run agent as Windows service

## Quick Start Deployment

### Option 1: Manual Installation (Testing/Development)

#### Deploy the Server

```bash
# On your central server machine
cd /opt
git clone <repository-url> loglumen
cd loglumen

# Build the Rust server
cd server
cargo build --release

# Configure the server
cp ../config/server.example.toml ../config/server.toml
nano ../config/server.toml  # Edit with your settings

# Run the server
./target/release/server
```

#### Deploy the Agent (On Each Monitored Machine)

```bash
# On each monitored machine
cd /opt
git clone <repository-url> loglumen
cd loglumen

# Install Python dependencies
cd agent
pip install -r requirements.txt  # (if any are added)

# Configure the agent
cp ../config/agent.example.toml ../config/agent.toml
nano ../config/agent.toml  # Set server IP and client name

# Run the agent (requires admin/root)
sudo python main.py
```

### Option 2: Docker Deployment (Recommended)

Docker makes deployment easier and more consistent across different environments.

#### Prerequisites
- Docker installed on both server and agent machines
- Docker Compose (optional, for easier management)

#### Deploy Server with Docker

```bash
# Create Dockerfile for server (example)
cd loglumen/server
docker build -t loglumen-server .

# Run the server container
docker run -d \
  --name loglumen-server \
  -p 8080:8080 \
  -v /var/lib/loglumen:/data \
  -v /etc/loglumen/server.toml:/app/config/server.toml \
  loglumen-server
```

#### Deploy Agent with Docker

```bash
# Create Dockerfile for agent (example)
cd loglumen/agent
docker build -t loglumen-agent .

# Run the agent container (needs access to host logs)
# Windows (requires Windows containers)
docker run -d \
  --name loglumen-agent \
  -v C:\Windows\System32\winevt\Logs:C:\Logs:ro \
  -v C:\loglumen\agent.toml:/app/config/agent.toml \
  loglumen-agent

# Linux
docker run -d \
  --name loglumen-agent \
  -v /var/log:/var/log:ro \
  -v /etc/loglumen/agent.toml:/app/config/agent.toml \
  loglumen-agent
```

### Option 3: Systemd Service (Linux)

Run the agent as a system service on Linux for automatic startup.

#### Create Systemd Unit File

```bash
sudo nano /etc/systemd/system/loglumen-agent.service
```

Add the following content:

```ini
[Unit]
Description=Loglumen Security Event Collection Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/loglumen/agent
ExecStart=/usr/bin/python3 /opt/loglumen/agent/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable and Start the Service

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable loglumen-agent

# Start the service now
sudo systemctl start loglumen-agent

# Check status
sudo systemctl status loglumen-agent

# View logs
sudo journalctl -u loglumen-agent -f
```

#### For the Server

```bash
sudo nano /etc/systemd/system/loglumen-server.service
```

```ini
[Unit]
Description=Loglumen Central SIEM Server
After=network.target

[Service]
Type=simple
User=loglumen
WorkingDirectory=/opt/loglumen/server
ExecStart=/opt/loglumen/server/target/release/server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable loglumen-server
sudo systemctl start loglumen-server
sudo systemctl status loglumen-server
```

### Option 4: Windows Service

Run the agent as a Windows service for automatic startup.

#### Using NSSM (Non-Sucking Service Manager)

1. **Download NSSM**
   - Download from [nssm.cc](https://nssm.cc/)
   - Extract to `C:\Program Files\nssm\`

2. **Install Agent as Service**
   ```cmd
   # Run as Administrator
   cd "C:\Program Files\nssm"
   nssm install LoglumenAgent "C:\Python39\python.exe" "C:\loglumen\agent\main.py"

   # Set service to start automatically
   nssm set LoglumenAgent Start SERVICE_AUTO_START

   # Start the service
   nssm start LoglumenAgent

   # Check status
   sc query LoglumenAgent
   ```

3. **View Service Logs**
   ```cmd
   # Configure logging in NSSM
   nssm set LoglumenAgent AppStdout "C:\loglumen\logs\stdout.log"
   nssm set LoglumenAgent AppStderr "C:\loglumen\logs\stderr.log"
   ```

## Docker Compose Example

For easier management of multiple containers, use Docker Compose.

### docker-compose.yml (Server)

```yaml
version: '3.8'

services:
  loglumen-server:
    build: ./server
    container_name: loglumen-server
    ports:
      - "8080:8080"
    volumes:
      - loglumen-data:/data
      - ./config/server.toml:/app/config/server.toml:ro
    environment:
      - RUST_LOG=info
    restart: unless-stopped

  postgres:  # Optional: if using PostgreSQL
    image: postgres:15
    container_name: loglumen-db
    environment:
      POSTGRES_DB: loglumen
      POSTGRES_USER: loglumen
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  loglumen-data:
  postgres-data:
```

### docker-compose.yml (Agent)

```yaml
version: '3.8'

services:
  loglumen-agent:
    build: ./agent
    container_name: loglumen-agent
    volumes:
      # Linux
      - /var/log:/var/log:ro
      - /run/systemd/journal:/run/systemd/journal:ro
      - ./config/agent.toml:/app/config/agent.toml:ro

      # Windows (uncomment for Windows)
      # - C:\Windows\System32\winevt\Logs:C:\Logs:ro
      # - C:\loglumen\agent.toml:C:\app\config\agent.toml:ro

    environment:
      - LOG_LEVEL=INFO
    restart: unless-stopped
```

### Deploy with Docker Compose

```bash
# Start the server
cd loglumen
docker-compose -f deploy/docker-compose-server.yml up -d

# Start agents on each monitored machine
cd loglumen
docker-compose -f deploy/docker-compose-agent.yml up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Example Dockerfile Templates

### Server Dockerfile

```dockerfile
# deploy/server.Dockerfile
FROM rust:1.75 as builder

WORKDIR /app
COPY server/Cargo.toml server/Cargo.lock ./
COPY server/src ./src

RUN cargo build --release

FROM debian:bookworm-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/server /app/server
COPY config/server.example.toml /app/config/server.toml

EXPOSE 8080

CMD ["/app/server"]
```

### Agent Dockerfile (Linux)

```dockerfile
# deploy/agent-linux.Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent/ .
COPY config/agent.example.toml /app/config/agent.toml

# Run as root to access system logs
USER root

CMD ["python", "main.py"]
```

### Agent Dockerfile (Windows)

```dockerfile
# deploy/agent-windows.Dockerfile
FROM python:3.11-windowsservercore

WORKDIR C:\\app

# Install dependencies
COPY agent\\requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent\\ .
COPY config\\agent.example.toml C:\\app\\config\\agent.toml

CMD ["python", "main.py"]
```

## Production Deployment Best Practices

### 1. Use HTTPS/TLS
```toml
# In server.toml
[server]
use_https = true
cert_file = "/etc/loglumen/cert.pem"
key_file = "/etc/loglumen/key.pem"
```

### 2. Set Up Firewall Rules

**Server (allow incoming on port 8080):**
```bash
# Linux (ufw)
sudo ufw allow 8080/tcp

# Linux (firewalld)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# Windows
netsh advfirewall firewall add rule name="Loglumen Server" dir=in action=allow protocol=TCP localport=8080
```

**Agents (allow outgoing to server):**
```bash
# Usually allowed by default, but verify firewall doesn't block
```

### 3. Use a Reverse Proxy (Nginx/Apache)

```nginx
# /etc/nginx/sites-available/loglumen
server {
    listen 443 ssl;
    server_name loglumen.company.com;

    ssl_certificate /etc/letsencrypt/live/loglumen.company.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/loglumen.company.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 4. Database Backups

```bash
# SQLite backup script
#!/bin/bash
BACKUP_DIR="/var/backups/loglumen"
DB_PATH="/var/lib/loglumen/events.db"
DATE=$(date +%Y%m%d_%H%M%S)

sqlite3 $DB_PATH ".backup $BACKUP_DIR/loglumen_$DATE.db"

# Keep only last 30 days
find $BACKUP_DIR -name "loglumen_*.db" -mtime +30 -delete
```

### 5. Monitoring

Monitor the Loglumen services themselves:

```bash
# Check if server is responding
curl http://localhost:8080/health

# Check agent status
systemctl status loglumen-agent

# Monitor logs for errors
tail -f /var/log/loglumen-server.log | grep ERROR
```

## Mass Deployment

For deploying agents to many machines:

### Using Ansible

```yaml
# ansible/deploy-agent.yml
---
- name: Deploy Loglumen Agent
  hosts: all
  become: yes

  tasks:
    - name: Install Python
      apt:
        name: python3
        state: present
      when: ansible_os_family == "Debian"

    - name: Clone Loglumen repository
      git:
        repo: https://github.com/your-org/loglumen.git
        dest: /opt/loglumen

    - name: Install Python dependencies
      pip:
        requirements: /opt/loglumen/agent/requirements.txt

    - name: Copy agent configuration
      template:
        src: agent.toml.j2
        dest: /opt/loglumen/config/agent.toml

    - name: Install systemd service
      copy:
        src: loglumen-agent.service
        dest: /etc/systemd/system/loglumen-agent.service

    - name: Enable and start service
      systemd:
        name: loglumen-agent
        enabled: yes
        state: started
        daemon_reload: yes
```

Run deployment:
```bash
ansible-playbook -i inventory.ini ansible/deploy-agent.yml
```

### Using Group Policy (Windows)

1. Create a GPO for agent installation
2. Use startup scripts to:
   - Install Python
   - Copy agent files
   - Configure agent with machine-specific settings
   - Install as Windows service

## Troubleshooting Deployment

### Server Won't Start
```bash
# Check if port is already in use
sudo netstat -tlnp | grep 8080

# Check server logs
tail -f /var/log/loglumen-server.log

# Verify configuration
cargo run --release -- --validate-config
```

### Agent Can't Connect to Server
```bash
# Test network connectivity
telnet server-ip 8080
# or
curl http://server-ip:8080/health

# Check agent logs
tail -f /var/log/loglumen-agent.log

# Verify DNS resolution
nslookup loglumen.company.com
```

### Permission Issues
```bash
# Ensure agent runs as root/administrator
# Linux
sudo /opt/loglumen/agent/main.py

# Check file permissions
ls -la /var/log/auth.log
```

## Security Considerations

1. **Network Segmentation**: Place server in a secure network segment
2. **Access Control**: Restrict who can access the server dashboard
3. **Encryption**: Always use HTTPS/TLS in production
4. **Credential Management**: Use secrets management (Vault, AWS Secrets Manager)
5. **Updates**: Keep all components updated regularly
6. **Logging**: Monitor the SIEM system itself for anomalies
7. **Backup**: Regular backups of the database and configuration

## Scaling

### Horizontal Scaling (Multiple Servers)

Use a load balancer to distribute agent connections:

```
        ┌─────────┐
        │  Load   │
        │ Balancer│
        └────┬────┘
             │
      ┬──────┴──────┬
      │             │
  ┌───▼───┐    ┌───▼───┐
  │Server1│    │Server2│
  └───┬───┘    └───┬───┘
      │             │
  ┌───▼─────────────▼───┐
  │  Shared Database    │
  │   (PostgreSQL)      │
  └─────────────────────┘
```

### Vertical Scaling (Bigger Server)

- Increase server resources (CPU, RAM, disk)
- Optimize database with indexes
- Use caching (Redis) for frequently accessed data

## Next Steps

1. Choose your deployment method (Docker recommended)
2. Set up the central server first
3. Deploy agents to a test machine
4. Verify events are being received
5. Gradually roll out to all machines
6. Set up monitoring and alerting
7. Create backup procedures
8. Document your specific deployment

For questions or issues, refer to the main README.md or create an issue in the repository.
