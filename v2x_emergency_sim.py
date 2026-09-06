import os
import sys
import time

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare the environment variable 'SUMO_HOME'")

import traci

def draw_pulse_circle(polygon_id, cx, cy, r, color):
    import math
    num_points = 16
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    points.append(points[0]) # close polygon
    
    if polygon_id in traci.polygon.getIDList():
        traci.polygon.setShape(polygon_id, points)
        traci.polygon.setColor(polygon_id, color)
    else:
        # add(polygonID, shape, color, fill=False, polygonType='', layer=0)
        traci.polygon.add(polygon_id, points, color, False, "", 100)

class SumoHUD:
    def __init__(self, x, y, dy=15):
        self.start_x = x
        self.start_y = y
        self.dy = dy
        self.active_pois = {}
        
    def update_line(self, line_idx, text, color=(255, 255, 255, 255)):
        # Remove old POI if it exists for this line index
        if line_idx in self.active_pois:
            old_poi_id = self.active_pois[line_idx]
            if old_poi_id in traci.poi.getIDList():
                traci.poi.remove(old_poi_id)
        
        # Add new POI with the text itself as the POI ID
        y_pos = self.start_y - (line_idx * self.dy)
        poi_id = text
        # Set a semi-transparent color for the dot so it acts like a subtle bullet point
        traci.poi.add(poi_id, self.start_x, y_pos, (0, 255, 255, 0), "", 200)
        self.active_pois[line_idx] = poi_id
        
    def clear(self):
        for line_idx, poi_id in list(self.active_pois.items()):
            if poi_id in traci.poi.getIDList():
                traci.poi.remove(poi_id)
        self.active_pois.clear()

def run_intersection_simulation():
    print("====================================================")
    print(" 5G URLLC vs 4G LTE: EMERGENCY VEHICLE PREEMPTION   ")
    print("====================================================")
    print("This simulation demonstrates V2I (Vehicle-to-Infrastructure)")
    print("preemption. An ambulance approaching from the North faces a")
    print("RED light while West-to-East civilian traffic is flowing.")
    print("----------------------------------------------------")
    if len(sys.argv) > 1:
        network_choice = sys.argv[1].upper()
    else:
        network_choice = input("Select Network Profile ('4G' or '5G'): ").strip().upper()

    # Define V2I network delays in milliseconds and steps (1 step = 20ms)
    if network_choice == '4G':
        network_delay_ms = 3500
        network_delay_steps = 175   # 3500ms / 20ms
        color_theme = (255, 69, 0, 255)  # Orange-red
        print("\n[CONFIG] 4G LTE Selected: 3500ms preemption delay expected.")
    elif network_choice == '5G':
        network_delay_ms = 5
        network_delay_steps = 1    # 5ms -> 1 step (20ms)
        color_theme = (0, 255, 127, 255) # Spring Green
        print("\n[CONFIG] 5G URLLC Selected: 5ms near-instant preemption.")
    else:
        print("Invalid entry. Defaulting to 4G.")
        network_choice = '4G'
        network_delay_ms = 3500
        network_delay_steps = 175
        color_theme = (255, 69, 0, 255)

    # Start SUMO
    sumo_binary = "sumo" if (len(sys.argv) > 2 and sys.argv[2] == "headless") else "sumo-gui"
    traci.start([sumo_binary, "-c", "intersection.sumocfg", "--start"])

    # Force traffic light 'center' to prioritize West-to-East initially (Ambulance faces Red)
    # Phase 2 is rrGG (West-East Green, North-South Red)
    traci.trafficlight.setPhase("center", 2)

    step = 0
    request_sent = False
    light_switch_step = None
    total_stopped_time_ms = 0
    ambulance_initialized = False
    
    # Initialize HUD on the side of the intersection
    hud = SumoHUD(x=-180, y=100, dy=12)

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        step += 1  # 1 step = 20ms
        
        # Pace simulation to match real-time
        if sumo_binary == "sumo-gui":
            time.sleep(0.02)

        # Check if ambulance is active in the network map
        active_veh_list = traci.vehicle.getIDList()
        if "ambulence_ev" in active_veh_list:
            # Scale up vehicle size and center camera on first appearance
            if not ambulance_initialized:
                try:
                    traci.gui.trackVehicle("View #0", "ambulence_ev")
                except Exception:
                    pass
                ambulance_initialized = True

            current_speed = traci.vehicle.getSpeed("ambulence_ev")
            lane_pos = traci.vehicle.getLanePosition("ambulence_ev")
            distance_to_intersection = 300.0 - lane_pos

            # Track stopped time due to red light congestion
            if current_speed < 0.1:
                total_stopped_time_ms += 20

            # Flashing siren (Emergency lights)
            if (step // 5) % 2 == 0:
                traci.vehicle.setColor("ambulence_ev", (255, 0, 0, 255)) # Red
            else:
                traci.vehicle.setColor("ambulence_ev", (0, 0, 255, 255)) # Blue

            # Preemption zone trigger: Ambulance broadcasts request when within 35 meters
            if distance_to_intersection <= 35.0 and not request_sent:
                print(f"\n>>> [V2I] Ambulance at {distance_to_intersection:.1f}m transmitting priority preemption request...")
                request_sent = True
                light_switch_step = step + network_delay_steps
                print(f"    [NETWORK] Message traversing network. Action scheduled at step: {light_switch_step} ({network_delay_ms}ms latency)")

            # Pulse the V2X wireless signal circle if request is sent but preemption not executed yet
            if request_sent and light_switch_step is not None:
                pulse_time = step - (light_switch_step - network_delay_steps)
                if network_choice == '5G':
                    r = 20.0 + (pulse_time * 10.0) # Fast instant pulse
                    wave_color = (0, 255, 127, 180)
                else:
                    r = 15.0 + ((pulse_time % 20) * 2.0) # Pulsing waves showing delay
                    wave_color = (255, 69, 0, 180)
                
                amb_x, amb_y = traci.vehicle.getPosition("ambulence_ev")
                draw_pulse_circle("v2i_wave", amb_x, amb_y, r, wave_color)

            # Update HUD overlay text
            hud.update_line(0, "=== V2X EMERGENCY PREEMPTION SIM ===", (255, 255, 255, 255))
            hud.update_line(1, f"Network Mode : {network_choice} Profile", color_theme)
            hud.update_line(2, f"V2I Latency  : {network_delay_ms} ms", color_theme)
            
            if not request_sent:
                hud.update_line(3, "Status       : Approaching Intersection (Red Light)", (200, 200, 200, 255))
            elif light_switch_step is not None:
                hud.update_line(3, "Status       : Transmitting... [PREEMPTION PENDING]", (255, 165, 0, 255))
            else:
                hud.update_line(3, "Status       : PREEMPTION ACTIVE! (Green Light)", (0, 255, 0, 255))
                
            hud.update_line(4, f"Distance     : {distance_to_intersection:.1f} m", (255, 255, 255, 255))
            hud.update_line(5, f"Current Speed: {current_speed * 3.6:.1f} km/h", (255, 255, 255, 255))
            hud.update_line(6, f"Stopped Time : {total_stopped_time_ms / 1000:.2f} s", (255, 50, 50, 255) if total_stopped_time_ms > 0 else (100, 255, 100, 255))

        # Execute traffic light manipulation after network latency completes
        if request_sent and light_switch_step is not None:
            if step >= light_switch_step:
                print(f"*** [TRAFFIC LIGHT] Preemption command executed! Switching North-South axis to GREEN.")
                # Force traffic light to Phase 0 (GGrr - North-South Green)
                traci.trafficlight.setPhase("center", 0)
                light_switch_step = None # Clear trigger
                
                # Remove pulse wave polygon
                if "v2i_wave" in traci.polygon.getIDList():
                    traci.polygon.remove("v2i_wave")

    # Clear HUD before exiting
    hud.clear()

    print("\n========================= MISSION METRICS =========================")
    print(f"Network Connectivity Profile : {network_choice}")
    print(f"Total Intersectional Delay   : {total_stopped_time_ms / 1000:.3f} seconds")
    
    if total_stopped_time_ms > 0:
        print("Outcome: EMERGENCY DELAYED! 4G latency caused the ambulance to stop.")
    else:
        print("Outcome: PERFECT PREEMPTION! 5G URLLC cleared the intersection instantly.")
    print("=====================================================================")

    traci.close()

if __name__ == "__main__":
    run_intersection_simulation()