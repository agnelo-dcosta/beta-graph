# GCP Trial Deployment Guide

Step-by-step guide to deploy the beta-graph MCP servers on Google Cloud using your $300 free trial.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GCE VM (e2-small, 2GB RAM)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Chroma    │  │ WTA Server │  │  Weather Server     │  │
│  │  (in-process│  │   :8001    │  │      :8003          │  │
│  │  /chroma_   │  │            │  │                     │  │
│  │   data)     │  └─────────────┘  └─────────────────────┘  │
│  └─────────────┘                                              │
└─────────────────────────────────────────────────────────────┘
         ↑
    Your laptop runs: run_agent.py (connects via WTA_MCP_URL, WEATHER_MCP_URL)
```

Everything runs on one VM. Chroma stores data on the VM disk. You run the agent locally and connect to the remote servers.

---

## Prerequisites

- GCP project with billing enabled (trial uses $300 credit)
- `gcloud` CLI installed and logged in
- API keys ready: `google_maps_api_key`, `openweathermap_api_key` (for the servers)

---

## Step 1: Set Your Project and Create the VM

```bash
# Set your project (replace with your GCP project ID)
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# Create VM: e2-small has 2GB RAM (needed for sentence-transformers)
gcloud compute instances create beta-graph-server \
  --project=$PROJECT_ID \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --tags=beta-graph
```

---

## Step 2: Allow Traffic on Ports 8001 and 8003

```bash
# Create firewall rule for MCP servers
gcloud compute firewall-rules create allow-beta-graph-mcp \
  --project=$PROJECT_ID \
  --network=default \
  --allow=tcp:8001,tcp:8003 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=beta-graph \
  --description="MCP servers (WTA, Weather)"
```

> **Note:** `0.0.0.0/0` allows anyone to reach the servers. For production, restrict `--source-ranges` to your IP.

---

## Step 3: SSH and Install Dependencies

```bash
# SSH into the VM
gcloud compute ssh beta-graph-server --zone=us-central1-a --project=$PROJECT_ID
```

On the VM, run:

```bash
# Update and install Python + git (Ubuntu 22.04 includes Python 3.10)
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip git

# Verify Python version
python3 --version   # Should be 3.10+
```

---

## Step 4: Deploy the Code

**Option A: Clone from Git** (if your repo is on GitHub/GitLab)

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/beta-graph.git
cd beta-graph
```

**Option B: Copy from your laptop** (using `gcloud compute scp`)

From your **local machine** (new terminal):

```bash
# From project root - exclude keys/ and chroma_data for security
gcloud compute scp --recurse \
  --exclude='.git' --exclude='chroma_data' --exclude='keys' \
  . beta-graph-server:~/beta-graph --zone=us-central1-a --project=$PROJECT_ID
```

Then on the VM:

```bash
cd ~/beta-graph
```

---

## Step 5: Run Setup Script (Optional)

On the VM, you can use the setup script to install dependencies:

```bash
cd ~/beta-graph
chmod +x scripts/setup_gcp_vm.sh
./scripts/setup_gcp_vm.sh
```

Or manually install:

---

## Step 6: Install the Package (if not using setup script)

On the VM:

```bash
cd ~/beta-graph
pip install --user -e .
```

If `pip install -e .` fails, try:

```bash
pip install --user uv && uv pip install --system -e .
```

Or:

```bash
python3 -m pip install --user -e .
```

---

## Step 7: Set Up API Keys

The WTA server needs Google Maps (for geocoding), and the Weather server needs OpenWeatherMap. These keys are **never** stored in the repo (gitignored); you must create them on the VM yourself.

> **Why no keys in the repo?**  
> - **Clone from Git**: `keys/` is in `.gitignore`, so it won't exist on the VM.  
> - **SCP from laptop**: `keys/` is excluded for security (never copy keys over the network).

### Get your API keys

| Key | Used by | Where to get it |
|-----|---------|-----------------|
| **Google Maps** | WTA server (geocoding) | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Create API key → Enable [Places API](https://console.cloud.google.com/apis/library/places-backend.googleapis.com) |
| **OpenWeatherMap** | Weather server | [OpenWeatherMap](https://openweathermap.org/api) → Sign up → API keys |

### Option A: Environment variables (simple)

Create a file `~/beta-graph/env.sh` on the VM:

```bash
# Replace with your actual keys
export GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
export OPENWEATHERMAP_API_KEY="your-openweathermap-api-key"
```

Then `source ~/beta-graph/env.sh` before running servers or loading trails.

### Option B: Key files (like local dev)

On the VM, create the `keys/` directory and key files:

```bash
cd ~/beta-graph
mkdir -p keys

# Paste your keys (replace with actual values)
echo "YOUR_GOOGLE_MAPS_KEY" > keys/google_maps_api_key
echo "YOUR_OPENWEATHERMAP_KEY" > keys/openweathermap_api_key

# Restrict permissions
chmod 600 keys/*
```

**Required file names:** `keys/google_maps_api_key`, `keys/openweathermap_api_key`  
**Equivalent env vars:** `GOOGLE_MAPS_API_KEY`, `OPENWEATHERMAP_API_KEY`

---

## Step 8: Load Trails (One-Time)

On the VM:

```bash
cd ~/beta-graph
source env.sh   # only if using Option A (env vars) for keys

# Load trails for one region (faster) or all regions
python3 scripts/load_wta_by_region.py --region "North Cascades"

# Or load by location
python3 scripts/load_wta_to_chroma.py --location "North Bend"

# Or load all regions (takes longer)
python3 scripts/load_wta_by_region.py
```

This can take 10–30+ minutes depending on region count. Chroma data is saved to `./chroma_data`.

---

## Step 9: Start the Servers

### Run in foreground (for testing)

```bash
cd ~/beta-graph
source env.sh   # only if using Option A for keys
python3 scripts/run_servers.py
```

Press Ctrl+C to stop.

### Run in background (for production)

```bash
cd ~/beta-graph
source env.sh   # only if using Option A for keys
nohup python3 scripts/run_servers.py --background > servers.log 2>&1 &
```

Or use `tmux` so it survives SSH disconnect:

```bash
tmux new -s servers
cd ~/beta-graph
source env.sh   # only if using Option A for keys
python3 scripts/run_servers.py
# Detach: Ctrl+B, then D
# Reattach later: tmux attach -t servers
```

---

## Step 10: Get the VM's External IP

```bash
# On the VM or from your laptop:
gcloud compute instances describe beta-graph-server \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Example output: `34.123.45.67`

---

## Step 11: Run the Agent from Your Laptop

On your **local machine**:

```bash
cd beta-graph

# Point agent to the remote MCP servers
export WTA_MCP_URL="http://YOUR_VM_IP:8001/sse"
export WEATHER_MCP_URL="http://YOUR_VM_IP:8003/sse"
python3 scripts/run_agent.py "easy hikes near North Bend"
```

Or add to your shell profile (`.zshrc` or `.bashrc`):

```bash
export WTA_MCP_URL="http://YOUR_VM_IP:8001/sse"
export WEATHER_MCP_URL="http://YOUR_VM_IP:8003/sse"
```

---

## Quick Reference: One-Liner Summary

| Step | Command |
|------|---------|
| Create VM | `gcloud compute instances create beta-graph-server --zone=us-central1-a --machine-type=e2-small --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud --boot-disk-size=30GB` |
| Firewall | `gcloud compute firewall-rules create allow-beta-graph-mcp --allow=tcp:8001,tcp:8003 --target-tags=beta-graph` |
| SSH | `gcloud compute ssh beta-graph-server --zone=us-central1-a` |
| Install | `pip install --user -e .` |
| Keys | Create `keys/google_maps_api_key` and `keys/openweathermap_api_key` on the VM (or set env vars); see Step 7 |
| Load trails | `python3 scripts/load_wta_by_region.py --region "North Cascades"` |
| Run servers | `python3 scripts/run_servers.py --background` |
| Connect | `WTA_MCP_URL=http://IP:8001/sse WEATHER_MCP_URL=http://IP:8003/sse python3 scripts/run_agent.py` |

---

## Cost (GCP Trial)

With the $300 trial credit and an e2-small VM:

- **e2-small**: ~$12–15/month
- **30GB disk**: ~$1.20/month
- **Total**: ~$14–16/month

Your $300 credit covers roughly **18–20 months** of always-on runtime.

---

## Troubleshooting

### "Connection refused" from agent

- Check firewall: `gcloud compute firewall-rules list`
- Ensure servers are running: `ps aux | grep beta_graph`
- Test: `curl http://YOUR_VM_IP:8001/sse` (should not 404)

### "API key not found"

- Verify `keys/` files or env vars are set
- For Google Maps: enable [Places API](https://console.cloud.google.com/apis/library/places-backend.googleapis.com) in your GCP project

### Servers stop after SSH disconnect

- Use `tmux` or `systemd` to keep them running
- Or: `nohup python3 scripts/run_servers.py --background &`

### Out of memory

- e2-small has 2GB. If loading fails, try `e2-medium` (4GB) for the load step, then downgrade, or use a larger machine during load only.
