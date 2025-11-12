#!/usr/bin/env python3
"""
Optimized BTC Puzzle Scanner for Termux/Android
Uses fastecdsa for better performance and batch processing
"""

import os
import sys
import time
import hashlib
import random
import psutil
from multiprocessing import Pool, cpu_count, Value
import ctypes
import signal

# Try to use faster libraries if available
try:
    from fastecdsa import curve, point
    from fastecdsa.encoding.sec1 import SEC1Encoder
    FAST_MODE = True
    print("✅ Using fastecdsa (faster)")
except:
    import ecdsa
    FAST_MODE = False
    print("⚠️ Using ecdsa (slower) - install fastecdsa for better performance")

import base58

class OptimizedBTCScanner:
    def __init__(self, puzzle_number):
        self.puzzle_number = puzzle_number
        self.start_range = 2 ** (puzzle_number - 1)
        self.end_range = 2 ** puzzle_number - 1
        
        # Puzzle addresses
        self.puzzle_addresses = {
            64: "16jY7qLJnxb7CHZyqBP8qca9d51gAjyXQN",
            65: "18ZMbwUFLMHoZBbfpCjUJQTCMCbktshgpe",
            66: "13zb1hQbWVsc2S7ZTZnP2G4undNNpdh5so",
            67: "1MY8PEU7jmvcEHjbfNcWpe4EsH57yFQmVZ",
            68: "14BuVKkeEpJFDwYUqhzm1D39hmPyQ5sKT5",
            69: "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU",
            70: "1JTK7s9YVYywfm5XUH7RNhHJH1LshCaRFR",
            71: "12JzYkkN76xkwvcPT6AWKZtGX6w2LAgsJg",
            72: "1EQJvpsmhazYCcKX5Au6AZmZKRnzFPMbYr",
            73: "12VVRNPi4SJqUTsp6FmqDqY5sGosDtysn4",
            74: "1CRjKZJu8LvTutnSKq4zTJ4yiqrzMAArQW",
            75: "1PJZPzvGX19a7twf5HyD2VvNbPTEeGPtgD",
            # Add more as needed
        }
        
        self.target_address = self.puzzle_addresses.get(puzzle_number, "")
        self.target_hash160 = None
        if self.target_address:
            # Pre-compute hash160 for faster comparison
            decoded = base58.b58decode_check(self.target_address)
            self.target_hash160 = decoded[1:]  # Remove version byte
        
        # Shared counter for multiprocessing
        self.counter = Value(ctypes.c_ulonglong, 0)
        self.start_time = time.time()
        
    def fast_private_to_hash160(self, private_key_int):
        """Optimized version - computes only hash160, not full address"""
        # Convert to bytes
        private_key_bytes = private_key_int.to_bytes(32, 'big')
        
        if FAST_MODE:
            # Use fastecdsa
            from fastecdsa import keys
            public_key = keys.get_public_key(private_key_int, curve.secp256k1)
            public_key_bytes = b'\x04' + public_key.x.to_bytes(32, 'big') + public_key.y.to_bytes(32, 'big')
        else:
            # Use ecdsa (slower)
            sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
            vk = sk.verifying_key
            public_key_bytes = b'\x04' + vk.to_string()
        
        # SHA-256
        sha256_hash = hashlib.sha256(public_key_bytes).digest()
        
        # RIPEMD-160
        h = hashlib.new('ripemd160')
        h.update(sha256_hash)
        hash160 = h.digest()
        
        return hash160
    
    def batch_scan(self, start_key, batch_size=1000):
        """Scan a batch of keys"""
        found = None
        
        for i in range(batch_size):
            key = start_key + i
            if key > self.end_range:
                break
                
            try:
                hash160 = self.fast_private_to_hash160(key)
                
                if hash160 == self.target_hash160:
                    # Found it! Now compute full address for verification
                    versioned_key = b'\x00' + hash160
                    checksum = hashlib.sha256(hashlib.sha256(versioned_key).digest()).digest()[:4]
                    address = base58.b58encode(versioned_key + checksum).decode()
                    
                    return {
                        'found': True,
                        'private_key_hex': hex(key),
                        'private_key_dec': key,
                        'address': address
                    }
                    
            except Exception as e:
                continue
                
        return None
    
    def worker_process(self, worker_id, total_workers, keys_per_worker):
        """Worker process for parallel scanning"""
        # Each worker scans a different portion
        worker_start = self.start_range + (worker_id * keys_per_worker)
        worker_end = min(worker_start + keys_per_worker, self.end_range)
        
        current_key = worker_start
        batch_size = 10000  # Larger batches for better performance
        
        while current_key < worker_end:
            result = self.batch_scan(current_key, batch_size)
            
            if result:
                return result
                
            # Update shared counter
            with self.counter.get_lock():
                self.counter.value += min(batch_size, worker_end - current_key)
                
            current_key += batch_size
            
        return None
    
    def run_parallel_scan(self):
        """Run parallel scanning using all CPU cores"""
        num_workers = cpu_count()
        print(f"\n🚀 Starting {num_workers} parallel workers...")
        
        # Divide keyspace among workers
        total_keys = self.end_range - self.start_range
        keys_per_worker = total_keys // num_workers
        
        # Monitor thread
        import threading
        stop_monitor = threading.Event()
        
        def monitor():
            while not stop_monitor.is_set():
                self.display_stats()
                time.sleep(1)
        
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.start()
        
        try:
            # Create process pool
            with Pool(num_workers) as pool:
                # Start workers
                results = []
                for i in range(num_workers):
                    result = pool.apply_async(
                        self.worker_process,
                        (i, num_workers, keys_per_worker)
                    )
                    results.append(result)
                
                # Wait for results
                for result in results:
                    try:
                        output = result.get(timeout=1)
                        if output and output.get('found'):
                            print("\n" + "🎉" * 30)
                            print("FOUND THE KEY!")
                            print(f"Private Key (Hex): {output['private_key_hex']}")
                            print(f"Private Key (Dec): {output['private_key_dec']}")
                            print(f"Address: {output['address']}")
                            stop_monitor.set()
                            return output
                    except:
                        continue
                        
        except KeyboardInterrupt:
            print("\n⛔ Stopped by user")
        finally:
            stop_monitor.set()
            monitor_thread.join()
    
    def display_stats(self):
        """Display current statistics"""
        # System resources
        process = psutil.Process(os.getpid())
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        ram_usage_mb = memory_info.rss / 1024 / 1024
        
        # Calculate speed
        elapsed = time.time() - self.start_time
        keys_checked = self.counter.value
        keys_per_second = keys_checked / elapsed if elapsed > 0 else 0
        
        # Progress
        total_keys = self.end_range - self.start_range
        progress = (keys_checked / total_keys) * 100 if total_keys > 0 else 0
        
        # Clear and display
        os.system('clear')
        print("=" * 60)
        print(f"🔍 BTC PUZZLE #{self.puzzle_number} SCANNER - OPTIMIZED")
        print("=" * 60)
        print(f"📍 Target: {self.target_address}")
        print(f"🔢 Range: {hex(self.start_range)} to {hex(self.end_range)}")
        print(f"📊 Total Keys: {total_keys:,}")
        print("-" * 60)
        print(f"⚡ Keys Checked: {keys_checked:,}")
        print(f"📈 Progress: {progress:.10f}%")
        print(f"🚀 Speed: {keys_per_second:,.0f} keys/second")
        print(f"⏱️  Elapsed: {elapsed:.0f}s")
        print("-" * 60)
        print(f"💻 CPU: {cpu_percent:.1f}%")
        print(f"🧠 RAM: {ram_usage_mb:.1f} MB")
        print(f"🔧 Mode: {'FAST' if FAST_MODE else 'STANDARD'}")
        print("-" * 60)
        
        if keys_per_second > 0:
            remaining_time = (total_keys - keys_checked) / keys_per_second
            years = remaining_time / (365.25 * 24 * 3600)
            if years > 1000000:
                print(f"⏳ Time Remaining: {years:.1e} years")
            elif years > 1:
                print(f"⏳ Time Remaining: {years:,.0f} years")
            else:
                days = remaining_time / (24 * 3600)
                print(f"⏳ Time Remaining: {days:,.0f} days")

def main():
    print("\n🔐 OPTIMIZED BTC PUZZLE SCANNER")
    print("=" * 60)
    
    # Recommendations for different puzzles
    print("\n📊 Realistic Puzzles for Phone/Termux:")
    print("  • Puzzles 1-30: Instant")
    print("  • Puzzles 31-40: Seconds")
    print("  • Puzzles 41-50: Minutes to hours")
    print("  • Puzzles 51-55: Days to weeks")
    print("  • Puzzles 56+: Not realistic on phone")
    
    try:
        puzzle = int(input("\n🎯 Enter puzzle number: "))
    except:
        print("❌ Invalid input")
        return
    
    scanner = OptimizedBTCScanner(puzzle)
    
    if puzzle > 55:
        print(f"\n⚠️  WARNING: Puzzle #{puzzle} is not realistic on a phone!")
        print(f"   Estimated time: Billions of years")
        confirm = input("   Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            return
    
    # Install optimizations if needed
    if not FAST_MODE and puzzle > 40:
        print("\n💡 TIP: Install fastecdsa for 3-5x speed boost:")
        print("   pip install fastecdsa")
    
    print(f"\n🚀 Starting optimized scan...")
    scanner.run_parallel_scan()

if __name__ == "__main__":
    main()
