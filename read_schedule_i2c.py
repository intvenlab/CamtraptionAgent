import smbus
import time

import binascii
import logging

from dateutil import parser
from datetime import datetime, timedelta
import time


def main():
    bus = smbus.SMBus(1)
    address = 0x08

#    startup_reason  = bus.read_byte_data(address, 0x0b)
#    print ("startup_reason: ", startup_reason)
#    temp_c  = bus.read_byte_data(address, 0x32)
#    print ("temp in c: " , temp_c)


    alarm1_sec  = hex(bus.read_byte_data(address, 27))
    alarm1_min  = hex(bus.read_byte_data(address, 28))
    alarm1_hour  = hex(bus.read_byte_data(address, 29))
    alarm1_date  = hex(bus.read_byte_data(address, 30))
    alarm1_weekday  = hex(bus.read_byte_data(address, 31))


#binascii.hexlify(byteArray).decode()
    alarm2_sec  = hex(bus.read_byte_data(address, 32))
    alarm2_min  = hex(bus.read_byte_data(address, 33))
    alarm2_hour  = hex(bus.read_byte_data(address, 34))
    alarm2_date  = hex(bus.read_byte_data(address, 35))
    alarm2_weekday  = hex( bus.read_byte_data(address, 36))

    
    print ("startup: weekday: " , alarm1_weekday, "date: " , alarm1_date, "hour: " , alarm1_hour, "min: ",  alarm1_min, "sec: ", alarm1_sec)
    print ("shutdown: weekday: " , alarm2_weekday, "date: " , alarm2_date, "hour: " , alarm2_hour, "min: ",  alarm2_min, "sec: ", alarm2_sec)


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
