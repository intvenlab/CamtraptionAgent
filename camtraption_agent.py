

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
    if (time_last_login < datetime.now() - timedelta(seconds=wait_time)):
        # not logged in recently, time to shut down
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
#  sample output file:   https://github.com/uugear/Witty-Pi-4/blob/main/Software/wittypi/schedules/on_5m_every_20m.wpi
#  the goal here is to have robust parsing of what we find in the artists name field, which can be changed by the end user.  

  onduration = 2  # the amount of time the system is on.
  logging.info("parsing schedule string from camera: {}".format(schedule_string))
  if not schedule_string: 
      schedule_string = "0600:C1,1800:C2"
      logging.info("no string found, assuming default schedule string: {}".format(schedule_string))
  
  witty_output =  "# Warning,this file is automaticly generated based on the artists name on the camera\n"
#  witty_output = witty_output + "BEGIN\t2022-06-01 00:00:00\n"
  witty_output = witty_output + "BEGIN\t" + datetime.now().strftime("%Y-%m-%d ") + schedule_string[0:2] + ":" + schedule_string[2:4] + ":00\n"
  witty_output = witty_output + "END\t2035-07-31 23:59:59\n"
  camtraption_output = "h,m,cameramode"
  minute_subtractor = 1440 # we need to have 1440 minutes in the witty schedule or it doesn't run exactly every day.  
 
  start = parser.parse("2022-06-01 00:00:00")
  last_time = start
 
  schedule_times = []
  schedule_modes = []
  first_scheduled_item = True

 
  for x in sorted(schedule_string.split(",")):
    hours = x[0:2]
    minutes = x[2:4]
    mode = x[5:]
    schedule_times.append(x[0:4])
    schedule_modes.append(mode)
    duration = (start + timedelta(hours=int(hours), minutes= int(minutes))) - last_time
    time_change = int(divmod(duration.total_seconds(), 60)[0])
    if first_scheduled_item:
      witty_output = witty_output + "ON\tM{}\n".format(onduration)
      first_scheduled_item = False
    else: 
      witty_output = witty_output + "OFF\tM{}\n".format(time_change)
      witty_output = witty_output + "ON\tM{}\n".format(onduration)

    minute_subtractor = minute_subtractor -  time_change - onduration
#    print ("minute_subtractor: {}".format(minute_subtractor))
    last_time = last_time + timedelta( minutes= (time_change+onduration))
   
#    print ("last time: " , last_time)
  witty_output = witty_output + "OFF\tM{} #stay off for the remainder of the day total on and off time must equal 1440 minutes for accurate daily schedule!  \n".format(minute_subtractor)
 
#  print (witty_output)
  f = open("/home/camtraption/wittypi/schedule.wpi", "w")
  f.write(witty_output)
  f.close()

  logging.info(subprocess.run(['/home/camtraption/wittypi/runScript.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  logging.info("final witty schedule: {}".format(witty_output))
  
  newmode = schedule_modes[len(schedule_modes)-1]

  schedule_modes.reverse()
  for scht in schedule_times:
    mode = schedule_modes.pop()
    hours = scht[0:2]
    minutes = scht[2:4]
    t = datetime.strptime(scht, "%H%M")
    if (t.time() < datetime.now().time()):  
        print("Match!", t.time(), mode)
        newmode=mode
  
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

#  print(mode_int)

  return (mode_int)
 
def get_temp():
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x32' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def get_last_startup_reason():
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
