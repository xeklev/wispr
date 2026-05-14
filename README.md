# WISPR CSI Motion Tracker

![System Design](<System Design.png>)

This repository contains the firmware and host software for a dual-node WiFi Channel State Information (CSI) motion tracking system. The system uses two ESP32 nodes to detect and visualize human presence and movement direction.

## Hardware Components (Per WISPR Node)
Each standalone WISPR node is built with the following hardware:
* **ESP32-U** (with an external antenna for improved signal stability)
* **18650 Battery** * **TP4056 Charging Module**
* **MT3608 Boost Converter** (Used to step up the battery voltage to power the 5V rail on the ESP32)
* **SSD1306 OLED Display**
* [cite_start]**Config Reset Switch** (Wired to GPIO 17 [cite: 73])

## Software Overview

### 1. `main.ino` (ESP32 Firmware)
The firmware responsible for capturing CSI data and streaming it to your computer.
* **Captive Portal Setup:** On first boot, the node hosts an access point (`WISPR CSI-Setup`). [cite_start]Connect to it to configure your local WiFi credentials, the Host PC's IP address, and the target UDP port[cite: 68, 69].
* [cite_start]**NVS Storage:** Configurations are saved to non-volatile storage, meaning they survive reboots and power cycles[cite: 5, 11].
* [cite_start]**UDP Streaming:** Streams binary CSI packets to the target IP at roughly 50Hz[cite: 49, 93].
* [cite_start]**Factory Reset:** Holding the reset switch for 3 seconds clears the NVS and WiFi config, restarting the device in setup mode[cite: 84, 85].

### 2. `main.py` (Host Visualization)
The Python script that receives the UDP streams and visualizes the data.
* **Dual-Node Tracking:** Listens concurrently on UDP port `8001` (Node A) and `8000` (Node B).
* **Data Processing:** Extracts a normalized single-digit feature from the CSI subcarriers and uses a streak-based hysteresis system to reliably trigger presence detection.
* **Direction Inference:** Analyzes the timing and amplitude differences between the two nodes to determine the direction of travel.
* **Visual Interfaces:** Launches a dual-heatmap dashboard using Matplotlib for raw data analysis, alongside a Tkinter window featuring an animated "stickman" that visually tracks movement between the nodes.

## How to Run
1. Flash `main.ino` to both of your ESP32-U devices.
2. Power on the nodes. Connect to their individual `WISPR CSI-Setup` WiFi networks to enter your router's credentials and your PC's IP address. Set one node to target port `8001` and the other to `8000`.
3. On your host PC, install the necessary dependencies (e.g., `pip install numpy matplotlib`).
4. Run `python main.py`. The script will wait for incoming packets from both nodes before launching the visualizers.
