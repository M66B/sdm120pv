#!/bin/bash

chmod +x sdm120pv.py
chmod +x service/run
chmod +x service/log/run

#svstat /service/sdm120pv
#tail -n 100 -f /data/log/sdm120pv/current | tai64nlocal
#tail -F /data/log/serial-starter/current | tai64nlocal
#zip /tmp/sdm120pv.zip *.py ext/*.py *.ini *.sh service/run service/log/run

#https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus
#https://github.com/mr-manuel/venus-os_dbus-mqtt-pv

#nano /data/conf/serial-starter.d
#service sdm120pv sdm102pv

#nano /data/rc.local
##!/bin/bash
#mount -o remount,rw /
#ln -s /data/etc/sdm120pv/service /opt/victronenergy/service-templates/sdm120pv
#sed -i 's/^.*1a86.*/ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_VENDOR_ID}=="1a86", ENV{ID_MODEL_ID}=="7523", ENV{VE_SERVICE}="sdm120pv"/' /etc/udev/rules.d/serial-start>
#mount -o remount,ro /
