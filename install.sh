#!/bin/bash

chmod +x sdm120pv.py
chmod +x service/run
chmod +x service/log/run

ln -s /data/etc/sdm120pv/service /service/sdm120pv

#svstat /service/sdm120pv
#tail -n 100 -f /data/log/sdm120pv/current | tai64nlocal
#zip /tmp/sdm120pv.zip *.py ext/*.py *.ini *.sh service/run service/log/run

#https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus
#https://github.com/mr-manuel/venus-os_dbus-mqtt-pv

# nano /data/rc.local
# ln -s /data/etc/sdm120pv/service /service/sdm120pv

# mount -o remount,rw /
# nano /etc/udev/rules.d/serial-starter.rules
# #ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_VENDOR_ID}=="1a86", ENV{ID_MODEL_ID}=="7523", ENV{VE_SERVICE}="cgwacs:default"
# ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_MODEL}=="USB_Serial" ENV{VE_SERVICE}="ignore"
# 1a86:7523 = QinHeng Electronics HL-340 USB-Serial adapter
# mount -o remount,ro /
