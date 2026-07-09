import os
import sys
import time

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare the environment variable 'SUMO_HOME'")

import traci

def run_intersection_simulation():
    print("====================================================")
    print(" 5G URLLC vs 4G LTE: EMERGENCY VEHICLE PREEMPTION   ")
    print("====================================================")
    network_choice = input("Select Network Profile ('4G' or '5G'): ").strip().upper()

    # Define V2I network delays in milliseconds
    if network_choice == '4G':
        network_delay_ms = 1500  # High delay due to network congestion/processing lag
        print("\n[CONFIG] 4G LTE Selected: 1500ms preemption delay expected.")
    elif network_choice == '5G':
        network_delay_ms = 5     # 5G URLLC localized edge preemption
        print("\n[CONFIG] 5G URLLC Selected: 5ms near-instant preemption.")
    else:
        print("Invalid entry. Defaulting to 4G.")
        network_delay_ms = 1500

    traci.start(["sumo-gui", "-c", "intersection.sumocfg"])

    # Force traffic light 'center' to prioritize West-to-East initially (Ambulance faces Red)
    # Phase 0 in standard SUMO automatic generation is typically green for horizontal axes
    traci.trafficlight.setPhase("center", 0)

    step = 0
    request_sent = False
    light_switch_step = None
    total_stopped_time_ms = 0

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        step += 1  # 1 step = 1 millisecond

        # Check if ambulance is active in the network map
        if "ambulence_ev" in traci.vehicle.getIDList():
            current_speed = traci.vehicle.getSpeed("ambulence_ev")
            
            # Track time lost/stopped due to red light congestion
            if current_speed < 0.1:
                total_stopped_time_ms += 1

            # Get distance remaining to the end of the entry edge (the intersection center)
            # Edge 'n2c' is 300 meters long total
            lane_pos = traci.vehicle.getLanePosition("ambulence_ev")
            distance_to_intersection = 300.0 - lane_pos

            # V2I Trigger: Ambulance broadcasts request when within 120 meters of intersection
            if distance_to_intersection <= 120.0 and not request_sent:
                print(f"\n📡 [V2I] Ambulance at {distance_to_intersection:.1f}m transmitting priority preemption request...")
                request_sent = True
                light_switch_step = step + network_delay_ms
                print(f"⌛ [NETWORK] Message traversing network. Action scheduled at step: {light_switch_step}ms")

        # Execute traffic light manipulation after network latency completes
        if request_sent and light_switch_step is not None:
            if step == light_switch_step:
                print(f"🟢 [TRAFFIC LIGHT] Preemption command executed! Switching North-South axis to GREEN.")
                # Force the traffic light to switch to North-South green phase
                # In basic 4-arm setups, phase 2 is typically the vertical green phase
                traci.trafficlight.setPhase("center", 2)
                light_switch_step = None  # Clear trigger

    print("\n========================= MISSION METRICS =========================")
    print(f"Network Connectivity Profile : {network_choice}")
    print(f"Total Intersectional Delay   : {total_stopped_time_ms / 1000:.3f} seconds")
    
    if total_stopped_time_ms > 500:
        print("Outcome: Emergency vehicle delayed. Traffic light failed to respond in time.")
    else:
        print("Outcome: Perfect Preemption! Ambulance cleared intersection safely without stopping.")
    print("=====================================================================")

    traci.close()

if __name__ == "__main__":
    run_intersection_simulation()