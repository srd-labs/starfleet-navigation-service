# Starfleet Navigation Service — Troubleshooting Notes

This document records issues encountered while building and deploying the
Starfleet Navigation Service to Google Kubernetes Engine (GKE).

The purpose is to capture the symptoms, investigation commands, root causes,
resolutions, and validation steps for real issues encountered during the lab.

---

## Issue 1 — kubectl Could Not Authenticate to GKE

### Symptom

After creating the GKE cluster and attempting to access it with `kubectl`,
the following message was displayed:

```text
CRITICAL: ACTION REQUIRED: gke-gcloud-auth-plugin,
which is needed for continued use of kubectl,
was not found or is not executable.
```

### Root Cause

The local workstation had `kubectl` and the Google Cloud CLI installed,
but the GKE authentication plugin required by `kubectl` was missing.

### Resolution

Install the GKE authentication plugin.

For a Homebrew-based installation:

```bash
brew install gke-gcloud-auth-plugin
```

Verify:

```bash
gke-gcloud-auth-plugin --version
```

Retrieve the cluster credentials again:

```bash
gcloud container clusters get-credentials enterprise-gke-alpha \
  --zone us-central1-a \
  --project starfleet-gke-platform-lab
```

### Validation

```bash
kubectl get nodes
```

The Alpha Quadrant node returned:

```text
STATUS: Ready
```

The current Kubernetes context can also be checked with:

```bash
kubectl config current-context
```

Expected Alpha cluster context:

```text
gke_starfleet-gke-platform-lab_us-central1-a_enterprise-gke-alpha
```

---

## Issue 2 — Navigation Pod ImagePullBackOff

### Symptom

After deploying the Navigation Service:

```bash
kubectl get pods -o wide
```

showed:

```text
READY   STATUS
0/1     ImagePullBackOff
```

### Investigation

Check Kubernetes events:

```bash
kubectl get events --sort-by=.lastTimestamp
```

Inspect the affected pod:

```bash
kubectl describe pod <pod-name>
```

The pod repeatedly failed while pulling the container image.

The image architecture was then inspected:

```bash
docker buildx imagetools inspect \
  us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:v0.1.0
```

The image reported:

```text
Platform: linux/arm64
```

Check the GKE node architecture:

```bash
kubectl get node \
  -o jsonpath='{.items[0].status.nodeInfo.architecture}{"\n"}'
```

The GKE node uses:

```text
amd64
```

### Root Cause

The Docker image was originally built on an Apple Silicon Mac.

Docker therefore produced a native:

```text
linux/arm64
```

image.

The GKE `e2-medium` node uses the `amd64` architecture.

The container image architecture therefore did not match the architecture
required by the GKE worker node.

### Resolution

Build a new image explicitly targeting `linux/amd64`.

A new version was used rather than overwriting the existing `v0.1.0` image:

```bash
docker buildx build \
  --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:v0.1.1 \
  --push \
  .
```

Verify the new image:

```bash
docker buildx imagetools inspect \
  us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:v0.1.1
```

Expected:

```text
Platform: linux/amd64
```

Update the Kubernetes Deployment:

```yaml
image: us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:v0.1.1
```

Update the application release metadata:

```yaml
- name: RELEASE_VERSION
  value: "v0.1.1"
```

Apply the deployment:

```bash
kubectl apply -f kubernetes/deployment.yaml
```

### Validation

```bash
kubectl get pods -o wide
```

The new application pod successfully entered:

```text
READY   STATUS
1/1     Running
```

This confirmed that GKE could successfully pull and execute the `amd64`
container image.

---

## Issue 3 — Pod Pending Due to Insufficient CPU

### Symptom

The Deployment requested two replicas, but one pod remained:

```text
STATUS: Pending
```

### Investigation

Check cluster events:

```bash
kubectl get events --sort-by=.lastTimestamp
```

Kubernetes reported:

```text
0/1 nodes are available: 1 Insufficient cpu.
```

Inspect the pod:

```bash
kubectl describe pod <pending-pod-name>
```

The initial application resource request was:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "250m"
    memory: "256Mi"
```

The lab cluster currently contains only one `e2-medium` worker node.

GKE system workloads also consume resources on this node.

### Root Cause

The single GKE worker node did not have sufficient allocatable CPU to
schedule all requested application pods in addition to existing GKE
system workloads.

### Resolution

For the cost-optimized lab environment, reduce the Navigation Service
CPU request:

```yaml
resources:
  requests:
    cpu: "50m"
    memory: "128Mi"
  limits:
    cpu: "250m"
    memory: "256Mi"
```

Apply the change:

```bash
kubectl apply -f kubernetes/deployment.yaml
```

### Validation

Monitor the deployment:

```bash
kubectl rollout status deployment/starfleet-navigation-service
```

Inspect pods:

```bash
kubectl get pods -o wide
```

Check events if scheduling problems continue:

```bash
kubectl get events --sort-by=.lastTimestamp
```

---

## Issue 4 — Rolling Update Temporarily Requires Additional Capacity

### Symptom

During the update from `v0.1.0` to `v0.1.1`, three pods were temporarily visible even though the Deployment requested only two replicas:

```text
Old ReplicaSet
└── Pod                         Running

New ReplicaSet
├── Pod                         Running
└── Pod                         Pending
```

### Explanation

Kubernetes Deployments use a rolling-update strategy by default.

During an update, Kubernetes can temporarily create a new pod before
terminating an old pod.

This helps maintain application availability during production
deployments, but it can temporarily require additional cluster capacity.

The lab cluster intentionally contains only one small worker node.

### Investigation

Inspect the Deployment:

```bash
kubectl get deployment starfleet-navigation-service
```

Inspect ReplicaSets:

```bash
kubectl get replicasets
```

Inspect pods:

```bash
kubectl get pods -o wide
```

Inspect scheduling events:

```bash
kubectl get events --sort-by=.lastTimestamp
```

Inspect the pending pod:

```bash
kubectl describe pod <pending-pod-name>
```

### Potential Lab Optimization

If additional temporary capacity continues to prevent rollouts, the
Deployment rolling-update strategy can be tuned for the constrained
single-node lab.

For example:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
```

This trades some rollout availability for lower temporary resource
requirements.

This setting should be evaluated differently for a production environment,
where maintaining application availability is normally more important than
minimizing temporary compute capacity.

---

## Useful Kubernetes Troubleshooting Commands

### Cluster

```bash
kubectl cluster-info
kubectl get nodes
kubectl get nodes -o wide
kubectl get pods -A
```

### Context

```bash
kubectl config current-context
```

### Applications

```bash
kubectl get deployments
kubectl get replicasets
kubectl get pods
kubectl get pods -o wide
```

### Detailed Pod Investigation

```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Events

```bash
kubectl get events --sort-by=.lastTimestamp
```

### Deployment Rollout

```bash
kubectl rollout status deployment/starfleet-navigation-service
kubectl rollout history deployment/starfleet-navigation-service
```

### Container Architecture

```bash
docker buildx imagetools inspect <image>
```

### GKE Node Architecture

```bash
kubectl get node \
  -o jsonpath='{.items[0].status.nodeInfo.architecture}{"\n"}'
```

---

## Lessons Learned

1. A healthy GKE cluster does not guarantee that the local `kubectl`
   client has the authentication components required to access it.

2. Container architecture matters when images are built on Apple Silicon
   and deployed to `amd64` cloud compute.

3. Kubernetes resource requests directly affect pod scheduling.

4. System workloads consume part of the node's available CPU and memory.

5. Rolling updates can temporarily require more resources than the
   steady-state application deployment.

6. Kubernetes events and `kubectl describe` should be checked before
   changing infrastructure or application configuration.

7. Versioned container tags make troubleshooting and rollback easier than
   relying on `latest`.
