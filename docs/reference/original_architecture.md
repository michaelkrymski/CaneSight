# Project Specification: AI-Assisted Smart Walking Stick (CaneSight)

## 1. Executive Summary
**CaneSight** is an assistive mobility platform designed for visually impaired pedestrians navigating complex urban crosswalks. It fuses edge sensor telemetry with cloud-accelerated computer vision to identify crosswalk locations, parse active pedestrian signal heads (walk vs. don't walk), count down remaining crossing seconds, and scan for crossing hazards like approaching vehicles.

The system combines a low-power edge computer (**Raspberry Pi Zero 2 W**), an embedded camera, local physical obstacle sensors, and directional haptic actuators with a high-throughput cloud inference engine running on **Vultr**.

---

## 2. Core Operational Workflow

```
[ Edge: Pi Zero 2 W ] 
      │ 
      ├─► (Local 50Hz Loop) VL53L1X ToF / Ultrasonic ──► Immediate Curb / Obstacle Alert
      ├─► (Local 50Hz Loop) MPU-6050 IMU ─────────────► Verifies Left-Right Sweep Gesture
      │
      └─► (1.0s Polled Loop) 416x416 Compressed JPEG
                │
                ▼ (HTTP/HTTPS via Mobile Hotspot)
[ Cloud Backend: Vultr GPU Instance ]
      │
      ├─► Stage 1: YOLOv8n / YOLO11n ──► Pedestrian Signal Head & Vehicle Detection
      ├─► Stage 2A: HSV / CNN Mask ────► Illuminated Hand vs. Walking Figure State
      ├─► Stage 2B: 7-Segment Parser ──► Active Crossing Seconds Remaining
      │
      ▼ (Telemetry JSON Response < 500B)
[ Edge: Pi Zero 2 W ]
      │
      ├─► Directional Haptics (Left / Right Handle Motors)
      └─► Low-Latency Audio Prompts (Pre-loaded WAV Files)
```

1. **Approach & Alignment:** The pedestrian approaches an intersection. The cane's camera captures frames, and the system guides alignment so the user faces perpendicular to the crosswalk.
2. **Safety Scan Sweep:** The user pans the cane left and right. The onboard IMU measures heading deviation ($\ge 60^\circ$ sweep) while the camera and cloud pipeline check for oncoming vehicles.
3. **Signal Acquisition:** Pointed forward, the system identifies the pedestrian signal head, parses the countdown timer and walk state, and alerts the user when it is safe to cross.
4. **Active Crossing Monitoring:** During crossing, low-latency local sensors continuously scan the ground for curbs, drops, or physical obstacles.

---

## 3. Hardware Architecture & Bill of Materials (BOM)

| Subsystem | Component | Interface | Purpose |
| :--- | :--- | :--- | :--- |
| **Compute Core** | Raspberry Pi Zero 2 W | — | Low-power client, capture management, telemetry polling |
| **OS** | Raspberry Pi OS Lite (64-bit) | — | Minimal headless footprint (~40–60 MB RAM baseline) |
| **Vision Input** | Pi Camera Module (CSI Ribbon) | CSI-2 | Captures $416\times416$ snapshot frames for transmission |
| **Spatial Heading** | MPU-6050 (or BNO055) 6-DOF IMU | $I^2C$ (`SDA`/`SCL`) | Tracks left/right scanning motion and cane angle |
| **Proximity Ranging**| VL53L1X ToF or HC-SR04 | GPIO / $I^2C$ | Zero-latency local curb, drop-off, and obstacle detection |
| **Haptic Feedback** | Dual ERM Coin Motors + 2N2222 | GPIO PWM | Directional physical alerts (left vs. right grip) |
| **Audio Output** | I2S DAC Breakout / Mono Speaker| I2S / USB | Auditory cues and status prompts |
| **Context Trigger** | Tactile Push Switch | GPIO Pull-up | Triggers on-demand Gemini environmental description |
| **Power System** | 5V 2.4A USB Power Bank | Micro-USB | Powers Pi Zero 2 W and peripherals |

---

## 4. Software & Computer Vision Pipeline

### 4.1 Client Layer (Raspberry Pi Zero 2 W)
* **Runtime:** Python 3.11+ running headlessly with `requests.Session()` over persistent HTTP keep-alive.
* **Camera Pipeline:** Frames captured into memory buffers (`io.BytesIO()`) at $416\times416$ resolution (JPEG quality 75%), avoiding flash storage wear and minimizing bandwidth to $\sim 25\text{ KB}$ per payload.
* **Failsafe Heartbeat:** If an HTTP response is not received within $2.5\text{ s}$, the system plays a failsafe disconnect tone and resets to a safe/stop state.

### 4.2 Cloud Inference Layer (FastAPI on Vultr)
* **Stage 1 (Object Localization):** A custom-trained **YOLOv8n / YOLO11n** model detects:
  * Pedestrian traffic signal heads
  * Static pedestrian crossing signs (MUTCD W11-2)
  * Vehicles (cars, trucks, buses)
* **Stage 2A (Symbol Discrimination):** Rather than using heavy detection heads for small symbols, the isolated signal box is evaluated via:
  * **Portland Orange / Red** mask: HSV ranges $(5, 120, 150)$ to $(22, 255, 255)$ $\rightarrow$ `Don't Walk (Hand)`
  * **Lunar White** mask: Low saturation, high brightness $(0, 0, 200)$ to $(180, 40, 255)$ $\rightarrow$ `Walk (Person)`
* **Stage 2B (Countdown OCR):** Cropped countdown windows are passed through a geometric 7-segment LED boolean intensity grid or CRNN digit classifier to read numeric crossing seconds.

---

## 5. Proposed Extra Features

1. **Dual Haptic Matrix (Directional Alerts):**
   * *Left Motor:* Hazard approaching from the left.
   * *Right Motor:* Hazard approaching from the right.
   * *Synchronous Rapid Buzz:* Immediate danger / emergency stop.
   * *Double Heartbeat Pulse:* Crosswalk clear / safe to cross.
2. **On-Demand Scene Context (Gemini API):**
   * A secondary button on the cane grip captures an uncompressed scene snapshot and sends it to `gemini-2.5-flash`.
   * Prompt: *"Describe immediate walking hazards, sidewalk conditions, or landmarks ahead in 20 words or less."*
   * Text is synthesized to voice for spatial context.
3. **Crosswalk Alignment Assist:**
   * Uses the bounding box horizontal centroid ($x_{\text{center}}$) of the target signal to guide the user to center themselves before stepping off the curb.
4. **Municipal Infrastructure & Safety Telemetry (Tiger Data):**
   * Every crossing event streams telemetry (`intersection_id`, `wait_time_sec`, `hazard_flags`, `signal_detected`) into a Tiger Data PostgreSQL database.
   * Enables continuous aggregate queries to map high-risk intersections and crosswalk wait times across city grids.

---

## 6. Hackathon Tracks Alignment (SwampHacks)

| Category / Sponsor | Feature Mapped | Prize Focus |
| :--- | :--- | :--- |
| **Best Use of Vultr** | FastAPI + YOLOv8n cloud backend deployed on Vultr Cloud GPU/Compute. | M5Stack Official Tab5 |
| **Best Use of Tiger Data** | Time-series crosswalk metrics and safety event logging stored in PostgreSQL. | Stream Deck Mini |
| **Best Use of Gemini API** | Tactile button triggering `gemini-2.5-flash` contextual environmental narration. | MLH Swag Kits |
| **Least Vibe Coded** | Embedded hardware-software co-design (Pi Zero 2 W, IMU, ToF, edge networking constraints). | Anker Docking Station (x4) |
| **Easy on the Eyes** | Web dashboard rendering live crosswalk telemetry and municipal hazard heatmaps. | Acer 27" Gaming Monitor (x4) |
| **DEV Writing Challenge**| Technical post-mortem on embedded ML edge-vs-cloud trade-offs for assistive devices. | $100 Prize |