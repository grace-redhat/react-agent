# OpenShell on OpenShift - Video 4 Setup

This guide deploys the OpenShell gateway to your OpenShift cluster. Video 3 deployed the agent to a standard namespace. Video 4 adds a separate OpenShell control plane for sandbox policy enforcement.

**Status**: Experimental. For private networks only.

## Why a Separate Namespace

OpenShell's gateway is a control plane that manages sandboxed agents. Separating it into its own namespace:
- Isolates the gateway from application workloads
- Makes policy and observability clearer
- Enables multiple agents to share the same gateway
- Simplifies RBAC and credentials

## Prerequisites

Verify you have completed Video 3 (agent deployed to OpenShift) and have:
- `oc` CLI configured
- Helm 3.x installed
- Admin access to the cluster (needed for SCC and cluster-scoped CRDs)

### 1. Install Red Hat Agent Sandbox Operator (cluster-wide, one-time)

The Red Hat Agent Sandbox Operator provides the `Sandbox` API for OpenShift. Install it via OLM before deploying the OpenShell chart:

```bash
# Create the operator namespace
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-agent-sandbox-operator
  labels:
    openshift.io/cluster-monitoring: "true"
EOF

# Create the operator group
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: agent-sandbox-operatorgroup
  namespace: openshift-agent-sandbox-operator
spec:
  targetNamespaces:
  - openshift-agent-sandbox-operator
EOF

# Subscribe to the operator
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: agent-sandbox-operator
  namespace: openshift-agent-sandbox-operator
spec:
  channel: stable
  installPlanApproval: Automatic
  name: agent-sandbox-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

# Verify the operator is running (may take 1-2 minutes)
oc -n openshift-agent-sandbox-operator get pods
```

This creates:
- `openshift-agent-sandbox-operator` namespace
- `sandboxes.sandbox.openshift.io` CRD (cluster-scoped)
- Operator pod (manages sandbox pod lifecycle)

For air-gapped clusters, refer to [Red Hat Agent Sandbox deployment docs](https://docs.redhat.com/en/documentation/openshift_sandboxed_containers/1.12/html/deploying_red_hat_build_of_agent_sandbox/index).

### 2. Create the OpenShell namespace

```bash
# New namespace for the gateway control plane
oc create ns openshell
```

This is separate from your Video 3 agent namespace. Agents deploy elsewhere; the gateway manages them from here.

### 3. Grant OpenShift privileges to sandbox pods

OpenShift enforces **Security Context Constraints (SCC)** — stricter security rules than vanilla Kubernetes. Sandbox pods need the `privileged` SCC to set up kernel-level isolation (Landlock, seccomp, namespace restrictions).

```bash
# Grant privileged SCC to the openshell-sandbox service account
# (The Helm chart will create this service account)
oc adm policy add-scc-to-user privileged -z openshell-sandbox -n openshell
```

**Why privileged?** The supervisor (the enforcement component inside each sandbox) needs privileges to apply security constraints to the agent process. This doesn't mean the agent runs privileged—it means the supervisor can restrict the agent.

### 4. Deploy the OpenShell gateway

```bash
helm install openshell oci://ghcr.io/nvidia/openshell/helm-chart \
  --version 0.1.0 \
  --namespace openshell \
  -f openshell/values.yaml
```

### 5. Verify the gateway is ready

```bash
# Wait for the gateway pod to be Running
oc rollout status statefulset/openshell -n openshell

# Port-forward for local access (while developing)
oc port-forward -n openshell svc/openshell 8080:8080 &

# Register the gateway with the OpenShell CLI
openshell gateway add http://127.0.0.1:8080 --local --name openshift

# Verify connectivity
openshell status
```

## Next: Deploy an Agent to a Sandbox

Once the gateway is running, agents (from Video 3 or elsewhere) can be deployed as sandboxes:

```bash
openshell sandbox create \
  --name my-agent-sandbox \
  --image your-registry/react-agent:latest
```

The supervisor inside the sandbox enforces your `values.yaml` policy (filesystem, network, process, inference). Check policy decisions:

```bash
# View allow/deny decisions
oc logs -n openshell -l app=openshell-gateway -f
```

## Troubleshooting

**Gateway pod in CrashLoopBackOff?**
- Verify SCC was granted: `oc get scc privileged -o yaml | grep openshell-sandbox`
- Check that `agent-sandbox-system` controller is running: `kubectl -n agent-sandbox-system get pods`

**Helm chart fails with "Sandbox API not found"?**
- Agent Sandbox CRDs not installed. Run step 1 first.
- Or disable the check (offline only): add `--set agentSandbox.preflight.enabled=false`

**Agent sandbox fails to start?**
- Check gateway logs: `oc logs -n openshell -l app=openshell-gateway`
- Verify policy is valid YAML: `helm template openshell ... -f values.yaml | grep -A 20 "policy:"`

**Policy denying too much?**
- OpenShell logs every deny with context (binary, destination, syscall)
- Use [Policy Advisor](https://docs.nvidia.com/openshell/latest/sandboxes/policy-advisor) to propose narrower rules
- Check `values.yaml` filesystem, network, and process sections

## Production: TLS and OIDC

For multi-user production deployments:

```bash
# Install cert-manager and configure a ClusterIssuer first
helm install openshell oci://ghcr.io/nvidia/openshell/helm-chart \
  --version 0.1.0 \
  --namespace openshell \
  -f openshell/values.yaml \
  --set server.disableTls=false \
  --set certManager.enabled=true \
  --set certManager.serverIssuerRef.name=letsencrypt-prod \
  --set certManager.serverIssuerRef.kind=ClusterIssuer \
  --set openshiftRoute.enabled=true \
  --set openshiftRoute.host=openshell.apps.your-domain.com \
  --set server.oidc.issuer=https://your-oidc-issuer \
  --set server.oidc.audience=openshell
```

Refer to:
- [Managing Certificates](https://docs.nvidia.com/openshell/latest/kubernetes/managing-certificates)
- [Access Control](https://docs.nvidia.com/openshell/latest/kubernetes/access-control)

## References

- [OpenShell Kubernetes Setup](https://docs.nvidia.com/openshell/latest/kubernetes/setup)
- [OpenShell OpenShift Install](https://docs.nvidia.com/openshell/latest/kubernetes/openshift)
- [Agent Sandbox Getting Started](https://agent-sandbox.sigs.k8s.io/docs/getting_started/)
