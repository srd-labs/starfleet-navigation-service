# GitHub Actions CI/CD -- Navigation Service

## Overview

The `starfleet-navigation-service` uses GitHub Actions to build,
security-scan, publish, and deploy the Navigation service to the Alpha
GKE cluster. The workflow uses `workflow_dispatch` so deployments occur
only when explicitly requested.

``` text
GitHub Actions
      |
      v
GitHub OIDC / GCP Workload Identity Federation
      |
      v
Build linux/amd64 image
      |
      v
Trivy HIGH/CRITICAL vulnerability gate
      |
      v
Artifact Registry (Git SHA tag)
      |
      v
GKE Alpha deployment
      |
      v
Rollout and pod validation
```

No long-lived Google Cloud service-account JSON key is stored in GitHub.

## Deployment Target

  Setting                        Value
  ------------------------------ ------------------------------------
  GCP project                    `starfleet-gke-platform-lab`
  Artifact Registry region       `us-central1`
  Artifact Registry repository   `starfleet-apps`
  Image                          `starfleet-navigation-service`
  GKE cluster                    `enterprise-gke-alpha`
  GKE zone                       `us-central1-a`
  Kubernetes deployment          `starfleet-navigation-service`
  Kubernetes container           `navigation-service`
  Pod selector                   `app=starfleet-navigation-service`

## Authentication Architecture

GitHub Actions authenticates to Google Cloud using OIDC and Workload
Identity Federation (WIF).

``` text
GitHub Actions
      |
      | OIDC token
      v
Workload Identity Provider
      |
      | impersonation
      v
github-actions-deployer GSA
      |
      +-- Artifact Registry
      |
      +-- GKE
```

### Workload Identity Pool

``` text
projects/232310545058/locations/global/workloadIdentityPools/github-actions
```

### Workload Identity Provider

``` text
projects/232310545058/locations/global/workloadIdentityPools/github-actions/providers/github
```

OIDC issuer:

``` text
https://token.actions.githubusercontent.com
```

The provider restricts authentication to
`srd-labs/starfleet-navigation-service` on the `main` branch.

## CI/CD Service Account

The workflow impersonates:

``` text
github-actions-deployer@starfleet-gke-platform-lab.iam.gserviceaccount.com
```

The repository identity receives `roles/iam.workloadIdentityUser`. The
CI/CD service account receives `roles/artifactregistry.writer` on
`starfleet-apps` and `roles/container.developer` for the GKE operations
required by this lab.

For production, GKE access should be narrowed with minimum Google Cloud
IAM permissions and workload-specific Kubernetes RBAC.

## GitHub Repository Secrets

`GCP_WORKLOAD_IDENTITY_PROVIDER`:

``` text
projects/232310545058/locations/global/workloadIdentityPools/github-actions/providers/github
```

`GCP_SERVICE_ACCOUNT`:

``` text
github-actions-deployer@starfleet-gke-platform-lab.iam.gserviceaccount.com
```

No service-account private key is required.

## Workflow Permissions

``` yaml
permissions:
  contents: read
  id-token: write
```

## Workflow Environment

``` yaml
env:
  PROJECT_ID: starfleet-gke-platform-lab
  REGION: us-central1
  GAR_REPOSITORY: starfleet-apps
  IMAGE_NAME: starfleet-navigation-service
  GKE_CLUSTER: enterprise-gke-alpha
  GKE_LOCATION: us-central1-a
```

## Container Build and Traceability

The image is explicitly built for `linux/amd64`, matching the GKE node
architecture.

Each image is tagged with the immutable Git commit SHA:

``` text
us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:<GITHUB_SHA>
```

This provides traceability from Git commit to container image to
deployed workload.

## Trivy Vulnerability Security Gate

Trivy scans the locally built image before publication. The scan checks
OS and application-library vulnerabilities and enforces:

``` yaml
severity: "HIGH,CRITICAL"
ignore-unfixed: true
exit-code: "1"
```

A qualifying HIGH or CRITICAL finding stops the pipeline before the
image is pushed.

### pip Vendored SBOM Finding

During implementation, Trivy reported:

``` text
msgpack     1.1.2
setuptools  70.3.0
```

Verification inside the exact built image showed:

``` text
msgpack: 1.2.2
setuptools: 84.0.0
```

The older versions were discovered through pip's vendored CycloneDX SBOM
rather than the application's installed runtime package versions.

The narrow metadata exclusion used by the pipeline is:

``` yaml
skip-files: "/usr/local/lib/python3.13/site-packages/pip/_vendor/bom.cdx.json"
```

The HIGH/CRITICAL security gate remains enabled.

## Artifact Registry

Only an image that passes the vulnerability gate is pushed to:

``` text
us-central1-docker.pkg.dev/starfleet-gke-platform-lab/starfleet-apps/starfleet-navigation-service:<GITHUB_SHA>
```

## GKE Deployment

The workflow obtains short-lived credentials for `enterprise-gke-alpha`
in `us-central1-a` and updates the existing Navigation deployment:

``` bash
kubectl set image deployment/starfleet-navigation-service \
  navigation-service="<SHA-TAGGED-IMAGE>"
```

## Deployment Validation

The workflow waits for the rolling deployment:

``` bash
kubectl rollout status deployment/starfleet-navigation-service --timeout=180s
```

It then displays the resulting pods:

``` bash
kubectl get pods -l app=starfleet-navigation-service -o wide
```

## Validated Pipeline

  Stage                                Status
  ------------------------------------ --------
  Manual `workflow_dispatch` trigger   PASS
  GitHub OIDC                          PASS
  Workload Identity Federation         PASS
  GCP service-account impersonation    PASS
  Artifact Registry authentication     PASS
  linux/amd64 image build              PASS
  Trivy HIGH/CRITICAL security gate    PASS
  SHA-tagged Artifact Registry push    PASS
  Alpha GKE authentication             PASS
  Navigation deployment update         PASS
  Kubernetes rollout verification      PASS

## Troubleshooting -- WIF Service Account Impersonation

### Symptom

Authentication initially failed with:

``` text
Permission 'iam.serviceAccounts.getAccessToken' denied
```

### Investigation and Root Cause

The IAM Service Account Credentials API, WIF pool/provider,
repository/ref claims, principal binding, and
`roles/iam.workloadIdentityUser` assignment were verified. Using the
exact service-account email directly in the workflow succeeded.

The GitHub secret `GCP_SERVICE_ACCOUNT` contained an incorrect or
malformed value.

### Resolution

The secret was recreated with:

``` text
github-actions-deployer@starfleet-gke-platform-lab.iam.gserviceaccount.com
```

WIF authentication then succeeded.

### Lesson Learned

Validate identity values before expanding IAM permissions. The WIF
provider resource used by the workflow and the IAM `principalSet` are
different values serving different purposes.

## Troubleshooting -- Trivy Vendored Package Findings

### Symptom

Trivy continued to report vulnerable `msgpack` and `setuptools` versions
after the application packages were upgraded.

### Verification and Resolution

The runtime image reported `msgpack 1.2.2` and `setuptools 84.0.0`. The
older package information was found in pip's vendored CycloneDX
metadata.

Only the specific pip SBOM metadata file was excluded. The HIGH/CRITICAL
vulnerability gate remained active.

### Lesson Learned

Scanner findings should be investigated rather than globally suppressed.
A narrow, documented exclusion is preferable to disabling the security
gate.

## Security Controls

  Control                    Implementation
  -------------------------- -----------------------------------------
  Long-lived GCP JSON key    Not used
  Cloud authentication       GitHub OIDC + GCP WIF
  Repository restriction     `srd-labs/starfleet-navigation-service`
  Branch restriction         `main`
  Dedicated CI/CD identity   `github-actions-deployer`
  Artifact publishing        Artifact Registry writer
  Image architecture         Explicit `linux/amd64`
  Image traceability         Git commit SHA
  Vulnerability scanning     Trivy
  Security gate              HIGH / CRITICAL
  Deployment target          Alpha GKE
  Deployment verification    Rollout status + pod status

## Production Recommendations

For production, consider tighter Kubernetes RBAC instead of the lab's
`roles/container.developer`, protected branches and deployment
approvals, immutable action-version pinning, retained SBOM artifacts,
signed image attestations with Binary Authorization, separate deployment
identities per environment, automated rollback, and post-deployment
health checks.

## Current Status

Navigation GitHub Actions CI/CD is implemented and validated for the
Alpha GKE cluster:

``` text
Source revision
      |
      v
linux/amd64 build
      |
      v
Trivy security gate
      |
      v
SHA-tagged Artifact Registry image
      |
      v
GKE Alpha deployment
      |
      v
Rollout verification
```

This completes the Navigation service GitHub Actions CI/CD
implementation for the current lab scope.
