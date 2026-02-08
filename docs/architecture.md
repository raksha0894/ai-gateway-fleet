# System Architecture – AI Gateway Fleet OTA

This document outlines the architecture and internal design of the
AI Gateway Fleet OTA (Over-The-Air) update system.

The system enables secure, resilient software updates and telemetry
aggregation in environments with intermittent connectivity.


## 1. High-Level Architecture

This system is built around two primary data pipelines:
1. Telemetry Pipeline – responsible for reliably collecting and forwarding operational metrics.
2. OTA Update Pipeline – responsible for securely delivering and installing software updates.	

Both pipelines are designed to function under unreliable network conditions and provide strong guarantees for correctness and durability.

### Telemetry Pipeline
```text
Central Server  <==== wan_net ====>   Gateway  <==== edge_net ====>  Robot
|                                       |                             |
|                                       |                             |
|                                       |                             |
Metrics <–––––––––––––––––   SQLite Telemetry DB <–––––––––––––––Telemetry Agent
                           (Store and Forward Mechanism)
```

#### Overview
The telemetry pipeline collects metrics from robots and delivers them reliably to the central server, even when connectivity is intermittent.
It uses a store-and-forward model.

#### Telemetry Flow
```text
Robot → Gateway → Dashboard (Central Server)
```
Gateways buffer data when WAN is unavailable.

#### Step-by-Step Flow

1. Metric Collection (Robot)
Each robot periodically generates telemetry:
1. CPU
2. Memory
3. Version
4. Health

This is sent to the gateway via:
POST /metrics

2. Local Persistence (Gateway – SQLite)
Upon receiving telemetry, the gateway:
1. Writes records to SQLite
2. Assigns timestamps
3. Marks records as pending

SQLite acts as a durable queue.
This prevents data loss during outages.


3. Forwarding to Central Server
The gateway runs a background forwarder that:
1. Reads pending records
2. Sends them to the dashboard
3. Marks successful sends
4. Deletes confirmed rows

If WAN is down, records remain stored.

#### Store-and-Forward Behavior
```text
Offline → Buffer → Reconnect → Flush
```
This ensures:
1. No metric loss
2. Ordered delivery
3. Crash-safe recovery

#### Failure Handling

| Failure Type   | Handling                         |
|----------------|----------------------------------|
| WAN Outage     | Local Buffering                  |
| Dashboard Down | Retry                            |                           
| Gateway restart| Resume from DB                   |


### OTA Update Pipeline
```text
Central Server  <==== wan_net ====>  Gateway  <============ edge_net ============>  Robot
   |                                  |                                               |
   |                                  |                                               |
   |<---------------------------------| poll manifest (every 30s)                     |
   |                                  |-- download + verify (checksum & cosign)       |
   |                                  |-- GC cache (Bounded)                          |
   |                                  |                                               |
   |                                  |<----------------------------------------------|  poll manifest (every 30s)
   |                                  |                                               |-- download + verify (cosign)
   |                                  |                                               |-- install (verification ✅)/rollback (verification ❌)
   |                                  |                                               | 
```
#### Overview

The OTA update pipeline is a pull-based, multi-stage process that delivers signed software artifacts from the cloud to robots via gateways.

It ensures:
1. End-to-end integrity
2. Authenticity verification
3. Fault tolerance
4. Automatic recovery

#### Update Flow

##### Online Update Flow

1. CI builds artifacts
2. Dashboard publishes OTA files
3. Gateway polls dashboard
4. Gateway downloads files
5. Gateway verifies signature
6. Gateway caches files
7. Robot polls gateway
8. Robot downloads files
9. Robot verifies files
10. Robot installs update

```text
Central Server → Gateway → Robot
```

##### Offline Update Flow

If WAN is unavailable:

1. Gateway serves cached artifacts
2. Robot downloads from Gateway
3. Robot verifies files
4. Robot installs update

```text
Gateway (cached) → Robot
```

Both Gateway and Robot components perform independent validation.

#### Step-by-Step Flow

1. Manifest Publication

The artifacts are published on the endpoint /dashboard/ota from the CI output directory and contains the following -
1. manifest.json
2. Compressed artifact (.tar.gz)
3. Cosign bundle
4. SHA256 checksum

```text
/dashboard/ota/
├── app-vX.Y.Z.tar.gz
├── app-vX.Y.Z.tar.gz.bundle
├── app-vX.Y.Z.sha256
└── manifest.json
```

This forms the authoritative release record.

2. Gateway Polling and Caching
The gateway periodically polls:
```text
GET /manifest
```
When a new version is detected:
1. Downloads artifact and bundle
2. Uses resumable downloads
3. Verifies checksum
4. Verifies signature (cosign)
5. Stores artifacts in local cache
6. Applies garbage collection

Only verified artifacts are cached.

The gateway acts as a trust boundary and distribution hub.

3. Robot Polling and Installation

The robot periodically polls the gateway enpoint (GET /manifest) for updates.

If a newer version exists:
1. Downloads artifacts from gateway
2. Resumes interrupted downloads
3. Verifies checksum
4. Verifies cosign signature
5. Extracts into NEW directory
6. Activates atomically
7. Runs self-test
8. Rolls back on failure

Updates are committed only after passing validation.

##### Atomicity and Rollback

The robot maintains three directories:

```text
NEW → CURRENT → OLD
```
This enables:
1. Instant rollback
2. Crash-safe upgrades

If any validation fails, the robot reverts automatically.

#### Failure Handling

| Failure Type        | Handling                         |
|---------------------|----------------------------------|
| Network loss        |	Resume + retry                   |
| Download error      | Backoff                          |
| Hash mismatch	      | Reject                           |
| Signature failure	  | Reject                           |
| Healthcheck failure |	Rollback                         |
| Repeated failure	  | Blacklist                        |

This ensures devices never enter broken states.

### Networks

| Network  | Purpose                         |
|----------|---------------------------------|
| wan_net  | Dashboard ↔ Gateway (Cloud/WAN) |
| edge_net | Gateway ↔ Robot (Local/Edge)    |


## 2. Component Responsibilities

### 2.1 Central Server

The Central Server is the source of truth for OTA updates.

Responsibilities:

1. Hosts OTA artifacts
2. Publishes version manifests
3. Exposes `/ota` endpoint for updates
4. Exposes `/status` endpoint for viewing the metrics on the dashboard

The artifact files are generated by CI scripts and signed using Cosign.


### 2.2 Gateway

The Gateway acts as an intermediary between cloud and robots.

Responsibilities:
1. Polls Dashboard for updates
2. Downloads OTA artifacts (resumable)
3. Verifies signatures
4. Manages local cache
5. Serves OTA files to robots
6. Supports offline operation

Cache layout:
```text
/app/cache/
├── app-v1.2.3.tar.gz
├── app-v1.2.3.bundle
└── manifest.json
```
#### Cache Management

Gateway cache is bounded by:

- Maximum size
- Maximum number of versions
- Garbage collection

Configuration:
```text
CACHE_KEEP_VERSIONS
CACHE_MAX_MB
CACHE_GC_INTERVAL
```
Garbage collection removes:

- Old versions
- Unused artifacts

Active verified version is always retained.
The robot(s) continue to update from this cache.

#### Resumable Downloads

Partial downloads are supported using HTTP Range on the Gateway.

Implementation:

- Downloads use `.part` files
- Resume from last byte
- Atomic rename on completion

Example:
```text
app-v1.2.3.tar.gz.part → app-v1.2.3.tar.gz
```
This enables recovery from network drops.

### 2.3 Robot

The Robot is the final update consumer.

Responsibilities:

- Polls Gateway
- Downloads artifacts
- Verifies checksum
- Verifies signature
- Installs software
- Handles rollback

Robot behavior:

- Periodic polling
- Offline-safe installation
- Automatic rollback on failure


#### Rollback Mechanism

Rollback is supported on the Robot.

Triggers:

- Installation failure
- Verification failure
- Runtime crash
- Network failure during update

Process:

1. Previous version retained
2. Failure detected
3. System reverts
4. Status reported

Rollback is automatic and requires no manual intervention.


#### Resumable Downloads

Partial downloads are supported using HTTP Range on the Robot too.

Implementation:

- Downloads use `.part` files
- Resume from last byte
- Atomic rename on completion

Example:
```text
app-v1.2.3.tar.gz.part → app-v1.2.3.tar.gz
```
This enables recovery from network drops.


## 3. Building and Signing Artifacts

OTA artifacts are built and signed using CI scripts.

Pipeline:

1. Read version
2. Package app
3. Generate checksum
4. Sign bundle
5. Generate manifest
6. Publish artifacts

## 4. Future enhancements:
1. Delta updates
2. Multi-robot orchestration
3. Fleet-level rollout policies
4. Canary deployments
5. Telemetry aggregation


