# GCP Deployment Guide

This guide covers deploying the WTA MCP server and Chroma vector store on Google Cloud.

## Architecture Options

### Option A: All Local (Development)
- MCP server runs locally (stdio) or with `--http` for remote
- Chroma persists to `./chroma_data`
- No GCP cost

### Option B: Chroma on GCP, MCP Local
- Chroma on Compute Engine (g1-small ~$15/mo)
- MCP server runs locally, connects via `CHROMA_SERVER_HOST`

### Option C: Full GCP (Production)
- Chroma on Compute Engine
- MCP server on Cloud Run (HTTP transport)

---

## 1. Deploy Chroma on GCP

Chroma needs at least 2GB RAM (g1-small). Use Deployment Manager or manual setup.

### Quick Deploy (Deployment Manager)

```bash
# Download Chroma deployment template
curl -O https://raw.githubusercontent.com/chroma-core/chroma/main/deployment-manager/chroma.yaml

# Deploy (replace with your project)
gcloud deployment-manager deployments create beta-graph-chroma \
  --config chroma.yaml \
  --project=YOUR_PROJECT_ID

# Get Chroma server IP
gcloud compute instances describe chroma-instance \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)' \
  --zone=us-central1-a
```

### Manual Docker on Compute Engine

```bash
# Create VM (g1-small has 1.7GB - e2-small has 2GB)
gcloud compute instances create chroma-vm \
  --machine-type=e2-small \
  --zone=us-central1-a \
  --image-family=cos-stable \
  --image-project=cos-cloud

# SSH and run Chroma
# docker run -p 8000:8000 chromadb/chroma
```

### Connect from MCP Server

```bash
export CHROMA_SERVER_HOST=YOUR_CHROMA_IP
export CHROMA_SERVER_PORT=8000
```

---

## 2. Deploy MCP Server on Cloud Run

For HTTP transport (remote agents):

```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/beta-graph-mcp

# Deploy (needs 2GB for sentence-transformers)
gcloud run deploy beta-graph-mcp \
  --image gcr.io/YOUR_PROJECT/beta-graph-mcp \
  --memory 2Gi \
  --allow-unauthenticated \
  --set-env-vars CHROMA_SERVER_HOST=YOUR_CHROMA_IP,CHROMA_SERVER_PORT=8000
```

### Connect Cursor to Cloud Run

Add to MCP config with HTTP transport:

```json
{
  "mcpServers": {
    "wta-trails": {
      "url": "https://beta-graph-mcp-xxx.run.app/sse"
    }
  }
}
```

---

## 3. Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CHROMA_SERVER_HOST` | Chroma HTTP host (GCP) | (local persist) |
| `CHROMA_SERVER_PORT` | Chroma port | 8000 |
| `CHROMA_PERSIST_DIR` | Local persist path | ./chroma_data |
| `USE_PLAYWRIGHT` | Use browser for scraping | true |
| `SCRAPE_DELAY` | Delay between requests (sec) | 2.0 |

---

## 4. Security Notes

- Chroma has no auth by default: put behind Cloud IAP or VPC
- Consider VPC connector for Cloud Run → Chroma private connectivity
- Use Secret Manager for any API keys (e.g. if switching to OpenAI embeddings)
