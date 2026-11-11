import json
import time
from astra_telemetry import AstraTelemetryDashboard
from qasm_exporter import OpenQASMExporter
from astra_agent_exchange import AstraAgentNode

def initialize_command_center():
    print("=== INITIALIZING ASTRA SUPERCOMPUTER COMMAND CENTER ===")
    
    # Initialize components
    node = AstraAgentNode(agent_id="ASTRA_CORE_01")
    node.register_peer_agent("AGENT_GEMINI", "ws://127.0.0.1:9090", ["quantum_sim", "code_gen"])
    
    # Log active discovery / telemetry state
    node.log_discovery("QUANTUM_EXPANSION", "Live 4-qubit error mitigation pipeline synced")
    
    # Generate voice telemetry script for playback
    voice_script = node.generate_voice_telemetry_prompt()
    print(f"\n[Astra Voice Synth]: \"{voice_script}\"")
    
    # Perform agent handshake
    handshake = node.agent_handshake("AGENT_GEMINI", {"status": "SYNC_OK", "nodes": 10248})
    print(f"\n[Inter-Agent Handshake]: {json.dumps(handshake, indent=2)}")
    
    # Generate sample OpenQASM stream
    exporter = OpenQASMExporter(num_qubits=2, num_clbits=2)
    exporter.add_gate("h", 0)
    exporter.add_gate("cx", 0, 1)
    print(f"\n[OpenQASM 3.0 Stream Preview]:\n{exporter.export()}")
    print("=== ASTRA COMMAND CENTER READY ===")

if __name__ == "__main__":
    initialize_command_center()
