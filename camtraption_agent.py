
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



logname = "/var/tmp/camtraption-" + ('{:%Y%m%d-%H%M%S}.log'.format(datetime.now()))

logging.basicConfig(filename=logname,
                    filemode='a',
                    format='%(asctime)s, %(name)s %(levelname)s %(message)s',
#                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    level=logging.DEBUG)


pin_wakeup = 26
pin_shutter = 19

sysup_pin = 17
halt_pin = 4

camera_time_epoch = 0

def main():
    version = 0.4
    hwid = getserial()
    logging.info(f"Starting camtraption_agent.py version {version}, hwid: {hwid}")
    dump_all_i2c_reg()
    notify_witty_board_up()
    get_input_voltage()
    get_last_startup_reason()
    get_temp()
    wakeup_camera_gpio()
    shutter_camera_gpio()
    Result, artist_string = camera_config()
    get_rtc_time()
    reset_usb()
    shutter_camera_gpio()
    dump_all_i2c_reg()
    sync_logs_usb()
    os.system('cat {}'.format(logname))
    conditional_shutdown()

def conditional_shutdown():
    wait_time = 60   
    time.sleep(wait_time)
    time_last_login = datetime.fromtimestamp(os.stat("/home/camtraption/.last_login").st_mtime)
    if (time_last_login < datetime.now() - timedelta(seconds=wait_time+60)):
        # not logged in recently, time to shut down
        print ("shutdown...")

        GPIO.setup(halt_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        bus = smbus.SMBus(1)
        address = 0x08
    
        bus.write_byte_data(address,55, 00)   # ctrl2
        bus.write_byte_data(address,39, 00)   # alarm1
        bus.write_byte_data(address,40, 00)   # alarm2
        
        os.system("sudo shutdown -h 'now'")

def notify_witty_board_up():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    
    GPIO.setup(halt_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    time.sleep(0.1)
    GPIO.setup(sysup_pin, GPIO.OUT)
    GPIO.output(sysup_pin, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(sysup_pin, GPIO.LOW)
    time.sleep(0.1)
    GPIO.output(sysup_pin, GPIO.HIGH)
    time.sleep(0.1)
    GPIO.output(sysup_pin, GPIO.LOW)
    time.sleep(0.1)
    GPIO.setup(sysup_pin, GPIO.IN)



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
        camera_time_epoch = raw_value
        set_clock(camera_time_epoch)

        artist_cfg = cfg.get_child_by_name('artist')
        artist_string = artist_cfg.get_value()

        model_cfg = cfg.get_child_by_name('cameramodel')
        serial_cfg = cfg.get_child_by_name('eosserialnumber')
        lens_cfg = cfg.get_child_by_name('lensname')
        batterylevel_cfg = cfg.get_child_by_name('batterylevel')
        availableshots_cfg = cfg.get_child_by_name('availableshots')

        logging.info("Camera: " + model_cfg.get_value() + " Serial: " + serial_cfg.get_value() + " lens: " + lens_cfg.get_value() + " Available Shots: " + availableshots_cfg.get_value())
        logging.info("Battery Level: " + batterylevel_cfg.get_value() )

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

def check_all_times(epoch):
    if (epoch != 0):
      camera_time = datetime.fromtimestamp(epoch) # human readable
    else:
      camera_time = datetime.now()
    system_time = datetime.now()
    rtc_time = get_rtc_time()
    alarm1 = get_witty_alarm1_time()
    alarm2 = get_witty_alarm2_time()
    rtc_alarm = get_witty_rtc_alarm_time()

    logging.info("Camera Time:    " + camera_time.isoformat(timespec='seconds'))
    logging.info("System Time:    " + system_time.isoformat(timespec='seconds') + " Delta from Camera time(s): {}".format((camera_time - system_time).total_seconds()))
    logging.info("RTC Time:       " + rtc_time.isoformat(timespec='seconds') + " Delta from Camera time(s): {}".format((camera_time - rtc_time).total_seconds()))
    logging.info("Alarm1 Time:    " + alarm1.isoformat(timespec='seconds'))
    logging.info("Alarm2 Time:    " + alarm2.isoformat(timespec='seconds'))
    logging.info("RTC alarm:      " + rtc_alarm.isoformat(timespec='seconds'))
	
def set_clock(epoch):
    check_all_times(epoch)

    logging.info("sync time to RTC using canon camera epoch: {}".format(epoch))
    logging.info(subprocess.run(['sudo', 'date','-s', '@{}'.format(epoch) ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
    logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/system_to_rtc.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def get_input_voltage():
    bus = smbus.SMBus(1)
    address = 0x08
    i = decode_bcd(bus.read_byte_data(address, 1))
    d = decode_bcd(bus.read_byte_data(address, 2))

    input_voltage = i + d / 100
    logging.info("Input Voltage: " + str(input_voltage))
    return (input_voltage)

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
  
  t_now = datetime.now()
### debug code

#  schedule_string = "0100:C2,0230:C1,1230:C1,1250:c2,1300:c1,1500:c3"
#  t_now = datetime.strptime("0050", "%H%M"); print ("Case1")
#  t_now = datetime.strptime("0059", "%H%M"); print ("Case2")
#  t_now = datetime.strptime("0100", "%H%M"); print ("Case2 special")
#  t_now = datetime.strptime("0102", "%H%M"); print ("Case2 special")
#  t_now = datetime.strptime("1230", "%H%M"); print ("case2 special")  # test case 2
#  t_now = datetime.strptime("1245", "%H%M"); print ("case2")  # test case 2
#  t_now = datetime.strptime("1400", "%H%M"); print ("case3")
#  t_now = datetime.strptime("1300", "%H%M"); print ("case3 special")
#  t_now = datetime.strptime("1600", "%H%M"); print ("case3 special")


#  print("Parse time schedule: ", schedule_string)
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
        set_wakeup(schedule_times[i], 0)
        newmode=schedule_modes[i]

    if (t_now.time() >= t.time() and t_now.time() < next_t.time() ):  
#        print ("Case2")
        newmode=schedule_modes[i]
        set_wakeup(schedule_times[i+1], 0)
    if (t_now.time() >= t.time() and i == len(schedule_times) - 1):  
#        print ("Case3")
        newmode=schedule_modes[i]
        set_wakeup(schedule_times[0], 1)

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

  #print(mode_int)

  return (mode_int)
 

def set_wakeup(timestamp, dayoffset):
    hours = timestamp[0:2]
    minutes = timestamp[2:4]

    current_date = datetime.today() + timedelta(days=dayoffset)
    day = current_date.day 

    alarm_time = datetime.strptime(timestamp, "%H%M")
    logging.info ("set wakeup: {}".format(alarm_time.time()))
#    logging.info ("day offset: {}".format(dayoffset))
    logging.info (f"day offset: {dayoffset}, set day: {day}")

    bus = smbus.SMBus(1)
    address = 0x08
    
    bus.write_byte_data(address,27, 00)   # second
    bus.write_byte_data(address,28, int(str(alarm_time.minute),16))   # min
    bus.write_byte_data(address,29, int(str(alarm_time.hour),16))   # hour
    bus.write_byte_data(address,30, int(str(day),16))   # date
    bus.write_byte_data(address,31, 00)   # weekday
    
    bus.write_byte_data(address,65, 00)   # second
    bus.write_byte_data(address,66, int(str(alarm_time.minute),16))   # min
    bus.write_byte_data(address,67, int(str(alarm_time.hour),16))   # hour
    bus.write_byte_data(address,68, int(str(day),16))   # date
    bus.write_byte_data(address,69, 00)   # weekday
  
    alarm_time = alarm_time + timedelta(seconds=120)
    logging.info ("set shutdown: {}".format(alarm_time.time()))

    bus.write_byte_data(address,32, 00)   # second
    bus.write_byte_data(address,33, int(str(alarm_time.minute),16))   # min
    bus.write_byte_data(address,34, int(str(alarm_time.hour),16))   # hour
    bus.write_byte_data(address,35, int(str(day),16))   # date  HACK Set the shutdown to 2 days prior -- this shutdown alarm was causing the system to wake up
    bus.write_byte_data(address,36, 00)   # weekday
    
    check_all_times(camera_time_epoch)
	

def dump_all_i2c_reg():
  logging.info("Dump all i2c:")
  bus = smbus.SMBus(1)
  address = 0x08
  logging_msg = ""
  for i in range(0,72):
      logging_msg += (f"Reg: {i}," + str(decode_bcd(bus.read_byte_data(address, i))) + " ")
  logging.info(logging_msg)

def get_last_startup_reason():
  logging.info("startup reason: ")
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_startup_reason.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x0b' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def get_rtc_time():
  bus = smbus.SMBus(1)
  address = 0x08
  try:
    rtc_time = datetime.strptime(str(decode_bcd(bus.read_byte_data(address, 64))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 63))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 62))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 61))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 60))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 59))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 58))),

      "%y %m %w %d %H %M %S")
  except (ValueError, TypeError):
    return datetime.min
#  logging.info("RTC time " + rtc_time.isoformat())
  return rtc_time

def get_witty_alarm1_time():
  bus = smbus.SMBus(1)
  address = 0x08
  try:
    alarm1_time = datetime.strptime(str(decode_bcd(bus.read_byte_data(address, 31))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 30))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 29))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 28))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 27))),

      "%w %d %H %M %S")
  except (ValueError, TypeError):
    return datetime.min
#  logging.info("RTC time " + rtc_time.isoformat())
  return alarm1_time

def get_witty_alarm2_time():
  bus = smbus.SMBus(1)
  address = 0x08
  try:
    alarm2_time = datetime.strptime(str(decode_bcd(bus.read_byte_data(address, 36))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 35))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 34))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 33))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 32))),

      "%w %d %H %M %S")
  except (ValueError, TypeError):
    return datetime.min
#  logging.info("RTC time " + rtc_time.isoformat())
  return alarm2_time

def get_witty_rtc_alarm_time():
  bus = smbus.SMBus(1)
  address = 0x08
  try:
    rtc_alarm = datetime.strptime(str(decode_bcd(bus.read_byte_data(address, 69))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 68))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 67))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 66))) + 
        " " + str(decode_bcd(bus.read_byte_data(address, 65))),

      "%w %d %H %M %S")
  except (ValueError, TypeError):
    return datetime.min
#  logging.info("RTC time " + rtc_time.isoformat())
  return rtc_alarm
  
def get_alarm_schedule():
  logging.info("Alarm Schedule: ")
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_startup_time.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  bus = smbus.SMBus(1)
  address = 0x08
  logging.info("Alarm1: Weekday: " +  hex(bus.read_byte_data(address, 31)) + 
        " Date: " + hex(bus.read_byte_data(address, 30)) + 
        " Hour: " + hex(bus.read_byte_data(address, 29)) + 
        " Min: " + hex(bus.read_byte_data(address, 28)) + 
        " Sec: " + hex(bus.read_byte_data(address, 27)))

  logging.info("Alarm2: Weekday: " +  hex(bus.read_byte_data(address, 36)) + 
        " Date: " + hex(bus.read_byte_data(address, 35)) +
        " Hour: " + hex(bus.read_byte_data(address, 34)) +
        " Min: " + hex(bus.read_byte_data(address, 33)) +
        " Sec: " + hex(bus.read_byte_data(address, 32)))

def get_last_startup_reason():
  logging.info("startup reason: ")
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_startup_reason.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))


def get_temp():
  logging.info("board temp: ")
#  logging.info(subprocess.run(['i2cget', '-y', '0x01', '0x08', '0x32' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))
  logging.info(subprocess.run(['sudo', '/home/camtraption/wittypi/get_temp.sh' ], stderr=subprocess.PIPE, stdout=subprocess.PIPE))

def decode_bcd(bcd):
  return (bcd // 16 * 10) + (bcd % 16)

def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"

  return cpuserial

if __name__ == "__main__":
    sys.exit(main())
