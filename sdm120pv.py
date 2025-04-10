#!/usr/bin/env python

from gi.repository import GLib
import platform
import logging
import sys
import os
import _thread
import serial
import configparser
import json
import dbus
import dbus.service

sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext'))
from vedbus import VeDbusService
import minimalmodbus

import paho.mqtt.client
import ssl

class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)

class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)

def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()

class DbusSdm120PvService:
    def __init__(
        self,
        deviceinstance1,
        deviceinstance2,
        paths,
        serial_port,
        productname1 = 'PV house',
        productname2 = 'PV barn',
        max_power1 = 2400,
        max_power2 = 600,
        position = 1,
        offset = 0.0,
        mqtt_host = 'localhost',
        mqtt_port = 8883,
        mqtt_username = '',
        mqtt_password = ''
    ):

        logging.basicConfig(level=logging.WARNING)
        #logging.basicConfig(level=logging.INFO)

        self._offset = offset;

        #https://minimalmodbus.readthedocs.io/en/stable/usage.html
        self._instrument = minimalmodbus.Instrument(serial_port, 1)
        self._instrument.serial.baudrate = 9600
        self._instrument.serial.bytesize = 8
        self._instrument.serial.parity   = serial.PARITY_NONE
        self._instrument.serial.stopbits = 1
        self._instrument.serial.timeout  = 0.1
        self._instrument.mode = minimalmodbus.MODE_RTU
        #self._instrument.debug = True

        #30001 Voltage Volts 0000
        #30007 Current Amps 0006
        #30013 Active Power Watts 000C
        #30019 Apparent Power VoltAmps 0012
        #30025 Reactive Power VAr 0018
        #30031 Power Factor None 001E
        #30037 Phase Angle Degrees 0024
        #30071 Frequency Hz 0046
        #30073 Import Active Energy kWh 0048
        #30075 Export Active Energy kWh 004A
        #30077 Import Reactive Energy kVArh 004C
        #30079 Export Reactive Energy kVArh 004E

        #30085 Total system power demand W 0054
        #30087 Maximum total system power demand W 0056
        #30089 Import system power demand W 0058
        #30091 Maximum Import system power demand W 005A
        #30093 Export system power demand W 005C
        #30095 Maximum Export system power demand W 005E
        #30259 Current demand Amps 0102
        #30265 Maximum current demand Amps 0108

        #30343 Total Active Energy kWh 0156
        #30345 Total Reactive Energy kVArh 0158

        self._dbusservice = VeDbusService('com.victronenergy.pvinverter.sdm120_pv_' + str(deviceinstance1), dbusconnection())
        self._paths = paths

        logging.debug("DeviceInstance = %d" % (deviceinstance1))

        # Create the management objects
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', productname1 + ' service')

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance1)
        self._dbusservice.add_path('/ProductId', 0xFFFF)
        self._dbusservice.add_path('/ProductName', productname1)
        self._dbusservice.add_path('/CustomName', productname1)
        self._dbusservice.add_path('/FirmwareVersion', '0.1')
        # self._dbusservice.add_path('/HardwareVersion', '')
        self._dbusservice.add_path('/Connected', 1)

        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/ErrorCode', 0)
        self._dbusservice.add_path('/Position', position)
        self._dbusservice.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path,
                settings['initial'],
                gettextcallback = settings['textformat'],
                writeable = True,
                onchangecallback = self._handlechangedvalue
                )

        self._dbusservice['/Ac/MaxPower'] = max_power1

        self._dbusservice_aux = VeDbusService('com.victronenergy.pvinverter.sdm120_pv_' + str(deviceinstance2), dbusconnection())

        # Create the management objects
        self._dbusservice_aux.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice_aux.add_path('/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
        self._dbusservice_aux.add_path('/Mgmt/Connection', productname2 + ' service')

        # Create the mandatory objects
        self._dbusservice_aux.add_path('/DeviceInstance', deviceinstance2)
        self._dbusservice_aux.add_path('/ProductId', 0xFFFF)
        self._dbusservice_aux.add_path('/ProductName', productname2)
        self._dbusservice_aux.add_path('/CustomName', productname2)
        self._dbusservice_aux.add_path('/FirmwareVersion', '0.1')
        # self._dbusservice.add_path('/HardwareVersion', '')
        self._dbusservice_aux.add_path('/Connected', 1)

        self._dbusservice_aux.add_path('/Latency', None)
        self._dbusservice_aux.add_path('/ErrorCode', 0)
        self._dbusservice_aux.add_path('/Position', position)
        self._dbusservice_aux.add_path('/StatusCode', 0)  # Dummy path so VRM detects us as a PV-inverter

        for path, settings in self._paths.items():
            self._dbusservice_aux.add_path(
                path,
                settings['initial'],
                gettextcallback = settings['textformat'],
                writeable = True,
                onchangecallback = self._handlechangedvalue
                )

        self._dbusservice_aux['/Ac/MaxPower'] = max_power2

        GLib.timeout_add(1000, self._update)

        logging.info("MQTT: connecting")
        #self._mqtt_client = paho.mqtt.client.Client('victron_pv')
        self._mqtt_client = paho.mqtt.client.Client(paho.mqtt.client.CallbackAPIVersion.VERSION1, 'victron_pv')
        self._mqtt_client.tls_set(cert_reqs = ssl.CERT_NONE)
        self._mqtt_client.tls_insecure_set(True)
        self._mqtt_client.username_pw_set(mqtt_username, password = mqtt_password)
        self._mqtt_client.connect(mqtt_host, port = mqtt_port)
        self._mqtt_client.on_connect = self._mqtt_on_connect
        self._mqtt_client.on_message = self._mqtt_on_message
        self._mqtt_client.loop_start()

    def _mqtt_on_connect(self, client, userdata, rc, args):
        logging.info("MQTT: connected")
        self._mqtt_client.subscribe('zigbee2mqtt-vde194/schuur_pv_0xa4c1381013698826')

    def _mqtt_on_message(self, client, userdata, msg):
        try:
            dmsg = str(msg.payload.decode("utf-8"))
            if dmsg is None:
                return
            jmsg = json.loads(dmsg)

            #{
            #  "current": 1.3,
            #  "energy": 0,
            #  "linkquality": 0,
            #  "power": 294,
            #  "produced_energy": null,
            #  "state": "ON",
            #  "voltage": 231.6
            #}

            self._dbusservice_aux['/Ac/Power'] = jmsg['power']
            self._dbusservice_aux['/Ac/Current'] = jmsg['current']
            self._dbusservice_aux['/Ac/Voltage'] = jmsg['voltage']
            self._dbusservice_aux['/Ac/L1/Power'] = jmsg['power']
            self._dbusservice_aux['/Ac/L1/Current'] = jmsg['current']
            self._dbusservice_aux['/Ac/L1/Voltage'] = jmsg['voltage']

            if self._dbusservice_aux['/Ac/Power'] is not None and self._dbusservice_aux['/Ac/Power'] >= 10:
                if self._dbusservice_aux['/StatusCode'] != 7:
                    self._dbusservice_aux['/StatusCode'] = 7 #running
            else:
                if self._dbusservice_aux['/StatusCode'] != 8:
                    self._dbusservice_aux['/StatusCode'] = 8 #standby

            index = self._dbusservice_aux['/UpdateIndex'] + 1
            if index > 255:
                index = 0
            self._dbusservice_aux['/UpdateIndex'] = index

            logging.info("PV: %s=%s" % (msg.topic, msg.payload))
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            print(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
            logging.error(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")

    def _update(self):
        v = None
        c = None
        a = None
        p = None
        f = None
        i = None
        e = None
        t = None

        try:
            v = self._instrument.read_float(0x0000, 4, 2) #Voltage
            c = self._instrument.read_float(0x0006, 4, 2) #Current
            a = self._instrument.read_float(0x000C, 4, 2) #Active power
            p = self._instrument.read_float(0x001E, 4, 2) #Power factor
            f = self._instrument.read_float(0x0046, 4, 2) #Frequency
            i = self._instrument.read_float(0x0048, 4, 2) #Import active
            e = self._instrument.read_float(0x004A, 4, 2) #Export active
            t = self._instrument.read_float(0x0156, 4, 2) #Total active

            i = i + self._offset

            logging.info("PV: {:.1f} W - {:.1f} V - {:.1f} A - {:.1f} Import".format(a, v, c, i))

        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            print(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
            logging.error(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")

        self._dbusservice['/Ac/Power'] = round(a, 2) if a is not None else None
        self._dbusservice['/Ac/Current'] = round(c, 2) if c is not None else None
        self._dbusservice['/Ac/Voltage'] = round(v, 2) if v is not None else None
        self._dbusservice['/Ac/Energy/Forward'] = round(i, 2) if i is not None else None

        self._dbusservice['/Ac/L1/Power'] = round(a, 2) if a is not None else None
        self._dbusservice['/Ac/L1/Current'] = round(c, 2) if c is not None else None
        self._dbusservice['/Ac/L1/Voltage'] = round(v, 2) if v is not None else None
        self._dbusservice['/Ac/L1/Frequency'] = round(f, 2) if f is not None else None
        self._dbusservice['/Ac/L1/PowerFactor'] = round(p, 2) if p is not None else None
        self._dbusservice['/Ac/L1/Energy/Forward'] = round(i, 2) if i is not None else None
        self._dbusservice['/Ac/L1/Energy/Reverse'] = round(e, 2) if e is not None else None

        if self._dbusservice['/Ac/Power'] is not None and self._dbusservice['/Ac/Power'] >= 10:
            if self._dbusservice['/StatusCode'] != 7:
                self._dbusservice['/StatusCode'] = 7 #running
        else:
            if self._dbusservice['/StatusCode'] != 8:
                self._dbusservice['/StatusCode'] = 8 #standby

        # increment UpdateIndex - to show that new data is available
        index = self._dbusservice['/UpdateIndex'] + 1
        if index > 255:
            index = 0
        self._dbusservice['/UpdateIndex'] = index
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True  # accept the change

def main():
    _thread.daemon = True  # allow the program to quit

    from dbus.mainloop.glib import DBusGMainLoop

    DBusGMainLoop(set_as_default=True)

    config_file = (os.path.dirname(os.path.realpath(__file__))) + "/config.ini"
    config = configparser.ConfigParser()
    config.read(config_file)

    # formatting
    def _kwh(p, v): return (str("%.2f" % v) + "kWh")
    def _a(p, v): return (str("%.1f" % v) + "A")
    def _w(p, v): return (str("%i" % v) + "W")
    def _v(p, v): return (str("%.2f" % v) + "V")
    def _hz(p, v): return (str("%.4f" % v) + "Hz")
    def _n(p, v): return (str("%i" % v))
    def _pf(p, v): return (str("%.2f" % v))

    paths_dbus = {
        '/Ac/Power': {'initial': 0, 'textformat': _w},
        '/Ac/Current': {'initial': 0, 'textformat': _a},
        '/Ac/Voltage': {'initial': 0, 'textformat': _v},
        '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh},
        '/Ac/Energy/Reverse': {'initial': None, 'textformat': _kwh},

        '/Ac/MaxPower': {'initial': 0, 'textformat': _w},
        '/Ac/Position': {'initial': int(config['DEFAULT']['inverter_position']), 'textformat': _n},
        '/Ac/StatusCode': {'initial': 0, 'textformat': _n},
        '/UpdateIndex': {'initial': 0, 'textformat': _n},
    }

    paths_dbus.update({
        '/Ac/L1/Power': {'initial': None, 'textformat': _w},
        '/Ac/L1/Current': {'initial': None, 'textformat': _a},
        '/Ac/L1/Voltage': {'initial': None, 'textformat': _v},
        '/Ac/L1/Frequency': {'initial': None, 'textformat': _hz},
        '/Ac/L1/PowerFactor': {'initial': None, 'textformat': _pf},
        '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': _kwh},
        '/Ac/L1/Energy/Reverse': {'initial': None, 'textformat': _kwh},
    })

    paths_dbus.update({
        '/Ac/L2/Power': {'initial': None, 'textformat': _w},
        '/Ac/L2/Current': {'initial': None, 'textformat': _a},
        '/Ac/L2/Voltage': {'initial': None, 'textformat': _v},
        '/Ac/L2/Frequency': {'initial': None, 'textformat': _hz},
        '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
        '/Ac/L2/Energy/Reverse': {'initial': None, 'textformat': _kwh},
    })

    paths_dbus.update({
        '/Ac/L3/Power': {'initial': None, 'textformat': _w},
        '/Ac/L3/Current': {'initial': None, 'textformat': _a},
        '/Ac/L3/Voltage': {'initial': None, 'textformat': _v},
        '/Ac/L3/Frequency': {'initial': None, 'textformat': _hz},
        '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh},
        '/Ac/L3/Energy/Reverse': {'initial': None, 'textformat': _kwh},
    })

    DbusSdm120PvService(
        deviceinstance1 = int(config['DEFAULT']['device_instance_1']),
        deviceinstance2 = int(config['DEFAULT']['device_instance_2']),
        paths = paths_dbus,
        serial_port = config['DEFAULT']['serial_port'],
        productname1 = config['DEFAULT']['device_name_1'],
        productname2 = config['DEFAULT']['device_name_2'],
        max_power1 = int(config['DEFAULT']['max_inverter_power_1']),
        max_power2 = int(config['DEFAULT']['max_inverter_power_2']),
        position = int(config['DEFAULT']['inverter_position']),
        offset = float(config['DEFAULT']['meter_offset']),
        mqtt_host = config['DEFAULT']['mqtt_host'],
        mqtt_port = int(config['DEFAULT']['mqtt_port']),
        mqtt_username = config['DEFAULT']['mqtt_username'],
        mqtt_password = config['DEFAULT']['mqtt_password']
        )

    logging.info('Connected to dbus and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == "__main__":
    main()
