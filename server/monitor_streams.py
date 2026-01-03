#!/usr/bin/env python3
"""
Stream monitoring utility
Helps debug active streams and resource usage
"""
import psutil
import time
import sys

def monitor_process():
    """Monitor FastAPI server resource usage"""
    try:
        # Find FastAPI process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['cmdline'] and any('main_fastapi' in str(arg) for arg in proc.info['cmdline']):
                print(f"Found FastAPI process: PID {proc.info['pid']}")
                
                while True:
                    try:
                        # Get process info
                        cpu_percent = proc.cpu_percent(interval=1)
                        memory_info = proc.memory_info()
                        memory_mb = memory_info.rss / 1024 / 1024
                        
                        # Get thread count
                        num_threads = proc.num_threads()
                        
                        # Get open connections
                        connections = proc.connections()
                        established_conns = [c for c in connections if c.status == 'ESTABLISHED']
                        
                        print(f"\r[{time.strftime('%H:%M:%S')}] "
                              f"CPU: {cpu_percent:5.1f}% | "
                              f"RAM: {memory_mb:6.1f}MB | "
                              f"Threads: {num_threads:3d} | "
                              f"Connections: {len(established_conns):2d}", 
                              end='', flush=True)
                        
                        time.sleep(1)
                        
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        print("\n❌ Process ended or access denied")
                        break
                    except KeyboardInterrupt:
                        print("\n\n✅ Monitoring stopped")
                        sys.exit(0)
                
                return
        
        print("❌ FastAPI process not found. Is the server running?")
        print("   Start server: python main_fastapi.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("📊 FastAPI Stream Monitor")
    print("=" * 60)
    print("Monitoring resource usage (Ctrl+C to stop)...\n")
    monitor_process()
