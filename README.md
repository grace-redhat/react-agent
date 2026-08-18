# AgentOps Unlocked

Companion repo for the **AgentOps Unlocked** video series.

_"I built this on my laptop &rarr; I shipped it to production &rarr; I trust it in production."_

This repo contains a LangGraph ReAct agent that evolves across the series&mdash;from a local prototype running on Ollama to a production-grade deployment on Kubernetes with sandboxing, zero-trust identity, and observability.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) &mdash; Python package manager
- [GNU Make](https://www.gnu.org/software/make/) and a bash-compatible shell (Windows: use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) or [Git Bash](https://git-scm.com/downloads))
- [Ollama](https://ollama.com/) &mdash; local inference (Video 2)
- [Podman](https://podman.io/) or [Docker](https://www.docker.com/) &mdash; container builds (Video 3+)
- [Helm](https://helm.sh/) &mdash; Kubernetes deployment (Video 3+)
- [oc CLI](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html) &mdash; OpenShift deployment (Video 3+)

---

## Series Overview

| # | Video | What You Build | Repo Content |
|---|-------|---------------|--------------|
| 1 | [Is Your AI Agent a Liability?](#video-1--is-your-ai-agent-a-liability) | &mdash; | No code (conceptual framing) |
| 2 | [Run Local AI Agents for Free](#video-2--run-local-ai-agents-for-free-ollama--qwen--mcp) | Working local agent | Agent code, Ollama/OGX setup, MCP tools |
| 3 | [Deploy AI Agents on Kubernetes](#video-3--deploying-ai-agents-on-kubernetes-ollama-to-vllm) | Containerized agent on OpenShift | Dockerfile, Helm chart, deploy targets |
| 4 | [Sandbox Your AI Agent](#video-4--sandbox-your-ai-agent-openshell) | Sandboxed agent with OpenShell | _Coming soon_ |
| 5 | [Zero-Trust Agent Identity](#video-5--zero-trust-agent-identity-with-spiffespire) | Identity-based tool authorization | MCP Gateway manifests |
| 6 | [LLM Observability](#video-6--llm-observability-monitor-and-trace-ai-agents) | MLflow tracing | Tracing config |

---

## Video 1 &mdash; Is Your AI Agent a Liability?

Series opener. Walks through the evolution of the AI stack&mdash;from chat completions to autonomous agents&mdash;and establishes the production gap. No code to run; every subsequent video references this framing.

---

## Video 2 &mdash; Run Local AI Agents for Free (Ollama + Qwen + MCP)

Build a working AI agent on your laptop using Ollama for local inference and MCP for tool connectivity.

### Files

| Path | Purpose |
|------|---------|
| `src/react_agent/agent.py` | LangGraph ReAct agent |
| `src/react_agent/tools.py` | Calculator, fetch_page tools, MCP server config |
| `main.py` | FastAPI app with OpenAI-compatible `/chat/completions` endpoint |
| `run_ogx_server.yaml` | OGX local server config (Ollama provider) |
| `playground/` | Browser-based chat UI |

### Setup

```bash
make init                     # create .env from .env.example
make env                      # create venv, install dependencies
make ollama MODEL=qwen3:1.7b  # install Ollama, pull model
```

Edit `.env`:

```ini
BASE_URL=http://localhost:8321/v1
MODEL_ID=ollama/qwen3:1.7b
```

> The `MODEL_ID` must use the `ollama/` prefix and match `ollama list` exactly.

### Run

```bash
make ogx-server   # terminal 1 — keep open
make run-app      # terminal 2 — agent at http://localhost:8000
```

### Test

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is 2+2?"}], "stream": false}'
```

---

## Video 3 &mdash; Deploying AI Agents on Kubernetes: Ollama to vLLM

The same agent, containerized and deployed to OpenShift. Inference moves from Ollama to vLLM for multi-user throughput. **The agent code does not change.**

### Files

| Path | Purpose |
|------|---------|
| `Dockerfile` | UBI9 Python 3.12 container image |
| `deployment/` | Helm chart (`Chart.yaml`, `templates/`) |
| `values.yaml` | Agent-specific Helm overrides |
| `Makefile` | `build`, `push`, `deploy`, `dry-run`, `undeploy` targets |

### Configure

Edit `.env` for your cluster:

```ini
API_KEY=your-api-key
BASE_URL=https://your-vllm-endpoint.svc.cluster.local:8443/v1
MODEL_ID=qwen3-17b
CONTAINER_IMAGE=quay.io/your-username/langgraph-react-agent:latest
```

### Build and Deploy

```bash
make build        # build container image (podman/docker)
make push         # push to registry
make deploy       # helm install to current namespace
```

Or build in-cluster without podman/docker:

```bash
make build-openshift
```

### Verify

```bash
oc get route langgraph-react-agent -o jsonpath='{.spec.host}'
curl -k https://<route>/health
```

---

## Video 4 &mdash; Sandbox Your AI Agent: OpenShell

Execution containment with [OpenShell](https://github.com/NVIDIA/OpenShell). Demonstrates why a default container is not a sandbox and how to enforce filesystem, network, and process policy around agent workloads.

> Content for this video will be added to the repo. Check back for OpenShell policy files and walkthrough.

---

## Video 5 &mdash; Zero-Trust Agent Identity with SPIFFE/SPIRE

SPIFFE/SPIRE issues workload identity to agents. An MCP Gateway (Kuadrant-based) sits in front of tool servers and authorizes each tool call against the caller's identity.

### Files

| Path | Purpose |
|------|---------|
| `deployment/mcp_gateway/kuadrant-operator.yaml` | Kuadrant operator + CatalogSource |
| `deployment/mcp_gateway/kuadrant-cr.yaml` | Activate Kuadrant |
| `deployment/mcp_gateway/istio-operator.yaml` | Istio Sail operator |
| `deployment/mcp_gateway/istio-selfmanaged.yaml` | Istio control plane |
| `deployment/mcp_gateway/gateway.yaml` | Gateway + ReferenceGrant |
| `deployment/mcp_gateway/mcp-gateway-values.yaml` | MCP Gateway Helm values |
| `deployment/mcp_gateway/reference-grant.yaml` | ReferenceGrant for MCPGatewayExtension |
| `deployment/mcp_gateway/agent-authpolicy.yaml` | Tool-level AuthPolicy (readonly vs readwrite) |
| `deployment/mcp_gateway/agent-identities.yaml` | Demo API key secrets |
| `deployment/github-mcp-server.yaml` | GitHub MCP server Deployment + Service |
| `deployment/github-mcp-registration.yaml` | HTTPRoute + MCPServerRegistration |

### Deploy (MCP Gateway)

```bash
# 1. Kuadrant
oc apply -f deployment/mcp_gateway/kuadrant-operator.yaml
# wait for Ready, then:
oc apply -f deployment/mcp_gateway/kuadrant-cr.yaml

# 2. Istio
oc create namespace gateway-system
oc apply -f deployment/mcp_gateway/istio-operator.yaml
# wait for Ready, then:
oc apply -f deployment/mcp_gateway/istio-selfmanaged.yaml
# wait for Ready, then:
oc apply -f deployment/mcp_gateway/gateway.yaml

# 3. MCP Gateway
export MCP_GATEWAY_VERSION=0.7.1
kubectl apply -k "https://github.com/kuadrant/mcp-gateway/config/crd?ref=v${MCP_GATEWAY_VERSION}"
helm upgrade -i mcp-gateway oci://ghcr.io/kuadrant/charts/mcp-gateway \
  --version ${MCP_GATEWAY_VERSION} \
  -f deployment/mcp_gateway/mcp-gateway-values.yaml \
  -n mcp-system --create-namespace
oc apply -f deployment/mcp_gateway/reference-grant.yaml

# 4. Register GitHub MCP server
oc create secret generic github-mcp-token \
  --from-literal=GITHUB_TOKEN=<your-token> -n mcp-system
oc apply -f deployment/github-mcp-server.yaml
oc apply -f deployment/github-mcp-registration.yaml

# 5. Authorization policy + demo identities
oc apply -f deployment/mcp_gateway/agent-authpolicy.yaml
# edit agent-identities.yaml with real API keys first
oc apply -f deployment/mcp_gateway/agent-identities.yaml
```

> SPIFFE/SPIRE manifests will be added to the repo alongside the video release.

---

## Video 6 &mdash; LLM Observability: Monitor and Trace AI Agents

MLflow Tracing captures every prompt, reasoning step, tool invocation, and token cost. OpenTelemetry-compatible.

### Files

| Path | Purpose |
|------|---------|
| `src/react_agent/tracing.py` | MLflow setup, health checks, K8s SA auth, TLS |
| `.env.example` | MLflow config (local and OpenShift sections) |

### Enable Tracing

Add to `.env`:

```ini
MLFLOW_TRACKING_URI="http://localhost:5000"
MLFLOW_EXPERIMENT_NAME="langgraph-react-agent"
```

Start MLflow:

```bash
uv run --extra tracing mlflow server --port 5000
```

For OpenShift (in-pod with K8s service account auth):

```ini
MLFLOW_TRACKING_URI=https://mlflow.redhat-ods-applications.svc:8443/mlflow
MLFLOW_EXPERIMENT_NAME=langgraph-react-agent
MLFLOW_TRACKING_AUTH=kubernetes-namespaced
MLFLOW_TRACKING_SERVER_CERT_PATH=/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt
```

Tracing is optional. If `MLFLOW_TRACKING_URI` is not set, the agent runs without it.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | OpenAI-compatible chat (supports `stream: true`) |
| `/health` | GET | Service health check |
| `/` | GET | Playground chat UI (disabled when auth is enabled) |

---

## Tests

```bash
make test                  # unit tests
make test-integration      # deployment integration tests
make test-auth-integration # auth integration tests
```

---

## Resources

- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [LangChain](https://python.langchain.com/)
- [OGX](https://ogx-ai.github.io/docs/)
- [Ollama](https://ollama.com/docs)
- [MCP Gateway](https://github.com/Kuadrant/mcp-gateway)
- [OpenShell](https://github.com/NVIDIA/OpenShell)
- [SPIFFE/SPIRE](https://spiffe.io/)

## License

See [LICENSE](LICENSE).
