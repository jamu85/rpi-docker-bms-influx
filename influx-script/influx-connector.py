#!/usr/bin/env python
#coding: utf8

from influxdb_client import InfluxDBClient
import gatt
import json
import sys
import time
import os

from time import gmtime, strftime

# Your InfluxDB Settings
influx_host = os.getenv('INFLUX_HOST', 'influxdb')
influx_port = os.getenv('INFLUX_PORT', 8086)
influx_user = os.getenv('INFLUX_USER', None)
influx_pass = os.getenv('INFLUX_PASS', None)
influx_db = os.getenv('INFLUX_DB', 'bmsd')

# Number of seconds between updates
update_interval = os.getenv('UPDATE_INTERVAL', 10)

# --------------------------------------------------------------------------------
# Do not change anything below this line
hostname = socket.gethostname()

# --------------------------------------------------------------------------------
# Create a device manager for bt interface
manager = gatt.DeviceManager(adapter_name='hci0')

# --------------------------------------------------------------------------------
# BMS BLE Reader Thread
class AnyDevice(gatt.Device):
    def  __init__(self, c, **kwargs):
        super().__init__(**kwargs)
        self.c=c

    def connect_succeeded(self):
        super().connect_succeeded()
        print("[%s] Connected" % (self.mac_address))

    def connect_failed(self, error):
        super().connect_failed(error)
        print("[%s] Connection failed: %s" % (self.mac_address, str(error)))
        exit(1)

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        print("[%s] Disconnected" % (self.mac_address))
    #    self.manager.stop()

    def services_resolved(self):
        super().services_resolved()

        device_information_service = next(
            s for s in self.services
            if s.uuid == '0000ff00-0000-1000-8000-00805f9b34fb')

        self.bms_read_characteristic = next(
            c for c in device_information_service.characteristics
            if c.uuid == '0000ff01-0000-1000-8000-00805f9b34fb')

        self.bms_write_characteristic = next(
            c for c in device_information_service.characteristics
            if c.uuid == '0000ff02-0000-1000-8000-00805f9b34fb')

        print("BMS found")
        self.bms_read_characteristic.enable_notifications()

    def characteristic_enable_notifications_succeeded(self, characteristic):
        super().characteristic_enable_notifications_succeeded(characteristic)
        print("BMS request generic data")
        self.response=bytearray()
        self.rawdat={}
        self.get_voltages=False
        self.bms_write_characteristic.write_value(bytes([0xDD,0xA5,0x03,0x00,0xFF,0xFD,0x77]));

    def characteristic_enable_notifications_failed(self, characteristic, error):
        super.characteristic_enable_notifications_failed(characteristic, error)
        print("BMS notification failed:",error)

    def characteristic_value_updated(self, characteristic, value):
        print("BMS answering")
        self.response+=value
        if (self.response.endswith(b'w')):
            print("BMS answer:", self.response.hex())
            self.response=self.response[4:]
            if (self.get_voltages):
                packVolts=0
                for i in range(int(len(self.response)/2)-1):
                    cell=int.from_bytes(self.response[i*2:i*2+2], byteorder = 'big')/1000
                    self.rawdat['V{0:0=2}'.format(i+1)]=cell
                    packVolts+=cell
                # + self.rawdat['V{0:0=2}'.format(i)]
                self.rawdat['Vbat']=packVolts
                self.rawdat['P']=round(self.rawdat['Vbat']*self.rawdat['Ibat'], 1)
                self.rawdat['State']=int.from_bytes(self.response[16:18], byteorder = 'big',signed=True)
                print(self.rawdat)
                print("BMS chat ended")
                print (json.dumps(self.rawdat, indent=1, sort_keys=True))
                influx_json_body = [
                  {
                    "measurement": "bmsd-python",
                    "tags": {
                      "host": hostname
                    },
                    "fields": {
                      "ah_percent": self.rawdat['Ah_percent'],
                      "ah_remaining": self.rawdat['Ah_remaining'],
                      "ah_full": self.rawdat['Ah_full'],
                      "p": self.rawdat['P'],
                      "v_bat": self.rawdat['Vbat'],
                      "i_bat": self.rawdat['Ibat'],
                      "t1": self.rawdat['T1'],
                      "cycles": self.rawdat['Cycles']
                    }
                  }
                ]

                influx_client = InfluxDBClient(influx_host, influx_port, influx_user, influx_pass, influx_db)

                influx_client.write_points(influx_json_body)
                print("Capacity: {capacity}% ({Ah_remaining} of {Ah_full}Ah)\nPower: {power}W ({I}Ah)\nTemperature: {temp}°C\nCycles: {cycles}".format(
                    capacity=self.rawdat['Ah_percent'],
                    Ah_remaining=self.rawdat['Ah_remaining'],
                    Ah_full=self.rawdat['Ah_full'],
                    power=self.rawdat['P'],
                    I=self.rawdat['Ibat'],
                    temp=self.rawdat['T1'],
                    cycles=self.rawdat['Cycles'],
                    ))
                #self.disconnect();
                self.manager.stop()
            else:
                self.rawdat['packV']=int.from_bytes(self.response[0:2], byteorder = 'big',signed=True)/100.0
                self.rawdat['Ibat']=int.from_bytes(self.response[2:4], byteorder = 'big',signed=True)/100.0
                self.rawdat['Bal']=int.from_bytes(self.response[12:14],byteorder = 'big',signed=False)
                self.rawdat['Ah_remaining']=int.from_bytes(self.response[4:6], byteorder='big', signed=True)/100
                self.rawdat['Ah_full']=int.from_bytes(self.response[6:8], byteorder='big', signed=True)/100
                self.rawdat['Ah_percent']=round(self.rawdat['Ah_remaining'] / self.rawdat['Ah_full'] * 100, 2)
                self.rawdat['Cycles']=int.from_bytes(self.response[8:10], byteorder='big', signed=True)

                for i in range(int.from_bytes(self.response[22:23],'big')): # read temperatures
                    self.rawdat['T{0:0=1}'.format(i+1)]=(int.from_bytes(self.response[23+i*2:i*2+25],'big')-2731)/10

                print("BMS request voltages")
                self.get_voltages=True
                self.response=bytearray()
                self.bms_write_characteristic.write_value(bytes([0xDD,0xA5,0x04,0x00,0xFF,0xFC,0x77]));

    def characteristic_write_value_failed(self, characteristic, error):
        pass
        print("BMS write failed:",error)

# --------------------------------------------------------------------------------
# BMS Loop

if __name__ == '__main__':
  try:
      print(strftime("%Y-%m-%d %H:%M:%S", gmtime()))
      device = AnyDevice(mac_address=sys.argv[1], manager=manager, c=c)
      device.connect()
      manager.run()
      time.sleep(int(update_interval))

  except (KeyboardInterrupt, SystemExit): #when you press ctrl+c
    print("\nKilling Thread...")
  print("Done.\nExiting.")
