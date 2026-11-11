class OpenQASMExporter:
    def __init__(self, num_qubits=2, num_clbits=2):
        self.num_qubits = num_qubits
        self.num_clbits = num_clbits
        self.instructions = []

    def add_gate(self, gate_name, *qubits):
        self.instructions.append((gate_name, qubits))

    def export(self):
        qasm = "OPENQASM 3.0;\ninclude \"stdgates.inc\";\n\n"
        qasm += f"qubit[{self.num_qubits}] q;\n"
        qasm += f"bit[{self.num_clbits}] c;\n\n"
        for gate, qubits in self.instructions:
            qbits_str = ", ".join([f"q[{q}]" for q in qubits])
            qasm += f"{gate} {qbits_str};\n"
        return qasm
