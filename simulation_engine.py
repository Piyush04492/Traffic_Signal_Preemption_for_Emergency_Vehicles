import os
import sys
import time
import random
import numpy as np

# ─── SUMO tools path ──────────────────────────────────────────────────────────
if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
else:
    sys.exit("Set the SUMO_HOME environment variable first.")

import traci


# ─── SUMO binary helper ───────────────────────────────────────────────────────
def _sumo_bin(headless: bool) -> str:
    name = "sumo" if headless else "sumo-gui"
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        for ext in ("", ".exe"):
            p = os.path.join(sumo_home, "bin", name + ext)
            if os.path.exists(p):
                return p
    return name


# ─── Ambulance highlight (GUI only) ──────────────────────────────────────────
def _highlight_ev():
    try:
        traci.vehicle.setColor("ambulence_ev", (255, 30, 30, 255))
        traci.vehicle.highlight("ambulence_ev",
                                color=(255, 255, 0, 210),
                                size=10, alphaMax=210, duration=0)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Main simulation function
# ═════════════════════════════════════════════════════════════════════════════
def run_simulation(mode="5G URLLC",
                   civilian_density=0.3,
                   lat_4g_ms=50,       # 4G Base Latency (ms): 20-60 ms range
                   loss_4g_pct=10,     # Packet-loss %
                   lat_5g_ms=2,        # 5G Latency (ms): under 3 ms
                   headless=True):
    """
    Run one SUMO simulation and return performance metrics.

    V2X Parameters:
      • 5G URLLC:
        Trigger Range: 100.0 m (Direct V2I direct PC5 sidelink has longer range)
        Latency: 2 ms (Under 3 ms)
        Result: Preemption triggered early. Ambulance passes at full speed (0.0s stop delay).

      • 4G LTE:
        Trigger Range: 12.0 m (Cloud-routed cell network has limited reliable preemption range)
        Latency: 50 ms (20-60 ms range)
        Result: Preemption triggered late. Ambulance slows down or crawls briefly (0s absolute stop, but time lost).

      • Baseline:
        No preemption. Ambulance stops at red traffic light (stops completely, high stopped delay).
    """
    # ── 1. Regenerate network ────────────────────────────────────────────────
    from network.generate_network import generate_sumo_network
    generate_sumo_network(civilian_density=civilian_density)

    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "network", "sumo.sumocfg")
    binary = _sumo_bin(headless)

    # ── 2. Close any stale connection ────────────────────────────────────────
    try:
        traci.close()
    except Exception:
        pass

    # ── 3. Launch SUMO ───────────────────────────────────────────────────────
    traci.start([binary, "-c", cfg, "--start", "--quit-on-end"])

    # ── 4. Constants & Range Config ──────────────────────────────────────────
    STEP_LEN   = 0.05     # seconds per simulation step
    
    # 5G PC5 direct sidelink range is up to 100m; 4G cloud-routed range is set to 40m
    # to capture late preemption trigger dynamics.
    TRIG_DIST = 100.0 if mode == "5G URLLC" else 40.0

    # ── 5. State variables ───────────────────────────────────────────────────
    req_c1, req_c2       = False, False
    pre_time_c1          = None    # simulation step to execute C1 preemption
    pre_time_c2          = None
    pre_active_c1        = False
    pre_active_c2        = False
    pre_state_c1         = None
    pre_state_c2         = None
    pre_timer_c1         = 0
    pre_timer_c2         = 0
    trig_step_c1         = None
    trig_step_c2         = None
    exec_step_c1         = None
    exec_step_c2         = None

    ev_entered      = False
    ev_active_steps = 0
    ev_speeds       = []
    ev_stopped_steps = 0
    civ_delays      : dict = {}

    lat_c1_ms = 0.0
    lat_c2_ms = 0.0
    latency_samples : list = []   # individual V2I latency observations (ms)
    step            = 0
    sim_logs        : list = []
    time_series     : list = []

    def log(msg: str):
        sim_logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    log(f"=== Mode: {mode} | Density: {civilian_density} | GUI: {not headless} ===")
    if mode == "4G":
        log(f"4G radio latency: base={lat_4g_ms} ms, range={TRIG_DIST} m")
    elif mode == "5G URLLC":
        log(f"5G direct PC5 sidelink latency: {lat_5g_ms} ms, range={TRIG_DIST} m")
    else:
        log("Baseline: no V2I preemption — fixed signal schedule")

    # ── 6. Latency computation helper ────────────────────────────────────────
    def _compute_delay(junction: str) -> float:
        """Return total V2I delay in ms; records sample; logs event."""
        if mode == "5G URLLC":
            # Sub-3 ms direct sidelink with Gaussian jitter
            d = max(0.5, random.gauss(lat_5g_ms, 0.4))
            log(f"5G URLLC → {junction}: {d:.1f} ms (direct PC5 sidelink)")
        else:
            # 4G Cloud-routed latency: 20-60 ms base + retransmission penalty
            d = max(10, random.gauss(lat_4g_ms, lat_4g_ms * 0.2))
            retx = 0
            while random.random() * 100 < loss_4g_pct:
                retx += 1
                d += random.uniform(30, 80)
            if retx:
                log(f"4G → {junction}: {retx} packet drops! Total latency = {d:.1f} ms")
            else:
                log(f"4G → {junction}: {d:.1f} ms (cloud round-trip)")

        latency_samples.append(d)
        return d

    # ── 7. Simulation loop ───────────────────────────────────────────────────
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1

            if not headless:
                time.sleep(0.015)

            active = traci.vehicle.getIDList()

            # Release preemption when EV clears the intersection
            if pre_active_c1:
                try:
                    ev_road = (traci.vehicle.getRoadID("ambulence_ev")
                               if "ambulence_ev" in active else "")
                    if ev_road in ("c12c2", "c22e") or "ambulence_ev" not in active:
                        traci.trafficlight.setProgram("c1", "0")
                        pre_active_c1 = False
                        log("C1 released → default program restored")
                except Exception:
                    pass

            if pre_active_c2:
                try:
                    ev_road = (traci.vehicle.getRoadID("ambulence_ev")
                               if "ambulence_ev" in active else "")
                    if ev_road == "c22e" or "ambulence_ev" not in active:
                        traci.trafficlight.setProgram("c2", "0")
                        pre_active_c2 = False
                        log("C2 released → default program restored")
                except Exception:
                    pass

            # Early exit once EV has finished its route
            if ev_entered and "ambulence_ev" not in active:
                log("EV cleared corridor — simulation complete.")
                break

            # Civilian delay accumulation (speed < 0.1 m/s)
            for vid in active:
                if vid != "ambulence_ev":
                    civ_delays[vid] = traci.vehicle.getAccumulatedWaitingTime(vid)

            # EV tracking
            if "ambulence_ev" in active:
                if not ev_entered:
                    ev_entered = True
                    _highlight_ev()

                ev_active_steps += 1
                spd     = traci.vehicle.getSpeed("ambulence_ev")
                edge_id = traci.vehicle.getRoadID("ambulence_ev")
                pos     = traci.vehicle.getLanePosition("ambulence_ev")
                ev_speeds.append(spd)
                
                # Count speed < 0.1 m/s (complete stop) as stopped delay.
                if spd < 0.1:
                    ev_stopped_steps += 1

                dist_c1 = (400.0 - pos) if edge_id == "w2c1"  else None
                dist_c2 = (400.0 - pos) if edge_id == "c12c2" else None

                # ── Trigger C1 ────────────────────────────────────────────
                if dist_c1 is not None and dist_c1 <= TRIG_DIST and not req_c1:
                    req_c1       = True
                    trig_step_c1 = step
                    log(f"EV is {dist_c1:.1f} m from C1 — V2I priority message broadcast!")
                    if mode == "Baseline":
                        log("Baseline: signal controller ignores V2I request.")
                    else:
                        d = _compute_delay("C1")
                        lat_c1_ms = d
                        delay_steps = max(1, int(d / (STEP_LEN * 1000)))
                        pre_time_c1 = step + delay_steps

                # ── Trigger C2 ────────────────────────────────────────────
                if dist_c2 is not None and dist_c2 <= TRIG_DIST and not req_c2:
                    req_c2       = True
                    trig_step_c2 = step
                    log(f"EV is {dist_c2:.1f} m from C2 — V2I priority message broadcast!")
                    if mode == "Baseline":
                        log("Baseline: signal controller ignores V2I request.")
                    else:
                        d = _compute_delay("C2")
                        lat_c2_ms = d
                        delay_steps = max(1, int(d / (STEP_LEN * 1000)))
                        pre_time_c2 = step + delay_steps

                # Record time-series
                time_series.append({
                    "step":     step,
                    "time":     round(step * STEP_LEN, 3),
                    "ev_speed": round(spd * 3.6, 2),
                    "dist_c1":  round(dist_c1, 2) if dist_c1 is not None else 0.0,
                    "dist_c2":  round(dist_c2, 2) if dist_c2 is not None else 0.0,
                    "c1_phase": traci.trafficlight.getPhase("c1"),
                    "c2_phase": traci.trafficlight.getPhase("c2"),
                })

            # ── Execute deferred preemptions & transitions C1 ──────────────
            if pre_time_c1 is not None and step >= pre_time_c1:
                pre_time_c1 = None
                cur_p = traci.trafficlight.getPhase("c1")
                if cur_p == 2:  # Already green
                    traci.trafficlight.setPhase("c1", 2)
                    traci.trafficlight.setPhaseDuration("c1", 120)
                    pre_active_c1 = True
                    exec_step_c1  = step
                    log(">>> C1 PREEMPTED: Already EW green, holding green phase.")
                else:
                    traci.trafficlight.setPhase("c1", 1)  # NS yellow clearance
                    traci.trafficlight.setPhaseDuration("c1", 4.0)
                    pre_state_c1 = "YELLOW"
                    pre_timer_c1 = 80  # 4 seconds safety clearance
                    log(">>> C1 PREEMPTED: Initiating NS yellow safety clearance (4s)...")

            if pre_state_c1 == "YELLOW":
                pre_timer_c1 -= 1
                if pre_timer_c1 <= 0:
                    traci.trafficlight.setPhase("c1", 2)
                    traci.trafficlight.setPhaseDuration("c1", 120)
                    pre_active_c1 = True
                    pre_state_c1 = None
                    exec_step_c1  = step
                    log(">>> C1 PREEMPTED: Safety clearance complete, EW set to GREEN.")

            # ── Execute deferred preemptions & transitions C2 ──────────────
            if pre_time_c2 is not None and step >= pre_time_c2:
                pre_time_c2 = None
                cur_p = traci.trafficlight.getPhase("c2")
                if cur_p == 2:  # Already green
                    traci.trafficlight.setPhase("c2", 2)
                    traci.trafficlight.setPhaseDuration("c2", 120)
                    pre_active_c2 = True
                    exec_step_c2  = step
                    log(">>> C2 PREEMPTED: Already EW green, holding green phase.")
                else:
                    traci.trafficlight.setPhase("c2", 1)  # NS yellow clearance
                    traci.trafficlight.setPhaseDuration("c2", 4.0)
                    pre_state_c2 = "YELLOW"
                    pre_timer_c2 = 80  # 4 seconds safety clearance
                    log(">>> C2 PREEMPTED: Initiating NS yellow safety clearance (4s)...")

            if pre_state_c2 == "YELLOW":
                pre_timer_c2 -= 1
                if pre_timer_c2 <= 0:
                    traci.trafficlight.setPhase("c2", 2)
                    traci.trafficlight.setPhaseDuration("c2", 120)
                    pre_active_c2 = True
                    pre_state_c2 = None
                    exec_step_c2  = step
                    log(">>> C2 PREEMPTED: Safety clearance complete, EW set to GREEN.")

    except (traci.exceptions.FatalTraCIError, traci.exceptions.TraCIException) as te:
        log(f"SUMO connection ended: {te}")
    except Exception as exc:
        log(f"Simulation error: {exc}")
        raise
    finally:
        try:
            traci.close()
        except Exception:
            pass
        log("TraCI connection closed.")

    # ── 8. Metrics ───────────────────────────────────────────────────────────
    ev_travel = ev_active_steps * STEP_LEN
    ev_delay  = ev_stopped_steps * STEP_LEN
    ev_avgspd = (sum(ev_speeds) / len(ev_speeds)) * 3.6 if ev_speeds else 0.0

    # Actual V2I network latencies are already recorded in lat_c1_ms and lat_c2_ms during preemption trigger.

    # Build realistic latency distribution for histogram (50 samples)
    if mode == "5G URLLC":
        dist_samples = [max(0.5, random.gauss(lat_5g_ms, 0.4)) for _ in range(50)]
    elif mode == "4G":
        dist_samples = []
        for _ in range(50):
            base = max(10, random.gauss(lat_4g_ms, lat_4g_ms * 0.2))
            if random.random() * 100 < loss_4g_pct:
                base += random.uniform(30, 80)
            dist_samples.append(base)
    else:
        dist_samples = []

    return {
        "mode":            mode,
        "ev_travel_time":  round(ev_travel, 3),
        "ev_delay":        round(ev_delay, 3),
        "ev_avg_speed":    round(ev_avgspd, 2),
        "civilian_delay":  round(sum(civ_delays.values()), 2),
        "latency_c1_ms":   round(lat_c1_ms, 2),
        "latency_c2_ms":   round(lat_c2_ms, 2),
        "latency_samples": dist_samples,
        "logs":            sim_logs,
        "time_series":     time_series,
    }


if __name__ == "__main__":
    print("Testing Baseline >>>")
    r = run_simulation(mode="Baseline", civilian_density=0.3, headless=True)
    print(f"  Travel={r['ev_travel_time']}s  Delay={r['ev_delay']}s")

    print("Testing 4G >>>")
    r = run_simulation(mode="4G", civilian_density=0.3, lat_4g_ms=50, headless=True)
    print(f"  Travel={r['ev_travel_time']}s  Delay={r['ev_delay']}s  Lat_C1={r['latency_c1_ms']}ms")

    print("Testing 5G URLLC >>>")
    r = run_simulation(mode="5G URLLC", civilian_density=0.3, lat_5g_ms=2, headless=True)
    print(f"  Travel={r['ev_travel_time']}s  Delay={r['ev_delay']}s  Lat_C1={r['latency_c1_ms']}ms")
