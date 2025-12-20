import sys
from .api import start_test_thread

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m runner.run_test <test_case_id>")
    else:
        tid = int(sys.argv[1])
        print(f">>> Starting Test ID: {tid} local...")
        start_test_thread(tid)