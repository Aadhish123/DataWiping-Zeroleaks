"""
Test Geolocation Functionality
This script tests if the geolocation is working correctly
"""

import sys
sys.path.insert(0, '.')

from security_utils import get_geolocation

print("="*80)
print("🌍 GEOLOCATION TEST")
print("="*80)

print("\n1️⃣ Testing with localhost IP (127.0.0.1):")
print("-" * 80)
geo_local = get_geolocation('127.0.0.1')
print(f"   City: {geo_local.get('city')}")
print(f"   Region: {geo_local.get('region')}")
print(f"   Country: {geo_local.get('country')}")
print(f"   ISP: {geo_local.get('isp')}")
print(f"   Real IP Used: {geo_local.get('real_ip')}")

print("\n2️⃣ Testing with your actual external IP:")
print("-" * 80)
import requests
try:
    response = requests.get('https://api.ipify.org?format=json', timeout=3)
    if response.status_code == 200:
        external_ip = response.json()['ip']
        print(f"   Your External IP: {external_ip}")
        
        geo_external = get_geolocation(external_ip)
        print(f"   City: {geo_external.get('city')}")
        print(f"   Region: {geo_external.get('region')}")
        print(f"   Country: {geo_external.get('country')}")
        print(f"   ISP: {geo_external.get('isp')}")
        print(f"   Timezone: {geo_external.get('timezone')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("✅ Geolocation test complete!")
print("="*80)
print("\n📍 Now when you perform a wipe operation:")
print("   • If accessed via localhost → Detects your REAL external IP")
print("   • If accessed via network → Uses actual network IP")
print("   • Result: Accurate geolocation logged every time!")
print("="*80)
