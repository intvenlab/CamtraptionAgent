#!/bin/bash

cur_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# utilities
. "$cur_dir/utilities.sh"

# GPIO utilites
. "$cur_dir/gpio-util.sh"

  reason=$(i2c_read 0x01 $I2C_MC_ADDRESS $I2C_ACTION_REASON)
  if [ "$reason" == $REASON_ALARM1 ]; then
    log 'System starts up because scheduled startup is due.'
  elif [ "$reason" == $REASON_CLICK ]; then
    log 'System starts up because the button is clicked.'
  elif [ "$reason" == $REASON_VOLTAGE_RESTORE ]; then
    log 'System starts up because the input voltage reaches the restore voltage.'
  elif [ "$reason" == $REASON_OVER_TEMPERATURE ]; then
    log 'System starts up because temperature is higher than preset value.'
    log "$(get_temperature)"
  elif [ "$reason" == $REASON_BELOW_TEMPERATURE ]; then
    log 'System starts up because temperature is lower than preset value.'
    log "$(get_temperature)"
  elif [ "$reason" == $REASON_ALARM1_DELAYED ]; then
    log 'System starts up because of the scheduled startup got delayed.'
    log 'Maybe the scheduled startup was due when Pi was running, or Pi had been shut down but TXD stayed HIGH to prevent the power cut.'
  elif [ "$reason" == $REASON_USB_5V_CONNECTED ]; then
    log 'System starts up because USB 5V is connected.'
  else
    log "Unknown/incorrect startup reason: $reason"
  fi


