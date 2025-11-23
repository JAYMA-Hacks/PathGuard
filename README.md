# PathGuard

> AI-powered smart pedestrian safety and hazard reporting system using edge devices and cloud intelligence.

Built for **Hack the Change 2025** by **Team Sudo Bash Bros**.

**Live prototype (map UI):** https://path-guard.vercel.app  

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Core components](#core-components)
  - [1. AI Camera Node (ESP32-CAM + YOLOv8)](#1-ai-camera-node-esp32-cam--yolov8)
  - [2. Hazard Kiosk (Arduino UNO R4 WiFi)](#2-hazard-kiosk-arduino-uno-r4-wifi)
  - [3. Cloud Backend (AWS)](#3-cloud-backend-aws)
  - [4. Web Dashboard (React)](#4-web-dashboard-react)
- [Getting started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Clone the repo](#clone-the-repo)
- [Running each part](#running-each-part)
  - [AI Model / people counter](#ai-model--people-counter)
  - [ESP32-CAM firmware](#esp32-cam-firmware)
  - [Arduino UNO R4 WiFi hazard kiosk](#arduino-uno-r4-wifi-hazard-kiosk)
  - [React web dashboard](#react-web-dashboard)
- [Configuration](#configuration)
  - [.env for AI Model](#env-for-ai-model)
  - [`secrets.h` for Arduino kiosk](#secretsh-for-arduino-kiosk)
- [Project status & limitations](#project-status--limitations)
- [Team](#team)

---

## Overview

**PathGuard** is a smart pedestrian safety system designed for crosswalks, shared paths, and high-risk crossings, especially in winter conditions.

The system combines:

- An **AI camera node** that counts pedestrians and estimates congestion using YOLOv8.
- A **physical hazard kiosk** where pedestrians can report hazards (e.g., ice, potholes) via joystick + LCD.
- An **AWS backend** that stores events and can fan out alerts via Amazon SNS.
- A **React map dashboard** that (prototype) visualizes congestion and hazards.

The goal is to give cities **real-time visibility** into what pedestrians are experiencing on the ground: **crowding near crossings** and **self-reported hazards** like icy surfaces, debris, or broken lights.

---

## Architecture

High-level data flow:

1. **ESP32-CAM** streams video from the crosswalk.
2. A **laptop/edge computer** runs YOLOv8n on the stream, tracks people, and computes a 5-minute rolling average of pedestrian counts.
3. Once per minute, the laptop sends a **minimal “congestion” record** (low / med / high) to an AWS API (CityIngest → DynamoDB).
4. Nearby, an **Arduino UNO R4 WiFi kiosk** lets pedestrians scroll a hazard menu and submit self-reports (e.g. “Icy surface”). Each report is POSTed to another AWS API (HazardIngest → DynamoDB + SNS).
5. A **CityRead API** exposes congestion + hazard records for frontend clients.
6. The **React dashboard** shows a map with congestion status and (planned) hazard markers.

---

## Repository structure

At the root of this repo:

```text
PathGuard/
├─ AI Model/             # Python YOLOv8 people-counter and congestion publisher
├─ ArduinoR4_HMI/        # Arduino UNO R4 WiFi hazard-report kiosk firmware
├─ ESP32 Wrover Module/  # PlatformIO project for ESP32-CAM camera server
├─ pathguard-web/        # React-based web dashboard (map UI prototype)
├─ .vscode/              # Editor / workspace settings
├─ .gitignore
├─ README.md             # (this file)
└─ package.json          # Root npm metadata / scripts (if used)
```

> Note: AWS infrastructure (Lambdas, DynamoDB table definitions, etc.) is **deployed separately** and not stored as IaC in this repository.

---

## Core components

### 1. AI Camera Node (ESP32-CAM + YOLOv8)

- **Hardware:**
  - ESP32-CAM board (Wrover module variant).
- **Firmware (this repo):**
  - Located under `ESP32 Wrover Module/`
  - Based on the classic `camera_web_server` example.
  - Exposes:
    - `http://<cam-ip>/` – camera web UI.
    - `http://<cam-ip>:81/stream` – MJPEG video stream.
    - `http://<cam-ip>/capture` – single JPEG snapshot.
- **AI side (Python):**
  - Located under `AI Model/`.
  - Uses **YOLOv8n** (Ultralytics, pretrained on COCO) to detect class `person` on frames pulled from the ESP32-CAM.
  - Uses **ByteTrack** (via the `supervision` library) to maintain stable tracking IDs.
  - Maintains a rolling 5-minute window of pedestrian counts and computes a **congestion level**:
    - Low / Medium / High (thresholds configurable via environment variables).
  - Once per minute, pushes a minimal record to an AWS API:

    ```json
    {
      "item_type": "congestion",
      "id": 123,
      "lng": -114.1594,
      "lat": 51.0189,
      "type": "congestion",
      "val": "low"
    }
    ```

### 2. Hazard Kiosk (Arduino UNO R4 WiFi)

- **Hardware:**
  - Arduino UNO R4 WiFi.
  - 16x2 LCD (LiquidCrystal).
  - Joystick (Y axis + center push).
  - Ultrasonic distance sensor.
  - Alert LED.
  - Extra “report” button.

- **Pins (as used in the sketch):**
  - LCD: `RS=7`, `EN=8`, `D4=9`, `D5=10`, `D6=11`, `D7=12`.
  - Joystick: `JOY_Y = A0`, `JOY_SW = 4` (with `INPUT_PULLUP`).
  - Ultrasonic: `TRIG_PIN = 2`, `ECHO_PIN = 3`.
  - Alert LED: `ALERT_LED = 13`.
  - Extra OK button: `BTN_PIN = 5` (with `INPUT_PULLUP`).

- **LCD UI flow:**
  - **DEMO mode**
    - Line 1: `Lest we Forget.`
    - Line 2: scrolling “Press joystick to report hazard…”.
  - **MENU mode**
    - User scrolls through:

      ```text
      Pothole
      Icy surface
      Debris
      Fallen sign
      Construction
      Flooded
      Poor lighting
      Broken light
      Other
      ```

    - Press joystick or extra button to select.
  - **THANKYOU mode**
    - Short “Thank you!” screen after successful POST.

- **Ultrasonic logic:**
  - Polls distance roughly every 100 ms.
  - If `distance < ALERT_DISTANCE` (e.g. 40 cm) → sets an active alert window.
  - During alert window (~5 seconds), `ALERT_LED` blinks every 250 ms to indicate a pedestrian detected near the crossing.

- **Networking:**
  - Uses `WiFiS3` + `ArduinoHttpClient`.
  - Builds a `self_report` JSON payload and POSTs it to an AWS **HazardIngest** API over HTTPS:

    ```json
    {
      "item_type": "self_report",
      "area_id": "heritage_park",
      "source": "kiosk",
      "device_id": "kiosk-r4-01",
      "report_category": "Debris",
      "location_name": "Heritage Park – North",
      "lat": 51.018900,
      "lon": -114.159400
    }
    ```

  - API key, WiFi credentials, and endpoint (host/path) are set in a `secrets.h` file (not committed).

### 3. Cloud Backend (AWS)

*(Architecture-level description; Lambda source code is not part of this repo.)*

- **API Gateway + Lambda:**
  - `CityIngest` – receives:
    - `item_type = "congestion"` (from AI camera node).
    - Optional crowd rollup types (`crowd_avg_5m`, `crowd_minute`).
    - `item_type = "self_report"` in some designs.
  - `HazardIngest` – receives:
    - `item_type = "self_report"` hazard reports from kiosks.
  - `CityRead` – read-only APIs for frontend:
    - `GET /records` – global feed (by date).
    - `GET /records/by-area` – filter by `area_id`.

- **Storage:**
  - DynamoDB tables such as:
    - `CityEvents` – congestion + crowd events.
    - `CityHazards` – hazard self-reports.
    - `Area` – lookup table for area names, route codes, optional SNS topic overrides.

- **Notifications (optional):**
  - Amazon SNS topic for **email alerts**:
    - On new hazard report → SNS message with subject like:  
      `[RouteCode] Debris @ Heritage Park – North`.

### 4. Web Dashboard (React)

- Located in `pathguard-web/`.
- Built as a **React** map dashboard (deployed to Vercel at `path-guard.vercel.app`).
- Intended to:
  - Call `CityRead` APIs (via API Gateway) with an API key.
  - Plot congestion status at locations.
  - Show hazard markers and recent reports.
- **Note:** For the hackathon timeframe, the dashboard is a **prototype** and not all endpoints / views are fully wired to live data.

---

## Getting started

### Prerequisites

To work with all parts of PathGuard you’ll need:

- **General**
  - Git
  - A modern OS (Linux, macOS, or Windows)

- **AI Model / Python**
  - Python 3.9+  
  - `pip` and `python -m venv`
  - A machine with a GPU is helpful but not required (YOLOv8n can run on CPU at low FPS).

- **ESP32-CAM**
  - [PlatformIO](https://platformio.org/) or Arduino IDE with ESP32 core installed.
  - ESP32-CAM board and USB-UART adapter.

- **Arduino UNO R4 WiFi**
  - Arduino IDE 2.x with **UNO R4** support.
  - UNO R4 WiFi board and basic electronics (LCD, joystick, ultrasonic).

- **Web frontend**
  - Node.js (LTS) and npm / pnpm / yarn.

- **Cloud (optional but recommended)**
  - AWS account.
  - DynamoDB, Lambda, API Gateway, and SNS set up to match the expected endpoints & payloads.

### Clone the repo

```bash
git clone https://github.com/JAYMA-Hacks/PathGuard.git
cd PathGuard
```

---

## Running each part

### AI Model / people counter

1. **Go to the AI Model folder:**

   ```bash
   cd "AI Model"
   ```

2. **Create a virtual environment and install deps:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scriptsctivate

   pip install -r requirements.txt
   ```

3. **Create a `.env` file** (see [Configuration](#env-for-ai-model) below) with:
   - ESP32-CAM base URL.
   - YOLO model path / thresholds.
   - AWS API endpoint + API key.
   - Lat/Lon of your test location.

4. **Run the people counter script** (name may differ slightly; typically):

   ```bash
   python people_counter.py
   ```

   - The script will:
     - Connect to `CAM_BASE_URL` stream or `/capture`.
     - Run YOLOv8n on incoming frames.
     - Use ByteTrack to maintain IDs.
     - Once per minute, log and send a congestion record to AWS.

### ESP32-CAM firmware

1. **Open the project** in PlatformIO or VS Code:

   - Folder: `ESP32 Wrover Module/`

2. **Configure Wi-Fi SSID/PASS**:

   - In the main config file (e.g. the `camera_web_server` sketch), update your WiFi credentials if needed.

3. **Build and upload**:

   - Connect your ESP32-CAM via USB-UART.
   - Select the correct board/port.
   - Upload the firmware.
   - Open Serial Monitor to capture the assigned IP address.

4. **Verify**:

   - Visit `http://<cam-ip>/` in a browser.
   - Confirm:
     - `/` web UI works.
     - `:81/stream` returns MJPEG.
     - `/capture` returns single JPEG frames.

5. **Update `.env` in AI Model** with the correct `CAM_BASE_URL`.

### Arduino UNO R4 WiFi hazard kiosk

1. **Open the Arduino sketch**:

   - Folder: `ArduinoR4_HMI/`
   - Open the main `.ino` file in Arduino IDE.

2. **Create `secrets.h`** in the same folder (this file is git-ignored), with content along the lines of:

   ```cpp
   #pragma once

   #define WIFI_SSID   "YourWifiSSID"
   #define WIFI_PASS   "YourWifiPassword"

   #define AWS_HOST    "your-api-id.execute-api.ca-west-1.amazonaws.com"
   #define AWS_PORT    443
   #define AWS_PATH    "/hazards/ingest"
   #define AWS_API_KEY "your-api-gateway-key"
   ```

3. **Wire the hardware** following the pin assignments listed in  
   [2. Hazard Kiosk (Arduino UNO R4 WiFi)](#2-hazard-kiosk-arduino-uno-r4-wifi).

4. **Upload the sketch** to the UNO R4 WiFi.

5. **Test flow**:

   - On power up you should see:
     - Demo screen: “Lest we Forget.” + scrolling “Press joystick to report hazard…”.
   - Press joystick to enter menu.
   - Scroll to a hazard (e.g. “Icy surface”) and press joystick or button.
   - LCD shows “Sending…” and then “Thank you!” (on success).
   - Check AWS logs / Dynamo / SNS for a new `self_report` item.

### React web dashboard

1. **Enter the web folder**:

   ```bash
   cd pathguard-web
   ```

2. **Install dependencies**:

   ```bash
   npm install
   # or
   pnpm install
   ```

3. **Start development server**:

   ```bash
   npm run dev
   # or whatever script is defined in package.json
   ```

4. **Configure API access**:

   - Update environment variables or config files inside `pathguard-web` to point to your `CityRead` endpoint and include the required API key.
   - By default, the Vercel deployment at `path-guard.vercel.app` is wired to the team’s own backend; you can adapt it for your own.

---

## Configuration

### .env for AI Model

Create `AI Model/.env` with keys similar to:

```ini
# ESP32 camera
CAM_BASE_URL=http://192.168.4.123
STREAM_PATH=:81/stream
CAPTURE_PATH=/capture

# YOLO model
MODEL_PATH=yolov8n.pt
CONF_THRESH=0.35
IOU_THRESH=0.45
IMG_SIZE=640

# Rolling window & tracking
ROLL_MIN_5=5
REENTRY_GRACE_S=45

# Location of this camera node
LAT=51.0189
LON=-114.1594

# AWS congestion ingest
AWS_API=https://your-api-id.execute-api.ca-west-1.amazonaws.com/ingest
AWS_API_KEY=your-api-gateway-key
POST_TIMEOUT_S=10

# Local state for incrementing record IDs
ID_STATE_FILE=.map_id
```

Adjust as needed for your environment (camera IP, thresholds, lat/lon, API URL, etc.).

### secrets.h for Arduino kiosk

Create `ArduinoR4_HMI/secrets.h` (not committed):

```cpp
#pragma once

#define WIFI_SSID   "YourWifiSSID"
#define WIFI_PASS   "YourWifiPassword"

#define AWS_HOST    "your-api-id.execute-api.ca-west-1.amazonaws.com"
#define AWS_PORT    443
#define AWS_PATH    "/hazards/ingest"
#define AWS_API_KEY "your-api-gateway-key"
```

If you deploy to a different region or path, update `AWS_HOST` and `AWS_PATH` accordingly.

---

## Project status & limitations

- This is a **hackathon prototype**, not a production system.
- The **React dashboard** is partially integrated; some views may use mock data or require additional wiring to `CityRead`.
- The AI pipeline uses **YOLOv8n on CPU by default**, which is fine for low-FPS counting but not high-frame-rate analytics.
- Fault tolerance, security hardening, and large-scale deployment considerations (multi-camera, multi-area) are out of scope for this initial version.

---

## Team

**PathGuard – Hack the Change 2025**

- @yassinsolim  
- @elitetq  
- @AbdulWQ
- @mujtaba-zia
- @AFFAN606

If you have questions or want to build on PathGuard, feel free to open an issue or reach out to the contributors on GitHub.
