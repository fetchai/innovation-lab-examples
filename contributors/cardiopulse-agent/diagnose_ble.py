"""
BLE diagnostic.

Scans for ALL Bluetooth Low Energy devices for 20 seconds and prints whatever
it finds. Use this to confirm:
  1. macOS / your OS will let Python use Bluetooth
  2. Your Garmin watch is actually broadcasting
  3. What name the watch is advertising (so bridge_agent.py can match it)

    python diagnose_ble.py
"""

from __future__ import annotations

import asyncio

from bleak import BleakScanner

HEART_RATE_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"


async def main() -> None:
    print("Scanning for BLE devices for 20 seconds...")
    print("(Make sure your watch is broadcasting HR or in an indoor activity.)\n")

    devices = await BleakScanner.discover(timeout=20.0, return_adv=True)

    if not devices:
        print("No devices found at all.")
        print()
        print("If this surprises you, the most likely cause is macOS not having")
        print("granted Python permission to use Bluetooth.")
        print("Fix: System Settings -> Privacy & Security -> Bluetooth")
        print("Add Terminal (or whatever shell you're using) to the list.")
        return

    print(f"Found {len(devices)} device(s):\n")

    has_garmin = False
    has_hr = False

    for addr, (device, adv) in devices.items():
        name = device.name or adv.local_name or "(no name)"
        services = list(adv.service_uuids or [])
        rssi = adv.rssi

        is_garmin = "garmin" in name.lower() or "forerunner" in name.lower()
        advertises_hr = HEART_RATE_SERVICE in services

        if is_garmin:
            has_garmin = True
        if advertises_hr:
            has_hr = True

        marker = ""
        if is_garmin and advertises_hr:
            marker = " <-- THIS IS YOUR WATCH BROADCASTING HR"
        elif is_garmin:
            marker = " <-- Garmin device but NOT broadcasting HR right now"
        elif advertises_hr:
            marker = " <-- BLE device advertising HR (possible match)"

        print(f"  {name}")
        print(f"    address: {addr}")
        print(f"    RSSI:    {rssi} dBm")
        if services:
            print(f"    services: {services}")
        if marker:
            print(f"    {marker}")
        print()

    print("---")
    if has_garmin and has_hr:
        print("Watch detected and broadcasting HR. bridge_agent.py should work.")
    elif has_garmin and not has_hr:
        print("Found your Garmin watch but it isn't broadcasting HR.")
        print("Fix: on the watch, enable Broadcast HR or start an indoor activity.")
    elif has_hr and not has_garmin:
        print("Found an HR-broadcasting device but its name doesn't contain")
        print("'Garmin' or 'Forerunner'. Note the device name above and update")
        print("the GARMIN_NAME variable in your .env file to match.")
    else:
        print("No Garmin watch and no HR broadcaster found.")
        print("Most likely: HR broadcast isn't actually on. Try:")
        print("  1. On the watch, hold the upper-left button")
        print("  2. Settings -> Sensors & Accessories -> Wrist Heart Rate")
        print("  3. Select 'Broadcast Heart Rate' -> Broadcast")
        print("  4. Keep that screen open while you rerun this script")


if __name__ == "__main__":
    asyncio.run(main())
