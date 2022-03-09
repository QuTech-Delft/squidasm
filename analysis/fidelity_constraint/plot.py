import datetime
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt

COMPILE_VERSIONS = ["nqasm_retry", "host_retry"]
FORMATS = {
    "nqasm_retry": "-ro",
    "host_retry": "-bs",
}
FORMATS_2 = {
    "nqasm_retry": "--ro",
    "host_retry": "--bo",
}
VERSION_LABELS = {
    "nqasm_retry": "NetQASM retry",
    "host_retry": "Host retry",
}

X_LABELS = {
    "fidelity": "Fidelity",
    "rate": "Success probability per entanglement attempt",
    "t2": "T2 (ns)",
    "gate_noise": "2-qubit gate depolarising probability",
    "gate_noise_trap": "2-qubit gate depolarising probability",
    "gate_time": "2-qubit gate duration (ms)",
    "gate_time_trap": "2-qubit gate duration (ms)",
    "latency": "Host <-> QNodeOS latency (ms)",
}


def create_png(param_name):
    output_dir = os.path.join(os.path.dirname(__file__), "plots")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"bqc_sweep_{param_name}_{timestamp}.png")
    plt.savefig(output_path)
    print(f"plot written to {output_path}")


def plot_host_qnos_latency(data: Dict[float, SimulationOutput]):
    param_name = "host_qnos_latency"

    data_path = os.path.join(
        os.path.dirname(__file__), f"sweep_data_bqc/sweep_{param_name}.json"
    )

    with open(data_path, "r") as f:
        all_data = json.load(f)

    fig, ax = plt.subplots()

    ax.grid()
    ax.set_xlabel(X_LABELS[param_name])
    ax.set_ylabel("Error rate")

    for version in COMPILE_VERSIONS:
        data = all_data[version]
        sweep_values = [v["sweep_value"] for v in data]
        error_rates = [v["error_rate"] for v in data]
        std_errs = [v["std_err"] for v in data]
        ax.errorbar(
            x=sweep_values,
            y=error_rates,
            yerr=std_errs,
            fmt=FORMATS[version],
            label=VERSION_LABELS[version],
        )

    ax.set_title(
        "BQC trap round error rate vs two-qubit gate noise probability",
        wrap=True,
    )

    # ax.set_ylim(0.10, 0.35)
    # ax.axhline(y=0.25, color="red", label="BQC threshold")
    ax.legend()
    # plt.tight_layout()

    create_png(param_name)


if __name__ == "__main__":
    plot_gate_noise_trap()
