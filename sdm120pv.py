#!/usr/bin/env python

from gi.repository import GLib
import platform
import logging
import sys
import os
import _thread
import serial
import configparser

sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext'))
from vedbus import VeDbusService
import minimalmodbus

class DbusSdm120PvService:
    def __init__(
        self,
        servicename,
        deviceinstance,
        paths,
        serial_port,
        productname = 'SDM120 PV',
        customname = 'SDM120 PV',
        connection = 'SDM120 PV service',
        position = 1,
        offset = 0.0
    ):

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

        self._dbusservice = VeDbusService(servicename)
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0xFFFF)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
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

        GLib.timeout_add(1000, self._update)

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

            i = i + offset
        except Exception:
            exception_type, exception_object, exception_traceback = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            print(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")

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
        self._dbusservice['/Ac/L1/Energy/Used'] = round(e, 2) if e is not None else None

        logging.debug("PV: {:.1f} W - {:.1f} V - {:.1f} A".format(p, v, c))

        # if power above 10 W, set status code to 7 (running)
        if self._dbusservice['/Ac/Power'] >= 10:
            if self._dbusservice['/StatusCode'] != 7:
                self._dbusservice['/StatusCode'] = 7
        # else set status code to 8 (standby)
        else:
            if self._dbusservice['/StatusCode'] != 8:
                self._dbusservice['/StatusCode'] = 8

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

        '/Ac/MaxPower': {'initial': int(config['DEFAULT']['max_inverter_power']), 'textformat': _w},
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
        '/Ac/L1/Energy/Used': {'initial': None, 'textformat': _kwh},
    })

    paths_dbus.update({
        '/Ac/L2/Power': {'initial': None, 'textformat': _w},
        '/Ac/L2/Current': {'initial': None, 'textformat': _a},
        '/Ac/L2/Voltage': {'initial': None, 'textformat': _v},
        '/Ac/L2/Frequency': {'initial': None, 'textformat': _hz},
        '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
    })

    paths_dbus.update({
        '/Ac/L3/Power': {'initial': None, 'textformat': _w},
        '/Ac/L3/Current': {'initial': None, 'textformat': _a},
        '/Ac/L3/Voltage': {'initial': None, 'textformat': _v},
        '/Ac/L3/Frequency': {'initial': None, 'textformat': _hz},
        '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh},
    })

    DbusSdm120PvService(
        servicename = 'com.victronenergy.pvinverter.sdm120_pv_' + config['DEFAULT']['device_instance'],
        deviceinstance = int(config['DEFAULT']['device_instance']),
        paths = paths_dbus,
        serial_port = config['DEFAULT']['serial_port'],
        #productname
        customname = config['DEFAULT']['device_name'],
        #connection
        position = int(config['DEFAULT']['inverter_position']),
        offset = float(config['DEFAULT']['meter_offset'])
        )

    logging.info('Connected to dbus and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()

if __name__ == "__main__":
    main()
