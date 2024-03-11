# sdm120pv
Victron dbus driver for SDM120 modbus

1. Copy the files to /data/etc/sdm120pv
2. Edit config.ini
3. Modify /etc/udev/rules.d/serial-starter.rules, see install.sh for some information
4. Add ln -s /data/etc/sdm120pv/service /service/sdm120p to /data/rc.local

I'm assuming you know what you are doing, so this should be enough to get you started.
