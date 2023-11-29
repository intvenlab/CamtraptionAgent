
import smbus

from dateutil import parser
from datetime import datetime, timedelta
import time
import locale
import logging
import sys
import time
import RPi.GPIO as GPIO
import gphoto2 as gp
import os
import subprocess


version = 0.1

logname = "/var/tmp/camtraption-" + ('{:%Y%m%d-%H%M%S}.log'.format(datetime.now()))

logging.basicConfig(filename=logname,
                    filemode='a',
                    format='%(asctime)s, %(name)s %(levelname)s %(message)s',
#                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    level=logging.DEBUG)

logging.info("Starting camtraption_agent.py version {}".format(version))

pin_wakeup = 26
pin_shutter = 19

def main():
    get_input_voltage()
    get_last_startup_reason()
    get_temp()
    wakeup_camera_gpio()
    shutter_camera_gpio()
    Result, artist_string = camera_config()
    reset_usb()
    shutter_camera_gpio()
    sync_logs_usb()
    os.system('cat {}'.format(logname))
    conditional_shutdown()

def conditional_shutdown():
    wait_time = 140   
    time.sleep(wait_time)
    time_last_login = datetime.fromtimestamp(os.stat("/home/camtraption/.last_login").st_mtime)
    if (time_last_login < datetime.now() - timedelta(seconds=wait_time+60)):
        # not logged in recently, time to shut down
        print ("shutdown...")
        os.system("sudo shutdown -h 'now'")



def camera_config():
    camera = gp.Camera()
    artist_string = ""
    try:
        camera.init()
        cfg = camera.get_config()
        cameradatetime = cfg.get_child_by_name('datetime')
        OK, datetime_config = gp.gp_widget_get_child_by_name(cfg, 'datetime')
        widget_type = datetime_config.get_type()
        raw_value = datetime_config.get_value()
        camera_time = datetime.fromtimestamp(raw_value) # human readable
        set_clock(raw_value)

        artist_cfg = cfg.get_child_by_name('artist')
        artist_string = artist_cfg.get_value()

        OK, mode_dial_config = gp.gp_widget_get_child_by_name(cfg, 'autoexposuremodedial')
        new_mode = parse_time_schedule(artist_string)
        if OK >= gp.GP_OK:
          logging.info("Existing camera mode:  "  + mode_dial_config.get_value())
          mode_dial_config.set_value(new_mode)
          logging.info("New camera mode:  "  + new_mode)
          camera.set_config(cfg)

    except Exception as error:
        print("No camera found:", error)
        logging.error("No camera found", error)
        return False, ""
    finally:
        camera.exit()
        time.sleep(2)
        return True, artist_string


def wakeup_camera_gpio(): 
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_wakeup, GPIO.OUT)
    GPIO.output(pin_wakeup, GPIO.HIGH)
    time.sleep(2)
    GPIO.output(pin_wakeup, GPIO.LOW)
    GPIO.cleanup() # cleanup all GPIO
    logging.info("Waking up camera")


def shutter_camera_gpio(): 
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin_shutter, GPIO.OUT)
    GPIO.output(pin_shutter, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(pin_shutter, GPIO.LOW)
    logging.info("fire shutter")

def reset_usb(): 
    # warning this resets all usb ports on the rpi...
    logging.info(subprocess.run(['umount', '/mnt/usb'], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    logging.info(subprocess.run(['sudo', 'uhubctl','-l', '1-1' ,'-a', '2' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    time.sleep(5)  # we need time for the USB device to come back
    logging.info("reset usb complete")

def set_clock(epoch):
#    os.system("sudo echo date -s  '@{}'".format(epoch))
    logging.info(subprocess.run(['sudo', 'date','-s', '@{}'.format(epoch) ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/system_to_rtc.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
#    os.system("sudo /home/camtraption/wittypi/system_to_rtc.sh")
    logging.info("sync time to RTC using canon camera epoch: {}".format(epoch))
def get_input_voltage():
    logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_input_voltage.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def sync_logs_usb():
#    logging.info(subprocess.run(['sudo', 'mount','-o', 'rw', '/mnt/usb'  ],stderr=subprocess.PIPE, stdout=subprocess.PIPE))
#    os.system('sudo fsck -y /dev/sda1 ')
    logging.info(subprocess.run(['sudo', 'fsck','-y','/dev/sda1'  ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
#    os.system('sudo mount -o rw /dev/sda1 /mnt/usb')
    logging.info(subprocess.run(['sudo', 'mount','-o','rw','/dev/sda1','/mnt/usb'  ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    os.system('sudo rsync -qt /var/tmp/*.log /mnt/usb/logs/')
    logging.info(subprocess.run(['sudo', 'umount','/mnt/usb'  ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    logging.info("all logs synced to usb")

 
def parse_time_schedule(schedule_string):
  
#  schedule_string = "0100:C2,0230:C1,1230:C1,1250:c2,1300:c1,1500:c3"
#  t_now = datetime.strptime("0050", "%H%M"); print ("Case1")
#  t_now = datetime.strptime("0059", "%H%M"); print ("Case2")
#  t_now = datetime.strptime("0100", "%H%M"); print ("Case2 special")
#  t_now = datetime.strptime("0102", "%H%M"); print ("Case2 special")
#  t_now = datetime.strptime("1230", "%H%M"); print ("case2 special")  # test case 2
#  t_now = datetime.strptime("1245", "%H%M"); print ("case2")  # test case 2
#  t_now = datetime.strptime("1400", "%H%M"); print ("case3")
#  t_now = datetime.strptime("1300", "%H%M"); print ("case3 special")

  t_now = datetime.now()

  print("Parse time schedule: ", schedule_string)
  onduration = 2  # the amount of time the system is on.
  t_now = t_now + timedelta(seconds=(onduration +1)* 60)

  logging.info("parsing schedule string from camera: {}".format(schedule_string))
  if not schedule_string: 
      schedule_string = "0600:C1,1800:C2"
      logging.info("no string found, assuming default schedule string: {}".format(schedule_string))
  
 
  schedule_times = []
  schedule_modes = []

  for x in sorted(schedule_string.split(",")):
    hours = x[0:2]
    minutes = x[2:4]
    mode = x[5:]
    schedule_times.append(x[0:4])
    schedule_modes.append(mode)
  

  newmode = ""

  i =0
  for scht in schedule_times:
    hours = scht[0:2]
    minutes = scht[2:4]
    t = datetime.strptime(scht, "%H%M")
#    print()
#    print("Time now: " , t_now.time())
    if (i+1 >= len(schedule_times)):
      next_t = datetime.strptime(schedule_times[0], "%H%M")
    else: 
      next_t = datetime.strptime(schedule_times[i+1], "%H%M")
#    print ("Schd Time: ", t.time())
#    print ("Next Time: ", next_t.time())
    if (t_now.time() <= t.time() and i == 0):  
#        print ("Case1")
        set_wakeup(schedule_times[i])
        newmode=schedule_modes[i]

    if (t_now.time() >= t.time() and t_now.time() < next_t.time() ):  
#        print ("Case2")
        newmode=schedule_modes[i]
        set_wakeup(schedule_times[i+1])
    if (t_now.time() >= t.time() and i == len(schedule_times) - 1):  
#        print ("Case3")
        newmode=schedule_modes[i]
        set_wakeup(schedule_times[0])

    i = i + 1
    
#  print("newmode: ", newmode) 
  logging.info("newmode: " + newmode)

  mode_int = ""
  if newmode.upper() == "AUTO": mode_int = "Auto"
  if newmode.upper() == "FV": mode_int = "Fv"
  if newmode.upper() == "P": mode_int = "P"
  if newmode.upper() == "TV": mode_int = "TV"
  if newmode.upper() == "AV": mode_int = "AV"
  if newmode.upper() == "MANUAL": mode_int = "Manual"
  if newmode.upper() == "BULB": mode_int = "Bulb"
  if newmode.upper() == "C1": mode_int = "Custom"
  if newmode.upper() == "CUSTOM": mode_int = "Custom"
  if newmode.upper() == "C2": mode_int = "Unknown value 0010"
  if newmode.upper() == "C3": mode_int = "Unknown value 0011"

  print(mode_int)

  return (mode_int)
 

def set_wakeup(timestamp):
    hours = timestamp[0:2]
    minutes = timestamp[2:4]
    day = datetime.today().day
    alarm_time = datetime.strptime(timestamp, "%H%M")
    logging.info ("set wakeup: {}".format(alarm_time))

    bus = smbus.SMBus(1)
    address = 0x08
    
    bus.write_byte_data(address,27, 00)   # second
    bus.write_byte_data(address,28, int(str(alarm_time.minute),16))   # min
    bus.write_byte_data(address,29, int(str(alarm_time.hour),16))   # hour
    bus.write_byte_data(address,30, int(str(day),16))   # date
    bus.write_byte_data(address,31, 00)   # weekday

    bus.write_byte_data(address,32, 00)   # second
    bus.write_byte_data(address,33, int(str(alarm_time.minute+2),16))   # min
    bus.write_byte_data(address,34, int(str(alarm_time.hour),16))   # hour
    bus.write_byte_data(address,35, int(str(day),16))   # date
    bus.write_byte_data(address,36, 00)   # weekday

def get_temp():
  logging.info("board temp: ")
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x32' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def get_last_startup_reason():
  logging.info("startup reason: ")
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_startup_reason.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x0b' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

# normal usecase

#parse_time_schedule("0623:C1,1823:C2")

# test out of order schedule
#parse_time_schedule("1823:C2,0623:C1")

# complex example,

if __name__ == "__main__":
    main()
def get_temp():
  logging.info("board temp: ")
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x32' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def get_last_startup_reason():
  logging.info("startup reason: ")
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_startup_reason.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x0b' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

# normal usecase

#parse_time_schedule("0623:C1,1823:C2")

# test out of order schedule
#parse_time_schedule("1823:C2,0623:C1")

# complex example,
# c1 = daytime, c2 = nighttime, c3 = dusk (sunrise and sunset)
#parse_time_schedule("0523:C3,0620:c1,1823:C3,1900:c2")





if __name__ == "__main__":
    sys.exit(main())
