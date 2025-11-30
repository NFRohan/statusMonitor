# StatusMonitor

A real-time system monitoring application with a web dashboard and standalone agent.

## Architecture

- **Frontend**: React + Vite + Tailwind CSS - Web dashboard for viewing metrics
- **Auth Service**: FastAPI + PostgreSQL - User authentication and agent management
- **Ingestion Service**: FastAPI + Redis - Receives metrics from agents
- **Distribution Service**: FastAPI + Redis + WebSocket - Real-time metric distribution
- **History Service**: FastAPI + InfluxDB - Historical metric storage and queries
- **Agent**: Python GUI application - Collects and sends system metrics

## Quick Start (Development)

1. **Clone and setup environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (defaults work for development)
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Access the dashboard:**
   - Open http://localhost:5173
   - Register a new account
   - Create an agent and copy the token

4. **Run the agent:**
   ```bash
   cd agent_service
   pip install -r requirements-gui.txt
   python gui_agent.py
   ```
   - Paste the token in Settings
   - Click "Start Agent"

## Production Deployment

1. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with secure values:
   ```env
   POSTGRES_PASSWORD=<strong-password>
   SECRET_KEY=<generate-with-python-secrets>
   INFLUXDB_TOKEN=<strong-token>
   INFLUXDB_ADMIN_PASSWORD=<strong-password>
   ```

2. **Generate a secure SECRET_KEY:**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Deploy with production overrides:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

4. **For HTTPS**, configure a reverse proxy (nginx/traefik) in front of the frontend service.

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 5173 (dev) / 80 (prod) | Web dashboard |
| Auth Service | 8000 | Authentication API |
| Ingestion Service | 8001 | Metrics ingestion endpoint |
| Distribution Service | 8002 | WebSocket server |
| History Service | 8003 | Historical data API |
| PostgreSQL | 5432 | User/agent database |
| Redis | 6379 | Pub/sub message broker |
| InfluxDB | 8086 | Time-series metrics storage |

## Agent Installation

### From Source
```bash
pip install psutil requests
python agent_service/gui_agent.py
```

### Build Standalone Executable (Windows)
```powershell
.\build_agent.ps1
# Output: dist/StatusMonitorAgent.exe
```

## API Endpoints

### Auth Service
- `POST /register` - Create new user
- `POST /token` - Login and get tokens
- `POST /refresh` - Refresh access token
- `GET /users/me` - Get current user
- `POST /agents` - Create new agent
- `GET /agents` - List user's agents
- `DELETE /agents/{id}` - Delete agent

### Ingestion Service
- `POST /ingest` - Submit metrics (requires X-Agent-Token header)

### History Service
- `GET /history/{agent_id}/cpu` - CPU usage history
- `GET /history/{agent_id}/memory` - Memory usage history
- `GET /history/{agent_id}/disk` - Disk usage history
- `GET /history/{agent_id}/network` - Network usage history
- `GET /history/{agent_id}/summary` - Summary statistics

## Environment Variables

See `.env.example` for all available configuration options.

## License

MIT
