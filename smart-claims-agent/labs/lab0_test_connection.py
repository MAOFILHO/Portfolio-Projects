"""
Lab 0: Test Connection — Verify SDK Connectivity
=================================================
Run: python labs/lab0_test_connection.py
"""
 
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
 
from utils.config import get_clients, MODEL, ENDPOINT, print_header
 
 
def main():
    print_header(0, "Test Connection")
 
    # Step 1: Verify environment
    print("Step 1: Checking environment variables...")
    print(f"   ENDPOINT: {ENDPOINT[:60]}...")
    print(f"   MODEL:    {MODEL}")
    print("   ✅ Variables loaded\n")
 
    # Step 2: Create clients
    print("Step 2: Creating clients...")
    project_client, openai_client = get_clients()
    print("   ✅ AIProjectClient created")
    print("   ✅ OpenAI client created\n")
 
    # Step 3: Test call
    print("Step 3: Sending test prompt...")
    response = openai_client.responses.create(
        model=MODEL,
        input="Reply with exactly: SmartClaims connection successful!",
    )
    print(f"   🤖 Response: {response.output_text}\n")
 
    print("=" * 65)
    print("  ✅ ALL CHECKS PASSED — Environment is ready!")
    print("=" * 65)
    print("\n  Next → python labs/lab1_hello_agent.py\n")
 
 
if __name__ == "__main__":
    main()
