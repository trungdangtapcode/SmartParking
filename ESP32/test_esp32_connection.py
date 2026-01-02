#!/usr/bin/env python3
"""
Test script for ESP32-CAM connection
Tests all ESP32 endpoints and validates responses
"""

import requests
import sys
import time
from pathlib import Path

# ESP32-CAM Configuration
ESP32_URL = "http://192.168.33.122:81"  # Change this to your ESP32 IP
MOCK_URL = "http://localhost:8081"       # Local mock server

def test_connection(url, name="ESP32"):
    """Test basic connection"""
    print(f"\n{'='*60}")
    print(f"Testing {name} Connection: {url}")
    print('='*60)
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {name} is online")
            return True
        else:
            print(f"❌ {name} returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {name} at {url}")
        print(f"   Make sure {name} is powered on and connected to network")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Connection timeout to {name}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_status(url):
    """Test /status endpoint"""
    print("\n📊 Testing /status endpoint...")
    try:
        response = requests.get(f"{url}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ Status endpoint working")
            print(f"   Device: {data.get('device', 'N/A')}")
            print(f"   Status: {data.get('status', 'N/A')}")
            print(f"   IP: {data.get('ip', 'N/A')}")
            print(f"   WiFi RSSI: {data.get('rssi', 'N/A')} dBm")
            print(f"   Uptime: {data.get('uptime', 0)} seconds")
            print(f"   Frames: {data.get('frames', 0)}")
            return True
        else:
            print(f"❌ Status returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Status test failed: {e}")
        return False

def test_capture(url, output_path="test_capture.jpg"):
    """Test /capture endpoint"""
    print("\n📸 Testing /capture endpoint...")
    try:
        response = requests.get(f"{url}/capture", timeout=10)
        if response.status_code == 200:
            # Save image
            Path(output_path).write_bytes(response.content)
            size_kb = len(response.content) / 1024
            print(f"✅ Capture successful")
            print(f"   Size: {size_kb:.2f} KB")
            print(f"   Saved to: {output_path}")
            return True
        else:
            print(f"❌ Capture returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Capture test failed: {e}")
        return False

def test_stream(url, duration=3):
    """Test /stream endpoint (just check if it starts)"""
    print(f"\n📹 Testing /stream endpoint (for {duration} seconds)...")
    try:
        response = requests.get(f"{url}/stream", stream=True, timeout=10)
        if response.status_code == 200:
            print("✅ Stream started")
            
            # Read a few chunks to verify streaming
            chunk_count = 0
            total_bytes = 0
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    chunk_count += 1
                    total_bytes += len(chunk)
                
                # Stop after specified duration
                if time.time() - start_time > duration:
                    break
            
            elapsed = time.time() - start_time
            throughput_kbps = (total_bytes / 1024) / elapsed
            
            print(f"   Duration: {elapsed:.2f} seconds")
            print(f"   Chunks received: {chunk_count}")
            print(f"   Data received: {total_bytes / 1024:.2f} KB")
            print(f"   Throughput: {throughput_kbps:.2f} KB/s")
            return True
        else:
            print(f"❌ Stream returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Stream test failed: {e}")
        return False

def test_control(url):
    """Test /control endpoint"""
    print("\n⚙️  Testing /control endpoint...")
    try:
        # Test quality control
        payload = {"action": "set_quality", "quality": 10}
        response = requests.post(f"{url}/control", json=payload, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Control endpoint working")
            print(f"   Response: {data.get('message', 'N/A')}")
            return True
        else:
            print(f"❌ Control returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Control test failed: {e}")
        return False

def run_full_test(url, name="ESP32"):
    """Run full test suite"""
    print(f"\n{'#'*60}")
    print(f"# Full ESP32-CAM Test Suite - {name}")
    print(f"{'#'*60}")
    
    results = {
        "Connection": test_connection(url, name),
    }
    
    if results["Connection"]:
        results["Status"] = test_status(url)
        results["Capture"] = test_capture(url, f"test_{name.lower()}_capture.jpg")
        results["Stream"] = test_stream(url, duration=3)
        results["Control"] = test_control(url)
    else:
        print(f"\n❌ Cannot connect to {name}, skipping other tests")
        results["Status"] = False
        results["Capture"] = False
        results["Stream"] = False
        results["Control"] = False
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary for {name}")
    print('='*60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test:20s} {status}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    return passed == total

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ESP32-CAM connection")
    parser.add_argument("--url", default=ESP32_URL, help=f"ESP32-CAM URL (default: {ESP32_URL})")
    parser.add_argument("--mock", action="store_true", help="Test mock server instead")
    parser.add_argument("--both", action="store_true", help="Test both real and mock")
    args = parser.parse_args()
    
    success = True
    
    if args.both:
        # Test both real and mock
        print("Testing both Real ESP32 and Mock Server...\n")
        success_real = run_full_test(ESP32_URL, "Real ESP32")
        print("\n" + "="*60 + "\n")
        success_mock = run_full_test(MOCK_URL, "Mock Server")
        success = success_real or success_mock  # At least one should work
    elif args.mock:
        # Test mock server
        success = run_full_test(MOCK_URL, "Mock Server")
    else:
        # Test specified URL
        success = run_full_test(args.url, "ESP32-CAM")
    
    # Exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
