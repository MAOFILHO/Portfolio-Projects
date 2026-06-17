"""
Step 6: Customer-Facing Streamlit Frontend

Launches the Streamlit chat application using credentials from SSM/Secrets Manager.
The app provides a real-time streaming chat interface backed by the AgentCore Runtime endpoint.
"""
import os
import signal
import subprocess
import sys

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
PORT = 8501


def _free_port(port: int) -> None:
    """Kill any process already listening on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        if pids:
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
            print(f"  Stopped existing process(es) on port {port}: {', '.join(pids)}")
    except Exception:
        pass


def run() -> None:
    """Run Step 6: launch the Streamlit customer support chat interface."""
    print("\n=== Step 6: Customer-Facing Streamlit Frontend ===")

    print("\n[Step 1/2] Verifying AgentCore Runtime endpoint is available...")
    try:
        from agentcore.utils import get_ssm_parameter
        agent_arn = get_ssm_parameter("/app/customersupport/agentcore/runtime_arn")
        print(f"  Runtime ARN: {agent_arn}")
    except Exception as e:
        print(f"  WARNING: Could not retrieve runtime ARN from SSM: {e}")
        print("  Make sure Steps 4 and 5 have been completed before running Step 6.")

    print(f"\n[Step 2/2] Launching Streamlit chat application on port {PORT}...")
    _free_port(PORT)
    print(f"  Application URL: http://localhost:{PORT}")
    print("  Press Ctrl+C to stop the server.\n")

    original_dir = os.getcwd()
    os.chdir(FRONTEND_DIR)
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "main.py", "--server.port", str(PORT)],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n  Streamlit server stopped.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Streamlit failed to start: {e}") from e
    finally:
        os.chdir(original_dir)
