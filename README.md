# AI Gateway Fleet – OTA Update Demo

This project demonstrates a secure Over-The-Air (OTA) update system for robot fleets,
including artifact signing, resumable downloads, offline recovery, and rollback safety.


## 📦 Architecture Overview

The system consists of:

- **Gateway** – Manages OTA downloads, verification, and caching
- **Robot** – Verifies and applies updates and reports metrics
- **Dashboard** – Displays fleet metrics
- **Central Server** – Hosts signed artifacts

All OTA artifacts are signed and verified before installation.


## ⚙️ Prerequisites

Ensure the following are installed for running the demo.sh script -
- Linux (Ubuntu 20.04+ recommended ) / Windows (with WSL2)
- Docker (v20+)
- Docker Compose (v2+)
- Bash (v4+)
- curl

Additionally, for rebuilding artifacts -
- cosign
- signing key
- COSIGN_PASSWORD

Note:
cosign is bundled inside containers and is NOT required on the host
when using prebuilt artifacts (default demo mode).


## 🚀 Quick Start (Recommended)
1. First clone the git repository
git clone https://github.com/raksha0894/ai-gateway-fleet.git
cd ai-gateway-fleet
2. Execute the following command -
```text
./scripts/demo.sh
```
Note: Use pre-built signed OTA artifacts (no secrets required). In some environments file ownership for mounted volumes need to be fixed using the following command -
```text
sudo chown -R $USER:$USER ./dashboard
```

Alternatively, if one wants to build & sign artifacts additionally - be sure to have the cosign.key in the /keys folder. Then execute the following command -
```text
COSIGN_PASSWORD=<password> ./scripts/demo.sh --rebuild
```

## 🧪 Demo Scenario
The demo simulates the following scenario: 
1. Gateway initially offline.
2. Central publishes new version.
3. Gateway comes online, downloads package, goes offline again.
4. Robot requests update from gateway and installs it.
5. Gateway reconnects later and forwards metrics to dashboard.
6. Dashboard shows the robot’s updated version and health.







