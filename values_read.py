"""
ESP32 to Firebase Data Bridge
Receives sensor data from ESP32 via serial and uploads to Firebase
"""

import serial
import json
import time
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import threading
import queue

class ESP32FirebaseBridge:
    def __init__(self, serial_port='COM5', baud_rate=115200):
        # Serial configuration
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.ser = None
        
        # Firebase configuration
        self.init_firebase()
        
        # Data queue for thread safety
        self.data_queue = queue.Queue()
        
        # Status tracking
        self.connected = False
        self.total_uploads = 0
        
    def init_firebase(self):
        """Initialize Firebase connection"""
        try:
            # Replace with your service account key path
            cred = credentials.Certificate('service_account.json')
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://isro-ar-default-rtdb.asia-southeast1.firebasedatabase.app'
            })
            print("✓ Firebase initialized successfully")
        except Exception as e:
            print(f"✗ Firebase initialization error: {e}")
    
    def connect_serial(self):
        """Establish serial connection with ESP32"""
        try:
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=1
            )
            time.sleep(2)  # Wait for ESP32 to reset
            self.connected = True
            print(f"✓ Connected to ESP32 on {self.serial_port}")
            return True
        except Exception as e:
            print(f"✗ Serial connection error: {e}")
            return False
    
    def read_serial_data(self):
        """Read and parse JSON data from ESP32"""
        while self.connected:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    raw_data = self.ser.readline().decode('utf-8').strip()
                    
                    if raw_data and raw_data.startswith('{'):
                        try:
                            sensor_data = json.loads(raw_data)
                            self.data_queue.put(sensor_data)
                            print(f"📥 Received: T={sensor_data.get('temperature', 'N/A')}°C, "
                                  f"P={sensor_data.get('pressure', 'N/A')}hPa, "
                                  f"L={sensor_data.get('light', 'N/A')}")
                        except json.JSONDecodeError:
                            print(f"⚠️ Invalid JSON: {raw_data[:50]}...")
                    elif raw_data and not raw_data.startswith('INFO') and not raw_data.startswith('ERROR'):
                        print(f"📝 ESP32: {raw_data}")
                        
            except Exception as e:
                print(f"✗ Serial read error: {e}")
                time.sleep(1)
            
            time.sleep(0.1)
    
    def upload_to_firebase(self, data):
        """Upload sensor data to Firebase"""
        try:
            # Add Python timestamp
            data['python_timestamp'] = datetime.now().isoformat()
            data['upload_id'] = self.total_uploads + 1
            
            # Create Firebase reference
            ref = db.reference('/UsersData/esp32_sensors/sensor_data')
            
            # Push data with auto-generated key
            new_ref = ref.push(data)
            
            self.total_uploads += 1
            print(f"🔥 Firebase upload #{self.total_uploads} successful: {new_ref.key}")
            
            return True
            
        except Exception as e:
            print(f"✗ Firebase upload error: {e}")
            return False
    
    def process_firebase_uploads(self):
        """Process Firebase uploads from queue"""
        while True:
            try:
                if not self.data_queue.empty():
                    data = self.data_queue.get()
                    self.upload_to_firebase(data)
                    self.data_queue.task_done()
                else:
                    time.sleep(0.5)
            except Exception as e:
                print(f"✗ Firebase processing error: {e}")
                time.sleep(1)
    
    def run(self):
        """Main execution loop"""
        print("🚀 Starting ESP32-Firebase Bridge...")
        
        if not self.connect_serial():
            return
        
        # Start threads
        serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        firebase_thread = threading.Thread(target=self.process_firebase_uploads, daemon=True)
        
        serial_thread.start()
        firebase_thread.start()
        
        print("📡 Bridge running. Press Ctrl+C to stop...")
        
        try:
            while True:
                time.sleep(1)
                
                # Status update every 30 seconds
                if self.total_uploads > 0 and self.total_uploads % 6 == 0:
                    print(f"📊 Status: {self.total_uploads} uploads completed")
                    
        except KeyboardInterrupt:
            print("\n🛑 Stopping bridge...")
            self.connected = False
            if self.ser:
                self.ser.close()
            print("✅ Bridge stopped")
""" This is the main method """
def main():
    # Configuration
    SERIAL_PORT = 'COM4'  # Change to your port (Linux: /dev/ttyUSB0)
    BAUD_RATE = 115200
    
    # Create and run bridge
    bridge = ESP32FirebaseBridge(SERIAL_PORT, BAUD_RATE)
    bridge.run()

if __name__ == "__main__":
    main()
