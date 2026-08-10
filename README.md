<div style="text-align: center;">

![LangGraph Logo](/images/langgraph_logo.svg)

# ReACT Agent

</div>

---

## What this agent does

General-purpose agent using a ReAct loop: it reasons and calls tools (e.g. search, math) step by step. Built with
LangGraph and LangChain.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Podman](https://podman.io/) or [Docker](https://www.docker.com/) — for local container builds (Option A)
- [oc](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html) — for
  OpenShift deployment
- [Helm](https://helm.sh/) — for deploying to Kubernetes/OpenShift
- [GNU Make](https://www.gnu.org/software/make/) and a bash-compatible shell — on Windows,
  use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) (recommended)
  or [Git Bash](https://git-scm.com/downloads)

## Local Development

### Initiating base

`make init` creates a `.env` file from `.env.example`. Set your environment variables in the `.env` file.

```bash
make init
```

### Creating environment

Now you will remove old .venv and create new. Next dependencies will be installed.

```bash
make env
```

### Tracing (optional)

Tracing is optional. If MLflow tracing is required, enable it by uncommenting and setting the following environment variables in the `.env` file.

#### Tracing with a local MLflow server

```ini
MLFLOW_TRACKING_URI="http://localhost:5000"
MLFLOW_EXPERIMENT_NAME="langgraph-react-agent"
MLFLOW_HTTP_REQUEST_TIMEOUT=2
MLFLOW_HTTP_REQUEST_MAX_RETRIES=0
```

Then start the MLflow server in a separate terminal:

```bash
# Start the MLflow server
cd agents/langgraph/templates/react_agent
uv run --extra tracing mlflow server --port 5000
```

When `MLFLOW_TRACKING_URI` is set, `make run-app` and `make run-cli` will automatically install the tracing dependency.

#### Tracing with MLflow on OpenShift (RHOAI)

See `.env.example` for the supported configurations (local dev with manual token, in-pod with K8s service account auth).

**Notes:**

- Tracing is optional; if you do not set `MLFLOW_TRACKING_URI`, the application will run without MLflow logging.

- If `MLFLOW_TRACKING_URI` is set, the application will attempt to connect to the MLflow server at startup. If the server is unreachable, the application will log a warning and continue running without tracing.

- You can control how long the application waits for the MLflow server by setting `MLFLOW_HEALTH_CHECK_TIMEOUT` (in seconds, default: `5`).

### Setup Ollama

This will install ollama if it is not installed already. Then pull needed models for local work.
The default model is `llama3.1:8b`. To use a different model, pass `MODEL=`:
`make ollama MODEL=llama3.2:3b`

```bash
make ollama
```
Then update MODEL_ID in your .env to match, with the ollama/ prefix:
`MODEL_ID=ollama/qwen3:1.7b`

Note: OGX auto-discovers any model you pull with Ollama — do not add the model to registered_resources in run_ogx_server.yaml. Adding it there will cause a conflict on startup because Ollama has already registered it. Verify the exact model name with ollama list and use that name (with ollama/ prefix) as your MODEL_ID.

---

> **Local OGX:** requires `ollama/` prefix. The name after the prefix must exactly match what `ollama list` shows (e.g., if `ollama list` shows `qwen3:1.7b`, set `MODEL_ID=ollama/qwen3:1.7b`). Do not register the model manually in `run_ogx_server.yaml` — OGX discovers it automatically.

### Run OGX server

> **Keep this terminal open** – the server needs to keep running.
> You should see output indicating the server started on `http://localhost:8321`.

```bash
make ogx-server
```

### Run the interactive web application

> **Keep this terminal open** – the app needs to keep running.
> You should see output indicating the app started on `http://localhost:8000`.

```bash
cd agents/langgraph/templates/react_agent
make run-app           # fails if port is already in use and print steps TO-DO
```

### Interactive CLI

For terminal-based testing without a browser:

```bash
cd agents/langgraph/templates/react_agent
make run-cli
```

This launches an interactive prompt where you can pick predefined questions or type your own. Tool calls and results are
displayed inline with colored output.

## Deploying to OpenShift

### Setup

```bash
cd agents/langgraph/templates/react_agent
make init
```

### Configuration

Edit `.env` with your model endpoint and container image:

```ini
API_KEY = your-api-key-here
BASE_URL = https://your-model-endpoint.com/v1
MODEL_ID = llama-3.1-8b-instruct
CONTAINER_IMAGE = quay.io/your-username/langgraph-react-agent:latest
```

**Notes:**

- `API_KEY` - your API key or contact your cluster administrator
- `BASE_URL` - should end with `/v1`. For local OGX, use `http://localhost:8321/v1`
- `MODEL_ID` - model identifier available on your endpoint
  - **Local OGX:** requires `ollama/` prefix (e.g., `ollama/Llama3.1:8B`)
  - **Cluster deployment:** discover available models via `curl $BASE_URL/models` or check your model serving dashboard
- `CONTAINER_IMAGE` – full image path where the agent container will be pushed and pulled from. The image is built
  locally, pushed to this registry, and then deployed to OpenShift.

  Format: `<registry>/<namespace>/<image-name>:<tag>`

  Examples:

  - Quay.io: `quay.io/your-username/langgraph-react-agent:latest`
  - Docker Hub: `docker.io/your-username/langgraph-react-agent:latest`
  - GHCR: `ghcr.io/your-org/langgraph-react-agent:latest`

  > **Note:** OpenShift must be able to pull the container image. Make the image **public**, or configure
  an [image pull secret](https://docs.openshift.com/container-platform/latest/openshift_images/managing_images/using-image-pull-secrets.html)
  for private registries.

### Building the Container Image

Login to OC

```bash
oc login -u "login" -p "password" https://super-link-to-cluster:111
```

Login ex. Docker

```bash
docker login -u='login' -p='password' quay.io
```

#### Option A: Build locally and push to a registry

Requires Podman (or Docker) and a registry account (e.g., Quay.io).

```bash
make build    # builds the image locally
make push     # pushes to the registry specified in CONTAINER_IMAGE
```

#### Option B: Build in-cluster via OpenShift BuildConfig

No Podman, Docker, or registry account needed — just the `oc` CLI.

```bash
make build-openshift
```

After the build completes, set `CONTAINER_IMAGE` in your `.env` to the internal registry URL printed after the build.

### Deploying

#### Preview manifests (`make dry-run`)

```bash
make dry-run          # preview rendered Helm manifests (secrets redacted)
```

#### Deploy (`make deploy`)

```bash
make deploy
```

#### Verify deployment

After deploying, the application may take about a minute to become available while the pod starts up.

The route URL is printed after `make deploy`. You can also retrieve it manually:

```bash
oc get route langgraph-react-agent -o jsonpath='{.spec.host}'
```

#### Remove deployment (`make undeploy`)

```bash
make undeploy
```

## Tests

```bash
make test
```

## API Endpoints

### POST /chat/completions

Non-streaming:

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": false}'
```

Streaming:

```bash
curl -sN -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": true}'
```

Pretty Printed Stream:

```bash
curl -sN -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the best cluster hosting service?"}], "stream": true}' |
   jq -R -r -j --stream 'scan("^data:(.*)")[] | fromjson.choices[0].delta.content // empty'
```

### GET /health

```bash
curl http://localhost:8000/health
```

## MCP Gateway (Optional): Tool-Level Authorization for MCP Tools

The manifests under `deployment/mcp_gateway/` (plus a couple in `deployment/`) set up a gateway in front of the agent's MCP tool servers that authorizes each *tool call* individually — not just each request. The demo distinguishes a "readonly" API key, which can call `github_issue_read` but is denied on `github_issue_write`, from a "readwrite" key
that can call both. This is independent of the base agent deployment above — the agent runs fine without it

### How it fits together

| Layer | Provides | Installed by |
|---|---|---|
| Kuadrant | Policy engine (Authorino evaluates `AuthPolicy`: resolves the caller's identity from an API key, checks
it against a rule) | `kuadrant-operator.yaml` (operator, brings in Authorino + a DNS operator as OLM dependencies),
`kuadrant-cr.yaml` (activates it) || Istio (Sail operator) | The Istio control plane, and the `istio` `GatewayClass` it registers once running |`istio-operator.yaml` (Sail operator subscription), `istio-selfmanaged.yaml` (`Istio` CR) || Gateway | The actual Envoy proxy traffic flows through — nothing serves traffic until this is applied |`gateway.yaml` (`Gateway` resource, class `istio`) — the object `AuthPolicy` and the `HTTPRoute` both attach to || [MCP Gateway](https://github.com/Kuadrant/mcp-gateway) | Decodes MCP/JSON-RPC traffic into named, policy-addressable tools (e.g. `github_issue_write`) instead of opaque HTTP bytes | `mcp-gateway-values.yaml` (Helm values for the `mcp-gateway` chart), granted the `Gateway` above via `mcpGatewayExtension` || Backend MCP server | The actual GitHub MCP server the gateway proxies to | `github-mcp-server.yaml` (Deployment/Service), registered via `github-mcp-registration.yaml` (`HTTPRoute` + `MCPServerRegistration`) |

### Deployment order

```bash
# 1. Kuadrant: policy engine + its OLM dependencies (Authorino, DNS operator)
oc apply -f deployment/mcp_gateway/kuadrant-operator.yaml
# wait for the operator to report Ready, then:
oc apply -f deployment/mcp_gateway/kuadrant-cr.yaml

# 2. Istio (Sail operator): control plane, then the actual Gateway
oc create namespace gateway-system
oc apply -f deployment/mcp_gateway/istio-operator.yaml
# wait for the sailoperator subscription to report Ready, then:
oc apply -f deployment/mcp_gateway/istio-selfmanaged.yaml
# wait for the Istio CR to report Ready, then:
oc apply -f deployment/mcp_gateway/gateway.yaml

# 3. MCP Gateway: CRDs, then the chart itself, pointed at the Gateway from step 2
export MCP_GATEWAY_VERSION=0.7.1
kubectl apply -k "https://github.com/kuadrant/mcp-gateway/config/crd?ref=v${MCP_GATEWAY_VERSION}"
helm upgrade -i mcp-gateway oci://ghcr.io/kuadrant/charts/mcp-gateway \
  --version ${MCP_GATEWAY_VERSION} \
  -f deployment/mcp_gateway/mcp-gateway-values.yaml \
  -n mcp-system --create-namespace
oc apply -f deployment/mcp_gateway/reference-grant.yaml

# 4. Register the GitHub MCP server behind it
oc create secret generic github-mcp-token --from-literal=GITHUB_TOKEN=<your-github-token> -n mcp-system
oc apply -f deployment/github-mcp-server.yaml
oc apply -f deployment/github-mcp-registration.yaml

# 5. Apply the tool-level authorization policy and demo identities
oc apply -f deployment/mcp_gateway/agent-authpolicy.yaml
# fill in deployment/mcp_gateway/agent-identities.yaml with real API keys first
oc apply -f deployment/mcp_gateway/agent-identities.yaml

# Before running the sequence above:** confirm `MCP_GATEWAY_VERSION` against a real [released tag](https://github.com/Kuadrant/mcp-gateway/releases) — `0.7.1` is current as of writing but may drift. Also confirm `deployment/mcp_gateway/mcp-gateway-values.yaml`'s `gateway.publicHost` and `deployment/github-mcp-registration.yaml`'s `HTTPRoute.hostnames` use the *same* value (your cluster's apps domain).

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [OGX Documentation](https://ogx-ai.github.io/docs/)
- [Ollama Documentation](https://ollama.com/docs)
