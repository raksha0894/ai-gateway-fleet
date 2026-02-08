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
./scripts/demo.sh
Note: Use pre-built signed OTA artifacts (no secrets required)
Note: In some environments file ownership for mounted volumes need to be fixed using (sudo chown -R $USER:$USER ./dashboard)

Alternatively, if one wants to build & sign artifacts additionally - be sure to have the cosign.key in the /keys folder. Then execute the following command -
COSIGN_PASSWORD=<password> ./scripts/demo.sh --rebuild

## 🧪 Demo Scenario
The demo simulates the following scenario: 
a. Gateway initially offline.
b. Central publishes new version.
c. Gateway comes online, downloads package, goes offline again.
d. Robot requests update from gateway and installs it.
e. Gateway reconnects later and forwards metrics to dashboard.
f. Dashboard shows the robot’s updated version and health.




