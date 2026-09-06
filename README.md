# 🚨 V2X Emergency Signal Preemption Simulator

A traffic simulation system built using **SUMO (Simulation of Urban MObility)** and controlled via Python's **TraCI API**. This project demonstrates and compares the performance of **Vehicle-to-Infrastructure (V2I)** emergency signal preemption under different network technologies: **5G URLLC** (Ultra-Reliable Low-Latency Communication), **4G LTE**, and a **Baseline** system with no preemption.

---

## 📌 Project Overview
When emergency vehicles (EVs) like ambulances get stuck in urban traffic congestion or at red lights, critical seconds are lost. V2I signal preemption allows an approaching EV to broadcast a priority request to the local traffic light controller, commanding it to turn green in its direction.

This project evaluates the performance trade-offs of this technology and compares three scenarios:
1. **5G URLLC (Direct PC5 Sidelink):** Leverages direct device-to-device communication with high range, near-zero latency, and high reliability.
2. **4G LTE (Cloud-Routed):** Priority requests are routed through cellular base stations to a remote cloud server, then back down to the traffic light, introducing higher network latency and range limits.
3. **Baseline:** Standard pre-timed/scheduled traffic signal schedules where the ambulance receives no priority.

---

## ⚙️ Technical Comparison

| Feature / Metric | 🔴 Baseline (No Preemption) | 🟡 4G LTE (Cloud-Routed) | 🟢 5G URLLC (Direct PC5 Sidelink) |
| :--- | :--- | :--- | :--- |
| **V2I Communication** | None | Cellular Uplink/Downlink + Cloud | Direct Sidelink (PC5 Interface) |
| **Average Latency** | — | **50 ms** (with jitter & packet drop penalty) | **2 ms** (Guaranteed low-latency) |
| **Reliable V2I Range** | — | **40 meters** (due to cloud routing & cell limits) | **100 meters** (direct line-of-sight range) |
| **Preemption Trigger Time** | — | Late (approx. 2.4s before arrival) | Early (approx. 6s before arrival) |
| **Yellow Clearance Impact** | — | EV must slow down/stop while yellow clears | Yellow clears *before* EV arrives; crosses at full speed |
| **EV Stopped Delay** | High (~5.2s) | Low (~1.1s due to brief stop/slowdown) | **0.0 seconds** (Perfect preemption) |
| **Civilian Traffic Delay** | Lowest | Medium | Optimized (restores normal flow immediately) |

### 🔍 The Core Technical Insight: Latency vs. Clearance Phase
In an interview or technical review, a common question is: *If 4G latency is 50ms and 5G is 2ms, why does 5G perform so much better? Both network delays are small fractions of a second.*

The difference lies in **reliable communication range** combined with traffic light **safety yellow clearance phases**:
* **Traffic Safety Rule:** When a traffic light receives a preemption request, it cannot instantly turn green for the ambulance. It must transition through a **4.0-second yellow clearance phase** to let cross-street civilian vehicles safely clear the intersection.
* **The 5G Advantage:** With a **100m communication range** (direct PC5 sidelink), the 5G system registers the preemption request about **6.0 seconds** before the ambulance reaches the junction. This allows the 4.0-second yellow phase to complete *before* the ambulance arrives, enabling it to cross at full speed (60 km/h) without stopping.
* **The 4G Bottleneck:** Due to cellular localization and routing limits, 4G has a reliable range of only **40m** in this simulation. The preemption request is received only **2.4 seconds** before the ambulance arrives. Consequently, the 4.0-second yellow phase is still active when the ambulance reaches the stop line, forcing it to brake and lose momentum.

---

## 📂 Project Directory Structure
* **`app.py`**: A modern **Streamlit** dashboard serving as the user interface. It lets users configure parameters (traffic density, latencies, packet loss), trigger simulations, and review detailed comparison metrics and charts.
* **`simulation_engine.py`**: The simulation runner that initiates SUMO, starts TraCI, runs the multi-intersection scenario (corridor with intersections `c1` and `c2`), executes real-time preemption logic, and collects statistics.
* **`v2x_emergency_sim.py`**: A simpler, standalone command-line / GUI script demonstrating single-intersection V2I preemption. It prompts the user for the network profile (4G or 5G) and displays an in-simulation HUD overlay.
* **`generate_pdf.py`**: Generates a professional technical report PDF (`V2X_Project_Explanation.pdf`) using ReportLab, covering key concepts and interview preparation questions.
* **`network/`**:
  * **`generate_network.py`**: Programmatically generates SUMO node (`.nod.xml`), edge (`.edg.xml`), route (`.rou.xml`), and configuration (`.sumocfg`) files based on civilian traffic density.
  * `network.net.xml`, `routes.rou.xml`, `sumo.sumocfg`: Generated files representing the double-intersection road network and traffic flows.

---

## 🛠️ Installation & Setup

### 1. Install SUMO
This simulator requires **SUMO (Simulation of Urban MObility)** to run.
* **Windows:** Download and run the installer from the [SUMO Download Page](https://sumo.dlr.de/docs/Downloads.php).
* **Environment Variable:** Ensure that `SUMO_HOME` is added to your system environment variables pointing to your SUMO installation directory (e.g., `C:\Program Files (x86)\Eclipse\Sumo`).

### 2. Clone and Install Dependencies
Install the required Python packages:
```bash
pip install streamlit pandas numpy plotly reportlab traci
```

---

## 🚀 How to Run

### Option A: The Streamlit Web Dashboard (Recommended)
Launch the interactive web dashboard to run simulations and compare profiles:
```bash
streamlit run app.py
```
* Once loaded, select **Batch — Run All 3** or individual modes.
* Adjust **Traffic Density**, **Network Latency**, and **Packet Loss** parameters in the sidebar.
* Toggle the **Launch SUMO GUI window** checkbox to watch the simulation run in real-time or run it headlessly for faster results.

### Option B: Standalone Single-Intersection CLI/GUI Simulator
Run the standalone, single-intersection visualization directly:
```bash
python v2x_emergency_sim.py
```
* Select `4G` or `5G` in the command prompt.
* A SUMO-GUI window will open, showing a live dashboard overlay (HUD) tracking preemption wave pulses, EV speed, distance, and stopped delay.

### Option C: Generate the Explanatory PDF
Compile the comprehensive technical summary and Q&A handbook:
```bash
python generate_pdf.py
```
This generates the file `V2X_Project_Explanation.pdf` in the root folder.

---

## 📊 Performance Metrics Tracked
* **Emergency Vehicle Travel Time (s):** Total time taken by the ambulance to traverse the entire corridor.
* **Stopped Delay (s):** Cumulative time the ambulance spent at a complete stop (speed < 0.1 m/s) due to red lights or traffic blocks.
* **Average Speed (km/h):** The average speed profile of the ambulance across its route.
* **Civilian Traffic Delay (s):** Cumulative waiting time of civilian vehicles. This tracks the trade-off of preemption (giving priority to the ambulance temporarily halts cross-street civilian traffic).
* **V2I Network Latency Jitter (ms):** Statistical distribution of V2I network round-trip packet latency including retransmissions.
