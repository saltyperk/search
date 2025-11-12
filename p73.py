#!/usr/bin/env python3
"""
Bitcoin Puzzle Key Range Scanner - Educational Purpose Only
Demonstrates key generation and address checking with resource monitoring
"""

import os
import sys
import time
import hashlib
import random
import psutil
from datetime import datetime
from multiprocessing import Process, Queue, cpu_count
import signal

# For Termux, install required packages:
# pkg install python python-pip
# pip install psutil ecdsa base58

try:
    import ecdsa
    import base58
except ImportError:
    print("Installing required packages...")
    os.system("pip install ecdsa base58 psutil")
    import ecdsa
    import base58

class BTCPuzzleScanner:
    def __init__(self, puzzle_number):
        self.puzzle_number = puzzle_number
        self.start_range = 2 ** (puzzle_number - 1)
        self.end_range = 2 ** puzzle_number - 1
        self.total_keys = self.end_range - self.start_range + 1
        
        # Known puzzle addresses (add more as needed)
        self.puzzle_addresses = {
            1: "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH",
            2: "1CUNEBjYrCn2y1SdiUMohaKUi4wpP326Lb",
            3: "19ZewH8Kk1PDbSNdJ97FP4EiCjTRaZMZQA",
            # ... add more puzzle addresses
            64: "16jY7qLJnxb7CHZyqBP8qca9d51gAjyXQN",
            65: "18ZMbwUFLMHoZBbfpCjUJQTCMCbktshgpe",
            66: "13zb1hQbWVsc2S7ZTZnP2G4undNNpdh5so",
            # Add target addresses you're searching for
        }
        
        self.target_address = self.puzzle_addresses.get(puzzle_number, "")
        self.keys_checked = 0
        self.start_time = time.time()
        
    def private_key_to_address(self, private_key_int):
        """Convert private key integer to Bitcoin address"""
        # Convert integer to 32-byte hex
        private_key_hex = format(private_key_int, '064x')
        private_key_bytes = bytes.fromhex(private_key_hex)
        
        # Generate public key using ECDSA
        sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        vk = sk.verifying_key
        public_key = b'\x04' + vk.to_string()
        
        # Perform SHA-256 hashing
        sha256_hash = hashlib.sha256(public_key).digest()
        
        # Perform RIPEMD-160 hashing
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256_hash)
        hashed_public_key = ripemd160.digest()
        
        # Add version byte (0x00 for mainnet)
        versioned_key = b'\x00' + hashed_public_key
        
        # Perform double SHA-256 for checksum
        checksum = hashlib.sha256(hashlib.sha256(versioned_key).digest()).digest()[:4]
        
        # Create final address
        address_bytes = versioned_key + checksum
        address = base58.b58encode(address_bytes).decode('utf-8')
        
        return address
    
    def scan_sequential(self, start, end, queue):
        """Sequential scanning of key range"""
        for key in range(start, min(end, self.end_range + 1)):
            try:
                address = self.private_key_to_address(key)
                self.keys_checked += 1
                
                # Check if we found the target
                if address == self.target_address:
                    result = {
                        'found': True,
                        'private_key': hex(key),
                        'address': address,
                        'decimal_key': key
                    }
                    queue.put(result)
                    return result
                    
            except Exception as e:
                continue
        
        return None
    
    def scan_random(self, num_attempts, queue):
        """Random scanning within key range"""
        for _ in range(num_attempts):
            key = random.randint(self.start_range, self.end_range)
            try:
                address = self.private_key_to_address(key)
                self.keys_checked += 1
                
                if address == self.target_address:
                    result = {
                        'found': True,
                        'private_key': hex(key),
                        'address': address,
                        'decimal_key': key
                    }
                    queue.put(result)
                    return result
                    
            except Exception as e:
                continue
        
        return None
    
    def display_stats(self):
        """Display scanning statistics and resource usage"""
        # Get system resource usage
        process = psutil.Process(os.getpid())
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        ram_usage_mb = memory_info.rss / 1024 / 1024
        
        # Calculate scanning speed
        elapsed_time = time.time() - self.start_time
        keys_per_second = self.keys_checked / elapsed_time if elapsed_time > 0 else 0
        
        # Calculate progress
        if self.total_keys > 0:
            progress = (self.keys_checked / self.total_keys) * 100
        else:
            progress = 0
        
        # Clear screen (works in Termux)
        os.system('clear')
        
        print("=" * 60)
        print(f"🔍 BTC PUZZLE #{self.puzzle_number} SCANNER")
        print("=" * 60)
        print(f"📍 Target Address: {self.target_address}")
        print(f"🔢 Range: {hex(self.start_range)} to {hex(self.end_range)}")
        print(f"📊 Total Keys in Range: {self.total_keys:,}")
        print("-" * 60)
        print(f"⚡ Keys Checked: {self.keys_checked:,}")
        print(f"📈 Progress: {progress:.10f}%")
        print(f"⏱️  Speed: {keys_per_second:.2f} keys/second")
        print(f"⌛ Time Elapsed: {elapsed_time:.2f} seconds")
        print("-" * 60)
        print(f"💻 CPU Usage: {cpu_percent:.1f}%")
        print(f"🧠 RAM Usage: {ram_usage_mb:.2f} MB")
        print(f"🔧 CPU Cores: {cpu_count()}")
        print(f"📱 System RAM: {psutil.virtual_memory().total / 1024 / 1024:.0f} MB")
        print("-" * 60)
        
        if self.total_keys > 0 and keys_per_second > 0:
            estimated_time = (self.total_keys - self.keys_checked) / keys_per_second
            print(f"⏳ Estimated Time to Complete: {self.format_time(estimated_time)}")
        
        print("=" * 60)
        print("Press Ctrl+C to stop")
    
    def format_time(self, seconds):
        """Format seconds into readable time"""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            return f"{seconds/60:.0f} minutes"
        elif seconds < 86400:
            return f"{seconds/3600:.1f} hours"
        elif seconds < 31536000:
            return f"{seconds/86400:.1f} days"
        else:
            return f"{seconds/31536000:.1f} years"

def main():
    print("\n" + "=" * 60)
    print("BTC PUZZLE KEY SCANNER - EDUCATIONAL PURPOSE ONLY")
    print("=" * 60)
    
    # Get puzzle number
    try:
        puzzle = int(input("\n🎯 Enter puzzle number (1-256): "))
        if puzzle < 1 or puzzle > 256:
            print("❌ Invalid puzzle number!")
            return
    except ValueError:
        print("❌ Please enter a valid number!")
        return
    
    # Choose scanning method
    print("\n📋 Select scanning method:")
    print("1. Sequential (start from beginning)")
    print("2. Random (random keys in range)")
    print("3. Sequential from middle")
    
    method = input("\n👉 Choice (1-3): ")
    
    # Initialize scanner
    scanner = BTCPuzzleScanner(puzzle)
    
    if not scanner.target_address:
        print(f"⚠️  Warning: No known address for puzzle #{puzzle}")
        custom = input("Enter target address (or press Enter to continue): ")
        if custom:
            scanner.target_address = custom
    
    print(f"\n🎯 Starting scan for Puzzle #{puzzle}")
    print(f"📍 Target: {scanner.target_address}")
    print(f"🔢 Range: {scanner.start_range:,} to {scanner.end_range:,}")
    print(f"📊 Total keys: {scanner.total_keys:,}")
    
    input("\n⚡ Press Enter to start scanning...")
    
    # Setup queue for multiprocessing
    result_queue = Queue()
    
    try:
        # Scanning loop
        while True:
            if method == "1":
                # Sequential scan
                scanner.scan_sequential(
                    scanner.start_range + scanner.keys_checked,
                    scanner.start_range + scanner.keys_checked + 10000,
                    result_queue
                )
            elif method == "2":
                # Random scan
                scanner.scan_random(10000, result_queue)
            else:
                # Sequential from middle
                middle = (scanner.start_range + scanner.end_range) // 2
                scanner.scan_sequential(
                    middle + scanner.keys_checked,
                    middle + scanner.keys_checked + 10000,
                    result_queue
                )
            
            # Check for results
            if not result_queue.empty():
                result = result_queue.get()
                print("\n" + "🎉" * 20)
                print("FOUND KEY!")
                print(f"Private Key (Hex): {result['private_key']}")
                print(f"Private Key (Dec): {result['decimal_key']}")
                print(f"Address: {result['address']}")
                print("🎉" * 20)
                break
            
            # Display statistics
            scanner.display_stats()
            time.sleep(0.1)  # Small delay to reduce CPU usage
            
    except KeyboardInterrupt:
        print("\n\n⛔ Scanning stopped by user")
        print(f"📊 Total keys checked: {scanner.keys_checked:,}")
        print(f"⏱️  Time elapsed: {time.time() - scanner.start_time:.2f} seconds")

if __name__ == "__main__":
    main()
