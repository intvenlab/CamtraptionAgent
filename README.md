Download this base image: 

(contains 0.1 code)
https://www.dropbox.com/scl/fi/n1x67dzbtq1j2ooclkdjo/camtraption.img?rlkey=snp87gv8mwdriljzs4pg96s4k&dl=0

Flash onto 128gb microsd card using rufus. 

Download these updates: 

https://github.com/intvenlab/CamtraptionAgent

To install the updated files from github, do the following: 


Scp/putty camtraption@192.168.137.192

Put camtraption_agent.py into /home/camtraption
Put *.sh into /home/camtraption/wittypi
Put cmdline.txt and config.txt into /boot (will need to run mount -o remount,rw /boot first)

Reboot

Confirm log files indicate version 0.4 of camtraption agent. 

