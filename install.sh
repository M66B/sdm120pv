#!/bin/bash

chmod +x sdm120pv.py
chmod +x service/run
chmod +x service/log/run

ln -s /data/etc/sdm120pv/service /opt/victronenergy/service/sdm120pv

#svstat /service/sdm120pv
#tail -n 100 -f /data/log/sdm120pv/current | tai64nlocal
#zip /tmp/sdm120pv.zip *.py ext/*.py *.ini *.sh service/run service/log/run

#https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus
#https://github.com/mr-manuel/venus-os_dbus-mqtt-pv

# nano /data/rc.local
#!/bin/bash
#rm /service/sdm120pv
#mount -o remount,rw /
#ln -s /data/etc/sdm120pv/service /opt/victronenergy/service/sdm120pv
#sed -i 's/^.*1a86.*/ACTION=="add", ENV{ID_BUS}=="usb", ENV{ID_MODEL}=="USB_Serial" ENV{VE_SERVICE}="ignore"/' /etc/udev/rules.d/serial-starter.rules
#mount -o remount,ro /

#/opt/victronenergy/serial-starter/stop-tty.sh /dev/ttyUSB1
