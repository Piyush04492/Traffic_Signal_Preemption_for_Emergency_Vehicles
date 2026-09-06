import os
import sys
import subprocess

def generate_sumo_network(civilian_density=0.2):
    """
    Generates all SUMO XML network and route files programmatically.
    Uses default traffic light cycles (90s cycle time) from netconvert.
    """
    network_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Generate nodes file (.nod.xml)
    nod_file = os.path.join(network_dir, "nodes.nod.xml")
    with open(nod_file, "w", encoding="utf-8") as f:
        f.write("""<nodes>
    <node id="west"   x="-200" y="0"    type="priority"/>
    <node id="c1"     x="200"  y="0"    type="traffic_light"/>
    <node id="c2"     x="600"  y="0"    type="traffic_light"/>
    <node id="east"   x="1000" y="0"    type="priority"/>
    
    <!-- Intersection 1 cross nodes -->
    <node id="north1" x="200"  y="250"  type="priority"/>
    <node id="south1" x="200"  y="-250" type="priority"/>
    
    <!-- Intersection 2 cross nodes -->
    <node id="north2" x="600"  y="250"  type="priority"/>
    <node id="south2" x="600"  y="-250" type="priority"/>
</nodes>""")

    # 2. Generate edges file (.edg.xml)
    edg_file = os.path.join(network_dir, "edges.edg.xml")
    with open(edg_file, "w", encoding="utf-8") as f:
        f.write("""<edges>
    <!-- Main corridor edges -->
    <edge id="w2c1"  from="west"   to="c1"     numLanes="3" speed="16.67" priority="3"/>
    <edge id="c12c2" from="c1"     to="c2"     numLanes="3" speed="16.67" priority="3"/>
    <edge id="c22e"  from="c2"     to="east"   numLanes="3" speed="16.67" priority="3"/>
    
    <!-- Cross street 1 edges -->
    <edge id="n12c1" from="north1" to="c1"     numLanes="2" speed="13.89" priority="2"/>
    <edge id="c12s1" from="c1"     to="south1" numLanes="2" speed="13.89" priority="2"/>
    
    <!-- Cross street 2 edges -->
    <edge id="n22c2" from="north2" to="c2"     numLanes="2" speed="13.89" priority="2"/>
    <edge id="c22s2" from="c2"     to="south2" numLanes="2" speed="13.89" priority="2"/>
</edges>""")

    # 3. Compile network using netconvert
    net_file = os.path.join(network_dir, "network.net.xml")
    sumo_home = os.environ.get("SUMO_HOME", "")
    netconvert_bin = "netconvert"
    if sumo_home:
        for ext in ("", ".exe"):
            cand = os.path.join(sumo_home, "bin", "netconvert" + ext)
            if os.path.exists(cand):
                netconvert_bin = cand
                break

    print(f"[NETCONVERT] Running netconvert from: {netconvert_bin}")
    cmd = [
        netconvert_bin,
        "--node-files", nod_file,
        "--edge-files", edg_file,
        "--output-file", net_file,
        "--no-turnarounds", "true"
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[NETCONVERT] Compiled network.net.xml successfully.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[NETCONVERT] ERROR: Failed to run netconvert: {e}", file=sys.stderr)
        if hasattr(e, 'stderr') and e.stderr:
            print(f"[NETCONVERT] Stderr details: {e.stderr}", file=sys.stderr)
        raise

    # 4. Generate routes file (.rou.xml)
    rou_file = os.path.join(network_dir, "routes.rou.xml")
    with open(rou_file, "w", encoding="utf-8") as f:
        f.write(f"""<routes>
    <!-- === Vehicle Types === -->
    <!-- Passenger car -->
    <vType id="car"   accel="2.6" decel="4.5" length="4.5" width="1.8"
           minGap="2.5" maxSpeed="13.89" sigma="0.5"
           color="0.55,0.55,0.60" guiShape="passenger"/>

    <!-- City bus -->
    <vType id="bus"   accel="1.4" decel="3.5" length="12.0" width="2.5"
           minGap="3.0" maxSpeed="11.11" sigma="0.4"
           color="0.20,0.45,0.80" guiShape="bus"/>

    <!-- Delivery truck -->
    <vType id="truck" accel="1.2" decel="3.0" length="16.0" width="2.6"
           minGap="4.0" maxSpeed="9.72"  sigma="0.3"
           color="0.30,0.30,0.30" guiShape="truck"/>

    <!-- Motorcycle -->
    <vType id="moto"  accel="3.8" decel="5.5" length="2.2" width="0.9"
           minGap="1.5" maxSpeed="16.67" sigma="0.6"
           color="1.00,0.80,0.00" guiShape="motorcycle"/>

    <!-- Emergency ambulance -->
    <vType id="ambulance" accel="5.0" decel="6.5" length="8.0" width="2.4"
           minGap="1.5" maxSpeed="22.22" sigma="0.0"
           guiShape="emergency" color="1,0,0"/>

    <!-- === Routes === -->
    <route id="main_corridor" edges="w2c1 c12c2 c22e"/>
    <route id="cross_1"       edges="n12c1 c12s1"/>
    <route id="cross_2"       edges="n22c2 c22s2"/>

    <!-- === Civilian Traffic Flows (mixed types) === -->
    <!-- Main corridor: cars 50%, buses 15%, trucks 10%, motos 25% -->
    <flow id="fc_car"   type="car"   route="main_corridor" begin="0" end="150"
          probability="{civilian_density * 0.50:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fc_bus"   type="bus"   route="main_corridor" begin="0" end="150"
          probability="{civilian_density * 0.15:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fc_truck" type="truck" route="main_corridor" begin="0" end="150"
          probability="{civilian_density * 0.10:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fc_moto"  type="moto"  route="main_corridor" begin="0" end="150"
          probability="{civilian_density * 0.25:.4f}" departSpeed="max" departLane="best"/>

    <!-- Cross street 1 -->
    <flow id="fx1_car"  type="car"   route="cross_1" begin="0" end="150"
          probability="{civilian_density * 0.40:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fx1_moto" type="moto"  route="cross_1" begin="0" end="150"
          probability="{civilian_density * 0.20:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fx1_bus"  type="bus"   route="cross_1" begin="0" end="150"
          probability="{civilian_density * 0.10:.4f}" departSpeed="max" departLane="best"/>

    <!-- Cross street 2 -->
    <flow id="fx2_car"  type="car"   route="cross_2" begin="0" end="150"
          probability="{civilian_density * 0.40:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fx2_moto" type="moto"  route="cross_2" begin="0" end="150"
          probability="{civilian_density * 0.20:.4f}" departSpeed="max" departLane="best"/>
    <flow id="fx2_truck" type="truck" route="cross_2" begin="0" end="150"
          probability="{civilian_density * 0.05:.4f}" departSpeed="max" departLane="best"/>

    <!-- === Emergency Vehicle === -->
    <vehicle id="ambulence_ev" type="ambulance" route="main_corridor"
             depart="15" departPos="0" departSpeed="16.67" departLane="1"/>
</routes>""")
    print("[ROUTES] Generated routes.rou.xml (cars + buses + trucks + motos) successfully.")

    # 5. Generate SUMO config (.sumocfg)
    cfg_file = os.path.join(network_dir, "sumo.sumocfg")
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.write("""<configuration>
    <input>
        <net-file value="network.net.xml"/>
        <route-files value="routes.rou.xml"/>
        <gui-settings-file value="viewsettings.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="200"/>
        <step-length value="0.05"/>
    </time>
</configuration>""")
    print("[CONFIG] Generated sumo.sumocfg successfully.")

if __name__ == "__main__":
    generate_sumo_network()
