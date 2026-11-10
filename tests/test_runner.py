#!/usr/bin/env python3
import os
import sys
import time
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def run_all_tests():
    start_time = time.time()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_dirs = [
        os.path.join(ROOT_DIR, "tests", "contract"),
        os.path.join(ROOT_DIR, "tests", "unit"),
        os.path.join(ROOT_DIR, "tests", "integration"),
    ]

    for d in test_dirs:
        discovered = loader.discover(start_dir=d, pattern="test_*.py", top_level_dir=ROOT_DIR)
        suite.addTests(discovered)

    print("=" * 70)
    print("CONTINUITY AI - MASTER TEST SUITE EXECUTION")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    duration = time.time() - start_time

    print("\n" + "=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures:  {len(result.failures)}")
    print(f"Errors:    {len(result.errors)}")
    print(f"Duration:  {duration:.2f}s")
    print("=" * 70)

    if result.wasSuccessful():
        print("RESULT: ALL TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print("RESULT: TEST SUITE FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
