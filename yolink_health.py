#!/usr/bin/python3
Filename= "yolink_health.py"
Version = "1.65"

# Version 1.25: Converted CURL to in-line commands
# Version 1.28: Add logging
# Version 1.43: Add support for relay
# Version 1.44: Reload data dictionary if new device appears
# Version 1.45: Fix issues with new device detection and relay battery status
# Version 1.46: Fix on_message bug, fix rc references which should be YL_rc
# Version 1.47: Add display of device and state when event occurs, add Manipulator.StatusChange
# Version 1.48: Add colors to table display
# Version 1.49: Add support for plug devices
# Version 1.50: Create empty Health_Table.txt file if one does not already exist
# Version 1.51: Move authentication information into external file
# Version 1.52: Add excluded_events list
# Version 1.54: Fix int conversion bug when signal strength is ??
# Version 1.55: Add THSensor.data.Report to exclusion list, fix min signal strength when previous was ??
# Version 1.56: Add polling for hubs
# Version 1.57: Update contact time when excluded event records are received
# Version 1.58: Add max time since last update
# Version 1.59: Fix display bug
# Version 1.60: Add 'file_dirty' flag to control writing table to disk
# Version 1.61: Pad the displayed update values to maintain alignment for up to 999 hours
# Version 1.62: Clean up startup displays
# Version 1.63: Add 'mid_battery' level to cause display to show in yellow, no alert
# Version 1.64: Add test for existence of configuration file at program startup
# Version 1.65: Add display of invalid entry in configuration file

import json
import time
import datetime
import smtplib
from pprint import pprint
import paho.mqtt.client as mqtt
import requests
from requests.structures import CaseInsensitiveDict
import os
import os.path

# Name of file containing configuration information
config_file='yolink_health.cfg'

# Name of activity log file
log_file="yolink_health.log"

# Name of file used to store current device list with health statistics
health_table = "yolink_health_table.txt"

# Yolink MQTT Broker variables:
YL_mqttBroker = 'api.yosmart.com'
YL_port = 8003

# Access Token time variables
# The access_token_timestamp value is set to a default value in the past here.  It will be 
# updated with the current value each time a new access token is obtained.
# The YL_token_valid_minutes is the number of minutes that a newly issued access token is valid.
# It is set to 120 minutes here but will be updated each time an access token is obtained.
access_token_timestamp=datetime.datetime.now()-datetime.timedelta(days=7)
YL_token_valid_minutes = 120 

# Flags to determine whether information from MQTT broker is current
YL_token_valid = False
dictionary_loaded = False
YL_home_ID_valid = False

# Display variables
line_len = 80
backspaces = '\b'*line_len

# Length of key to be used in device dictionary
key_size=30

""" ANSI color codes """
BLACK = "\x1b[0;30m"
RED = "\x1b[0;31m"
RED2 = "\x1b[31;0m"
GREEN = "\x1b[0;32m"
BROWN = "\x1b[0;33m"
BLUE = "\x1b[0;34m"
PURPLE = "\x1b[0;35m"
CYAN = "\x1b[0;36m"
LIGHT_GRAY = "\x1b[0;37m"
DARK_GRAY = "\x1b[1;30m"
LIGHT_RED = "\x1b[1;31m"
LIGHT_GREEN = "\x1b[1;32m"
YELLOW = "\x1b[1;33m"
LIGHT_BLUE = "\x1b[1;34m"
LIGHT_PURPLE = "\x1b[1;35m"
LIGHT_CYAN = "\x1b[1;36m"
LIGHT_WHITE = "\x1b[1;37m"
BOLD = "\x1b[1m"
FAINT = "\x1b[2m"
ITALIC = "\x1b[3m"
UNDERLINE = "\x1b[4m"
BLINK = "\x1b[5m"
NEGATIVE = "\x1b[7m"
CROSSED = "\x1b[9m"
END = "\x1b[0m"

# Function to display text with color
def pcolor(attribute,text):
   if color_enabled:
      print(attribute+text+END)
   else:
      print(text)
   return()

# Function to build text string with embedded ANSI color codes
def encode(attribute,text):
   if color_enabled:
      encoded_text = attribute+text+END
   else:
      encoded_text = text
   return(encoded_text)
 
# Function to conditionally log activity.  Skipped with "logging" flag is set to False
def post(text):
   if logging:
      log_fid = open(log_file,'a')
      log_fid.write("%s %s\n" % (timestamp(),text))
      log_fid.close()
   return

# Build Yolink unix style date/time string from current date/time
def unix_timestamp():
   now = int(time.time()*1000)
   return str(now)

# Convert Yolink version of Unix time to Python datetime format
def unpack_unix_time(time):
   dt=datetime.datetime.fromtimestamp(int(time/1000))
   return(dt.strftime('%Y-%m-%d %I:%M:%S %p'))

# Build formatted date/time string from current date/time.
def timestamp():
   now=datetime.datetime.now()
   return(now.strftime('%Y-%m-%d %I:%M:%S %p'))

# Function to print backspaces, then text right padded with spaces to standard length WITHOUT new line
def print_bs(text):
   print(backspaces+ text+ ' '*(line_len-len(text)), end='', flush=True)
   return

# Function to print backspaces, then text right padded with spaces to standard length WITH new line
def print_nl(text):
   print(backspaces+ text+ ' '*(line_len-len(text)))
   return()

# Function to get program configuration information from external file
def read_config_variables():
    global UAID
    global SECRET_KEY
    global color_enabled
    global logging
    global log_raw
    global verbose
    global mid_battery, min_battery, min_signal, max_age_minutes, max_alerts
    global send_status_emails, email_addr_list, email_server, email_account_name, email_account_pw
    global valid_config_file

    # Flag for valid config file contents.  Gets turned off if any entry from this
    # point forward is invalid in which case the rest of the lookups are abandoned
    valid_config_file = True

    if valid_config_file: UAID=get_config_string('UAID')
    if valid_config_file: SECRET_KEY=get_config_string('SECRET_KEY')
    if valid_config_file: color_enabled=get_config_truefalse('color_enabled')
    if valid_config_file: logging=get_config_truefalse('logging')
    if valid_config_file: log_raw=get_config_truefalse('log_raw')
    if valid_config_file: verbose=get_config_truefalse('verbose')
    if valid_config_file: mid_battery=get_config_integer('mid_battery')
    if valid_config_file: min_battery=get_config_integer('min_battery')
    if valid_config_file: min_signal=get_config_integer('min_signal')
    if valid_config_file: max_age_minutes=get_config_integer('max_age_minutes')
    if valid_config_file: max_alerts=get_config_integer('max_alerts')
    if valid_config_file: send_status_emails=get_config_truefalse('send_status_emails')
    if valid_config_file: email_addr_list=get_config_list('email_addr_list')
    if valid_config_file: email_server=get_config_string('email_server')
    if valid_config_file: email_account_name=get_config_string('email_account_name')
    if valid_config_file: email_account_pw=get_config_string('email_account_pw')

    return valid_config_file


# Function to search configuration file for a specific variable entry
def get_config_string(vname):
    global valid_config_file

    found = False
    vname_value = ''
 
    try:
        file = open(config_file,'r')

        for line in file:
            ptr=line.find('=')
            if ptr >= 0:
                tag = line[:ptr]
                tag=tag.rstrip(' ')
                if tag == vname:
                    vname_value = line[ptr+1:]
                    vname_value = vname_value.rstrip('\n')
                    vname_value = vname_value.lstrip(' ').rstrip(' ')
                    found = True

        file.close()
    except:
       valid_config_file = False

    if found == False:
       print('Unable to locate entry for key "%s" in "%s" configuration file.\n' % (vname,config_file))

    return vname_value

# Function to search configuration/state file for a specific variable which must have True or False value
def get_config_truefalse(vname):
    global valid_config_file
    
    vname_value = get_config_string(vname)
    result=''
    if valid_config_file:
        if vname_value=='True':
            result = True
        elif vname_value=='False':
            result = False
        else:
            valid_config_file = False
            print('Invalid True/False setting for key "%s" in "%s" configuration file.\n' % (vname,config_file))

    return result

# Function to search configuration file for a specific variable which must convert to an integer
def get_config_integer(vname):
    global valid_config_file
    
    vname_value = get_config_string(vname)
    result=''
    if valid_config_file:
       try:
          result = int(vname_value)
       except:
          result = ''
          valid_config_file = False
          print('Invalid integer value for key "%s" in "%s" configuration file.\n' % (vname,config_file))

    return result

# Function to search configuration file for a specific variable which must convert to a list
def get_config_list(vname):
    global valid_config_file
    
    vname_value = get_config_string(vname)
    result=''
    if valid_config_file:
       try:
          result = vname_value.split(',')
       except:
          result = []
          valid_config_file = False
          print('Invalid list entry for key "%s" in "%s" configuration file.\n' % (vname,config_file))

    return result


#=============================================================================================
# Get YoLink Access Token
#=============================================================================================
def YL_get_access_token():
   global YL_access_token_timestamp
   global YL_access_token, YL_token_valid, YL_token_valid_minutes

   if first_time: post("Getting Access Token")

   url = "http://api.yosmart.com/open/yolink/token"

   headers = CaseInsensitiveDict()
   headers["Content-Type"] = "application/x-www-form-urlencoded"

   data = "grant_type=client_credentials&client_id="+UAID+"&client_secret="+SECRET_KEY

   resp = requests.post(url, headers=headers, data=data)
   
   if resp.status_code == 200:

      # Response of 200 means valid POST
      # Proceed to request the record
      try:
         result = resp.json()

         YL_access_token = result['access_token']
         YL_token_type = result['token_type']
         YL_expires_in = result['expires_in']
         YL_refresh_token = result['refresh_token']
         YL_scope = result['scope']

         YL_access_token_timestamp = datetime.datetime.now()
         YL_token_valid_minutes = int(YL_expires_in/60)
         YL_token_valid = True

         if verbose:
            print("\nAccess Token Fields:")
            print("token: %s" % YL_access_token)
            print("type: %s" % YL_token_type)
            print("expires_in: %s - %s" % (YL_expires_in,YL_token_valid_minutes))
            print("refresh_token: %s" % YL_refresh_token)
            print("scope: %s" % YL_scope)
      except:
         YL_token_valid = False

   else:
      YL_token_valid = False

   if YL_token_valid == False:
      pcolor(LIGHT_RED+NEGATIVE,'\nUnable to obtain Access Token.  Check the credentials in the configuration file "%s".' % config_file)
      print("\nProgram stopped.\n")
      os._exit(5)
   return()

#=============================================================================================
# Establish connection to YoLink MQTT Broker
#=============================================================================================

# Establish MQTT connection
def YL_establish_MQTT_connection():
   global YL_mqttBroker, YL_port, YL_topic, YL_client
   global YL_access_token_timestamp

   if first_time: post("Establishing connection to MQTT Broker")

   if verbose: print_nl("%s Establishing connection to MQTT Broker" % timestamp())

   # Reset token timestamp and then get access token - this assures a current token
   YL_access_token_timestamp=datetime.datetime.now()-datetime.timedelta(days=7)
   YL_get_access_token()

   if YL_home_ID_valid == False:
      YL_get_home_ID()

   #Normal topic that gets all responses with 'report' in the topic name
   YL_topic = 'yl-home/' + YL_home_ID + '/+/report'

   # Establish the MQTT connection
   YL_client = mqtt.Client()
   YL_client.username_pw_set(username=YL_access_token)
   YL_client.on_connect = YL_on_connect
   YL_client.on_disconnect = YL_on_disconnect
   YL_client.onconnection_lost = YL_on_connectionlost
   YL_client.on_message = YL_on_message
   YL_client.connect(host=YL_mqttBroker, port=YL_port, keepalive=60)
   YL_client.reconnect_delay_set(min_delay=1, max_delay=120)
   if first_time: post("Established MQTT connection")
   return()

#=============================================================================================
# Function to be executed when a connection to the YoLink MQTT Broker is established
#=============================================================================================

def YL_on_connect(YL_client, YL_username, YL_flags, YL_rc):

   if first_time: post("On Connect - Return Code %s" % YL_rc)
   
   if YL_rc == 0:
      if verbose: print_nl("%s Connected to YoLink MQTT Broker" % timestamp())
      ###print_nl("%s" % timestamp())


   elif YL_rc == 5:
      print_nl("\n%s Authorization error connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   elif YL_rc == 1:
      print_nl("\n%s 'Incorrect Protocol' reported while connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   elif YL_rc == 2:
      print_nl("\n%s 'Invalid Client Identifier' reported while connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   elif YL_rc == 3:
      print_nl("\n%s 'Server Unavailable' reported while connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   elif YL_rc== 4:
      print_nl("\n%s 'Invalid User Name or Password' reported while connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   else:
      print_nl("\n%s 'Unknown Error' reported while connecting to YoLink MQTT Broker, result code %s" % (timestamp(),str(YL_rc)))

   if YL_rc != 0:
      print_nl("Sleeping for 60 seconds")
      time.sleep(60)

   # Subscribing in on_connect() means that if we lose the connection and
   # reconnect then subscriptions will be renewed.
   if first_time: post("Subscribing to %s" % YL_topic)
   if verbose: print_nl("*** Topic Subscribed: %s" % YL_topic)
   YL_client.subscribe(YL_topic)
   return()

#=============================================================================================
# Function to be executed when a connection to the YoLink MQTT Broker is disconnected
#=============================================================================================
def YL_on_disconnect():
   if first_time: post("MQTT Disconnected")
   print_nl("\n%s >>> MQTT Disconnected <<<" % timestamp())
   return()

#=============================================================================================
# Function to be executed when a connection to the YoLink MQTT Broker is lost
#=============================================================================================
def YL_on_connectionlost():
   if first_time: post("MQTT Connection Lost")
   print_nl("\n%s >>> MQTT Connection Lost <<<" % timestamp())
   return()

# Read current "yolink_health_table.txt" file and used it to build device status dictionary
def load_table():
   global dev_status_dictionary
   dev_status_dictionary={}
   if os.path.isfile(health_table) == False:
      fid=open(health_table,'w')
      fid.close()
   fid=open(health_table,'r')
   file=fid.readlines()
   for record in file:
      if len(record.rstrip()) > 0:
         entry=record[2:key_size+2]
         entry=entry.rstrip()
         key=entry[:-1]
         ptr=record.find('Battery:')
         battery_status=record[ptr+9:ptr+9+1]
         ptr=record.find('Current Signal:')
         current_signal_status=record[ptr+15:ptr+15+4].lstrip()
         ptr=record.find('Min Signal:')
         minimum_signal_status=record[ptr+11:ptr+11+4].lstrip()
         ptr=record.find('Last Update')
         update_time=record[ptr+13:ptr+34+1].lstrip()
         ptr=record.find('Longest Update:')
         longest_update=record[ptr+16:len(record)-6]

         if verbose: print("|%s| Battery:|%s|    Signal:|%s|    Min Signal:|%s|    Last Update: |%s|  Longest: |%s|" % (key,battery_status,current_signal_status,minimum_signal_status,update_time,longest_update))

         if battery_status == '-':
            battery_display = battery_status
         else:
            battery_display = int(battery_status)

         if current_signal_status=='??':
            current_signal_display = current_signal_status
         else:
            current_signal_display=int(current_signal_status)

         if minimum_signal_status=='??':
            minimum_signal_display = minimum_signal_status
         else:
            minimum_signal_display=int(minimum_signal_status)


         dev_status_dictionary[key]=[battery_display,current_signal_display,minimum_signal_display,update_time,longest_update]
   fid.close()
   return()


#=============================================================================================
# Get Device Status
#=============================================================================================

def get_device_status(device_data):

   # Default to off line - will be changed to on line if status check is successful and device reports it is on line
   device_online = False

   device_id = device_data['deviceId']
   device_name = device_data['name']
   device_token = device_data['token']
   device_type = device_data['type']


   #
   # Get status of device
   #

   url = "https://api.yosmart.com/open/yolink/v2/api"

   headers = CaseInsensitiveDict()
   headers["Content-Type"] = "application/json"
   headers["Authorization"] = "Bearer "+ YL_access_token

   data = '{"method":"' + device_type + '.getState","targetDevice":"' + device_id + '","token":"' + device_token + '"}'
   resp = requests.post(url, headers=headers, data=data)
   device_data = resp.json()

   if device_type == 'Hub':
      try:
         device_status = device_data['desc']
      except:
         device_status = 'Unknown (H1)'

      try:
         wifi = device_data['data']['wifi']['enable']
         if wifi:
            wifi_enabled = 'Yes'
         else:
            wifi_enabled = 'No'
      except:
         wifi_enabled = 'Unknown (H2)'

      try:
         ssid = device_data['data']['wifi']['ssid']
      except:
         ssid = 'Unknown (H3)'

      try:
         ethernet = device_data['data']['eth']['enable']
         if ethernet:
            ethernet_enabled = 'Yes'
         else:
            ethernet_enabled = 'No'

      except:
         ethernet_enabled = 'Unknown (H4)'

      if verbose: print("%s %s %s %s %s %s" % (device_name.ljust(30), device_type.ljust(25), device_status.ljust(10), wifi_enabled.ljust(10), ssid.ljust(20), ethernet_enabled))

   elif device_type == 'Manipulator':

      try:
         device_status = device_data['desc']
      except:
         device_status = 'Unknown (M1)'

      
      # Unsupported value
      device_online = ''

      try:
         device_state = device_data['data']['state']
      except:
         device_state = 'Unknown (M2)'

      try:
         device_battery = device_data['data']['battery']
      except:
         device_battery = 'Unknown (M3)'

      if verbose: print("%s %s %s %s %s %s" % (device_name.ljust(30), device_type.ljust(25), device_status.ljust(10), device_state.ljust(15), device_online.ljust(15), device_battery))


   elif device_type == 'Switch':

      try:
         device_status = device_data['desc']
      except:
         device_status = 'Unknown (S1)'

      
      # Unsupported value
      device_online = ''

      try:
         device_state = device_data['data']['state']
      except:
         device_state = 'Unknown (S2)'

 
      # Unsupported value
      device_battery = ''

      if verbose: print("%s %s %s %s %s %s" % (device_name.ljust(30), device_type.ljust(25), device_status.ljust(10), device_state.ljust(15), device_online.ljust(15), device_battery))

   elif device_type == 'Outlet':

      try:
         device_status = device_data['desc']
      except:
         device_status = 'Unknown (O1)'


      # Unsupported value
      device_online = ''

      try:
         device_state = device_data['data']['state']
      except:
         device_state = 'Unknown (O2)'

      # Unsupported value
      device_battery = ''

      if verbose: print("%s %s %s %s %s %s" % (device_name.ljust(30), device_type.ljust(25), device_status.ljust(10), device_state.ljust(15), device_online.ljust(15), device_battery))

   else:

      try:
         device_status = device_data['desc']
      except:
         device_status = 'Unknown (1)'

      try:
         dev_online = device_data['data']['online']
         if dev_online:
            device_online='True'
         else:
            device_online='False'
      except:
         device_online = 'Unknown (2)'

      try:
         device_state = device_data['data']['state']['state']
      except:
         device_state = 'Unknown (3)'

      try:
         device_battery = device_data['data']['state']['battery']
      except:
         device_battery = 'Unknown (4)'

      if verbose: print("%s %s %s %s %s %s" % (device_name.ljust(30), device_type.ljust(25), device_status.ljust(10), device_state.ljust(15), device_online.ljust(15), device_battery))


   if device_status == 'Success':
      device_online = True
   else:
      device_online = False

   return(device_online)



def write_table():
   global dev_status_dictionary
   global file_dirty

   fid = open(health_table,"w")

   for d in sorted(dev_status_dictionary):
      key=d+":"
      status=dev_status_dictionary[d]
      if status[0] == '-':
         battery_status = ' -'
      else:
         battery_status=str(status[0]).rjust(2,' ')
      current_signal_status=str(status[1]).rjust(4,' ')
      minimum_signal_status=str(status[2]).rjust(4,' ')
      update_time=status[3]
      longest_update=status[4]
      fid.write("  %s Battery:%s   Current Signal:%s   Min Signal:%s   Last Update: %s   Longest Update: %s Mins\n" % (key.ljust(key_size," "),battery_status,current_signal_status,minimum_signal_status,update_time,str(round(int(longest_update),1))))
      if verbose: print_nl("  %s Battery:%s   Signal:%s   Min Signal:%s   Last Update: %s   Longest Update: %s" % (key.ljust(key_size," "),battery_status,current_signal_status,minimum_signal_status,update_time,longest_update))
   
   fid.close()
   file_dirty = False
   return()

def display_table():
   divider = "="*123
   ###print("\033c\n\n\n"+divider)
   
   print(divider)

   for d in sorted(dev_status_dictionary):
      key=d+":"
      status=dev_status_dictionary[d]
      if status[0] == '-':
         battery_status = ' -'
      else:
        battery_status=str(status[0]).rjust(2,' ')
      current_signal_status=str(status[1]).rjust(4,' ')
      minimum_signal_status=str(status[2]).rjust(4,' ')
      update_time=status[3]

      dt_update_time=datetime.datetime.strptime(update_time,'%Y-%m-%d %I:%M:%S %p')
      et_minutes = round(int((datetime.datetime.now()-dt_update_time).total_seconds()/60),1)

      longest_et=int(status[4])

      if et_minutes > longest_et:
         # Update longest update time current length is greater than longest
         longest_update=str(et_minutes)
         dev_status_dictionary[d]=[status[0],status[1],status[2],status[3],longest_update]
         file_dirty = True
      else:
         longest_update = status[4]

      # Test for alarm conditions and, where appropriate, display fields as red on white
      alarm_condition = False

      
      if battery_status != ' -' and int(battery_status) <= mid_battery and int(battery_status) > min_battery:
         display_text = encode(YELLOW+NEGATIVE,"Battery:" + battery_status) + "   "
      elif battery_status != ' -' and int(battery_status) <= min_battery:
         display_text = encode(LIGHT_RED+NEGATIVE,"Battery:" + battery_status) + "   "
         alarm_condition = True
      else:
         display_text = "Battery:" + battery_status + "   "

      if current_signal_status.lstrip() != '??' and int(current_signal_status) < min_signal:
         display_text += encode(LIGHT_RED+NEGATIVE,"Signal:"+current_signal_status) + "   "
         alarm_condition = True
      else:
         display_text += "Signal:"+current_signal_status+"   "

      display_text += "Min Signal:" + minimum_signal_status + "   "

      et_text = str(round(et_minutes/60,1)).rjust(5,' ')

      if et_minutes > max_age_minutes:
         display_text += encode(LIGHT_RED+NEGATIVE,"Last Update: " + et_text + " Hrs")
         alarm_condition = True
      else:
         display_text += "Last Update: " + et_text + " Hrs"

      lt_text = str(round(int(longest_update)/60,1)).rjust(5,' ')

      display_text += "   Longest: " + lt_text + " Hrs"

      if alarm_condition:
         header = "  "+encode(LIGHT_RED+NEGATIVE,key.ljust(key_size," "))+" "
      else:
         header = "  "+key.ljust(key_size," ")+" "

      print(header+display_text)

   print_nl(divider)
   print()
   return()

def check_status():
   if verbose: print_nl("Checking status of all devices")
   alerts_count=0
   for d in sorted(dev_status_dictionary):
      key=d+":"
      status=dev_status_dictionary[d]
      if status[0] == '-':
         battery_status = ' -'
      else:
         battery_status=str(status[0]).rjust(2,' ')
      current_signal_status=str(status[1]).rjust(4,' ')
      minimum_signal_status=str(status[2]).rjust(4,' ')
      update_time=status[3]
      longest_update=status[4]

      if battery_status.lstrip() != '-' and int(battery_status) <= min_battery and alerts_count < max_alerts:
         send_status_email("Yolink Device Alert " + str(alerts_count+1), "%s Battery Level %s on Device %s" % (timestamp(),battery_status,d))
         alerts_count +=1
         time.sleep(1)

      if current_signal_status.lstrip() != '??' and int(current_signal_status) < min_signal and alerts_count < max_alerts:
         send_status_email("Yolink Device Alert " + str(alerts_count+1), "%s Signal Level %s on Device %s" % (timestamp(),current_signal_status,d))
         alerts_count +=1
         time.sleep(1)

      dt_update_time=datetime.datetime.strptime(update_time,'%Y-%m-%d %I:%M:%S %p')
      et_minutes = int((datetime.datetime.now()-dt_update_time).total_seconds()/60)
      if et_minutes > max_age_minutes  and alerts_count < max_alerts:
         send_status_email("Yolink Device Alert " + str(alerts_count+1), "%s Device %s Not Updated for %s hours" % (timestamp(), d, round(et_minutes/60,1)))
         alerts_count +=1
         time.sleep(1)

      if verbose: print_nl("Device %s Update Time: %s  Elapsed Minutes: %s" % (d,update_time,et_minutes))

   if alerts_count == 0:
      send_status_email("Yolink Devices AOK",timestamp()+" All Yolink devices are operating within normal parameters")

   if alerts_count >= max_alerts:
      send_status_email("Excessive Yolink Alerts", "Excessive Yolink alerts.  See application for display of all alerts")

   return()

#=============================================================================================
# FUnction to be used as callback when message is received from MQTT Broker
#=============================================================================================

def YL_on_message(YL_client, YL_userdata, YL_msg):
   global dev_status_dictionary
   global dictionary_reload_required
   global file_dirty

   YL_payload = json.loads(YL_msg.payload)
   YL_device_id=YL_payload['deviceId']

   if log_raw:
      fid = open("MQTT_raw.txt","a")
      fid.write("%s\n" % timestamp())
      for key, value in YL_payload.items():
         fid.write("%s:%s\n" % (key,value))
      fid.write("\n")
      fid.close()

   try:
      YL_device_name=id_dictionary[YL_device_id]
      dictionary_reload_required = False
   except:
      dictionary_reload_required = True
      print("\n\n*** New Device Reported.  Device List Reload Required")

   if dictionary_reload_required == False:

      YL_event=YL_payload['event']

      if YL_event not in excluded_events:
         try:
            YL_state = YL_payload['data']['state']
         except:
            YL_state = "???"

         print("\033c\n%s *** Event: %s for %s, state: %s\n" % (timestamp(),YL_event, YL_device_name, YL_state))

         if YL_event in recognized_events:
            valid_event = True

            try:
               YL_battery = str(YL_payload['data']['battery'])
            except:
               YL_battery = '-'
            try:
               YL_signal = str(YL_payload['data']['loraInfo']['signal'])
            except:
               YL_signal = '??'

         else:
            #YL_event not in recognized events
            valid_event=False

         if valid_event:

            if verbose:
               print_nl("%s: %s  Event: %s" % (timestamp(),YL_device_name, YL_event))
               print_nl("     Battery %s" % YL_battery)
               print_nl("     Signal  %s" % YL_signal)
               ###print_nl("     as of   %s" % (YL_event_time))
               print_nl('-' * 40)

            # Update status dictionary
            if YL_device_name in dev_status_dictionary:
               record=dev_status_dictionary[YL_device_name]
               prev_minimum=record[2]
               update_time=record[3]
               longest_update=record[4]

               dt_update_time=datetime.datetime.strptime(update_time,'%Y-%m-%d %I:%M:%S %p')
               et_minutes = int((datetime.datetime.now()-dt_update_time).total_seconds()/60)
               if et_minutes > int(longest_update):
                  longest_update = str(et_minutes)

               if YL_signal != '??':
                  if prev_minimum != '??':
                     minimum_signal=str(min(int(YL_signal),int(prev_minimum)))
                  else:
                     minimum_signal=YL_signal
               else:
                  minimum_signal = '??'

               if verbose: print("Previous: %s  Current: %s  New: %s" % (prev_minimum,YL_signal,minimum_signal))


            else:
              # Device name not in dictionary
               minimum_signal=YL_signal
               if verbose: print("NEW: Current: %s  New: %s" % (YL_signal,minimum_signal))
               longest_update='0'

            dev_status_dictionary[YL_device_name]=[YL_battery,YL_signal,minimum_signal,timestamp(),longest_update]
            file_dirty = True

            display_table()
         
         else:
            # Not valid event
            print_nl("%s: Unsupported event: %s on %s" % (timestamp(),YL_event, YL_device_name))
            fid = open("yolink_health_failed_log.txt","a")
            fid.write(timestamp()+': '+YL_device_name+'  ')
            fid.write(json.dumps(YL_payload))
            fid.write("-"*50+"\n")
            fid.close()

      else:
         # Excluded event
         print_nl("%s: Excluded event: %s on %s" % (timestamp(),YL_event, YL_device_name))

         if YL_device_name == '!!!39W Office Temp-Hum':
            try:
               YL_online = YL_payload['data']['online']
            except:
               YL_online = "???"

            if YL_online:
               # Update status dictionary entry with current time
               # Start by getting other fields from dictionary if record exists
               try:
                  YL_battery = dev_status_dictionary[YL_device_name][0]
               except: 
                  YL_battery = '-'

               try:   
                  YL_signal = dev_status_dictionary[YL_device_name][1]
               except:
                  YL_signal = '??'

               try:
                  minimum_signal = dev_status_dictionary[YL_device_name][2]
               except:
                  minimum_signal = '??'

               try:
                  longest_update = dev_status_dictionary[YL_device_name][4]
               except:
                  longest_update = '0'
            
               try: 
                  update_time = dev_status_dictionary[YL_device_name][3]
                  dt_update_time=datetime.datetime.strptime(update_time,'%Y-%m-%d %I:%M:%S %p')
                  et_minutes = int((datetime.datetime.now()-dt_update_time).total_seconds()/60)

                  if et_minutes > int(longest_update):
                     longest_update = str(et_minutes)
               except:
                 longest_update = '0'

               # Write the updated record
               # Currently, this sets battery and current signal to unknown.
               # If desired, can use previous values for YL_battery and YL_signal extracted above.
               dev_status_dictionary[YL_device_name]=['-','??',minimum_signal,timestamp(),longest_update]
               file_dirty = True
               display_table()
   return

def build_allowed_events_table():
   global recognized_events
   recognized_events = []
   recognized_events.append('LeakSensor.Alert')
   recognized_events.append('LeakSensor.Report')
   recognized_events.append('DoorSensor.Alert')
   recognized_events.append('DoorSensor.Report')
   recognized_events.append('DoorSensor.setOpenRemind')
   recognized_events.append('MotionSensor.Alert')
   recognized_events.append('MotionSensor.StatusChange')
   recognized_events.append('MotionSensor.Report')
   recognized_events.append('Manipulator.Alert')
   recognized_events.append('Manipulator.getState')
   recognized_events.append('Manipulator.Report')
   recognized_events.append('Manipulator.StatusChange')
   recognized_events.append('PowerFailureAlarm.Alert')
   recognized_events.append('PowerFailureAlarm.StatusChange')
   recognized_events.append('PowerFailureAlarm.Report')
   recognized_events.append('Switch.Alert')
   recognized_events.append('Switch.Report')
   recognized_events.append('Switch.StatusChange')
   recognized_events.append('Switch.setState')
   recognized_events.append('Switch.getState')
   recognized_events.append('Outlet.Alert')
   recognized_events.append('Outlet.Report')
   recognized_events.append('Outlet.StatusChange')
   recognized_events.append('Outlet.setState')
   recognized_events.append('Outlet.getState')
   recognized_events.append('Outlet.powerReport')
   recognized_events.append('THSensor.Alert')
   recognized_events.append('THSensor.Report')
   recognized_events.append('THSensor.DataRecord')

   if verbose:
      print("\n\nList of recoginized events:\n")
      print (recognized_events)
      print("")
   return()


def build_excluded_events_table():
   global excluded_events
   excluded_events = []
   excluded_events.append('Outlet.powerReport')
   ###excluded_events.append('THSensor.DataRecord')

   if verbose:
      print("\n\nList of excluded events:\n")
      print (excluded_events)
      print("")
   return()

#=============================================================================================
# Get Home ID
#=============================================================================================
def YL_get_home_ID():
   global YL_home_ID, YL_home_ID_valid

   if first_time: post("Getting Home ID")

   url = "https://api.yosmart.com/open/yolink/v2/api"

   headers = CaseInsensitiveDict()
   headers["Content-Type"] = "application/json"
   headers["Authorization"] = "Bearer "+ YL_access_token

   data = '{"method":"Home.getGeneralInfo","time":"' + unix_timestamp() + '"}'

   resp = requests.post(url, headers=headers, data=data)

   if resp.status_code == 200:

      # Response of 200 means valid POST
      # Proceed to request the record
      result = resp.json()

      YL_code = result['code']
      YL_time = result['time']
      YL_msgid = result['msgid']
      YL_method = result['method']
      YL_desc = result['desc']
      YL_home_ID = result["data"]["id"]

      if verbose:
         print("\nHome ID Data Fields:")
         print("code: %s" % YL_code)
         print("time: %s = %s" % (YL_time,unpack_unix_time(YL_time)))
         print("msgid: %s" % YL_msgid)
         print("method: %s" % YL_method)
         print("desc: %s" % YL_desc)
         print("id: %s" % YL_home_ID)

      YL_home_ID_valid = True

   else:
      YL_home_ID_valid = False

   return()

#=============================================================================================
# Get Device List
#=============================================================================================
def YL_get_device_list():
   global YL_device_dictionary
   global YL_dictionary_loaded
   global dictionary_reload_required

   if first_time: post("Getting Device List")

   url = "https://api.yosmart.com/open/yolink/v2/api"

   headers = CaseInsensitiveDict()
   headers["Content-Type"] = "application/json"
   headers["Authorization"] = "Bearer "+ YL_access_token

   data = '{"method":"Home.getDeviceList","time":"' + unix_timestamp() + '"}'

   resp = requests.post(url, headers=headers, data=data)

   if resp.status_code == 200:

      # Response of 200 means valid POST
      # Proceed to request the record
      result = resp.json()

      if verbose: print(result)

      YL_code = result['code']
      YL_time = result['time']
      YL_msgid = result['msgid']
      YL_method = result['method']
      YL_desc = result['desc']

      if verbose:
         print("\nDevice List Fields")
         print("code: %s" % YL_code)
         print("time: %s = %s" % (YL_time,unpack_unix_time(YL_time)))
         print("msgid: %s" % YL_msgid)
         print("method: %s" % YL_method)
         print("desc: %s" % YL_desc)


      # Extract sub-dictionary containing the device information
      YL_device_dictionary = result["data"]["devices"]
      if verbose: print("Dictionary:\n%s\n" % YL_device_dictionary)
      YL_dictionary_loaded = True
      dictionary_reload_required = False

   else:
      YL_dictionary_loaded = False

   return()

#=============================================================================================
# Get Decade
#=============================================================================================

# Function to return integer value of "decade"
def get_decade():
    time = datetime.datetime.now()
    decade = time.strftime("%M")
    decade = int(decade[0:1])
    return decade

#=============================================================================================
# Get Hour
#=============================================================================================

# Function to return integer value of hour
def get_hour():
    time = datetime.datetime.now()
    hour = time.strftime("%H")
    return hour

#=============================================================================================
# Get day of week
#=============================================================================================

# Function to return integer value of "decade"
def get_dow():
    time = datetime.datetime.now()
    dow = time.strftime("%w")
    return int(dow)


def sendemail(from_addr, to_addr_list, cc_addr_list,
              subject, message,
              login, password,
              smtpserver):

    header  = 'From: %s\n' % from_addr 
    header += 'To: %s\n' % ','.join(to_addr_list)
    header += 'Cc: %s\n' % ','.join(cc_addr_list)
    header += 'Subject: %s\n\n' % subject
    message = header + message
 
    try:
        server = smtplib.SMTP_SSL(smtpserver)
        server.login(login,password)
        problems = server.sendmail(from_addr, to_addr_list, message)
        server.quit()
    except:
        problems = "SMTP Server Error"
    return problems

def send_status_email(status_subject, status_message):
    if send_status_emails:
        print_nl("Sending Email %s - %s" % (status_subject, status_message))
        email_status = sendemail(from_addr = email_account_name, 
        to_addr_list = email_addr_list,
        cc_addr_list = [''], 
        subject      = status_subject+'\n', 
        message      = status_message,
        login        = email_account_name, 
        password     = email_account_pw,
        smtpserver   = email_server)
        hour_last_sent = get_hour()
    else:
       email_status = 'Disabled'
       print_nl("Status Email skipped because email disabled")
    return email_status

# ==========================================================================
#
# Main Program
#
# ==========================================================================
first_time = True
current_decade = get_decade()
current_hour = 99
current_dow=9
file_dirty=False

print("\033c\n%s Program start: %s Version %s\n" % (timestamp(),Filename, Version))

if os.path.exists(config_file):
   read_config_variables()
   if valid_config_file:
      post("\n%s\nProgram %s Version %s startup\n%s" % ('='*50, Filename, Version, '='*50))
   else:
      print('Invalid configuration file "%s".  Program unable to continue.\n' % config_file)

else:
   valid_config_file = False
   print('Missing configuraton file "%s".\n' % config_file)
   print('Obtain a copy of "yolink_health_template.cfg", edit it for your environment,')
   print('then save it as "%s" in the same folder as the main "yolink_health.py" program.' % config_file)
   print('\nExiting program\n')

if valid_config_file:
   build_allowed_events_table()
   build_excluded_events_table()
   load_table()

   while True:
      # ------------------------------------------------------------------------
      # Set up MQTT variables, including getting a new token
      # Runs at program start and agin 5 minutes before end of 
      # each access token valid period
      YL_establish_MQTT_connection()

      # ------------------------------------------------------------------------
      # Get list of devices
      YL_get_device_list()

      # Convert device list into dictionary with key = device ID and data = device names
      id_dictionary={}
      if verbose: print("\nYolink Devices Registered to this Account:")

      if logging and first_time: 
         log_fid=open(log_file,'a') 
         log_fid.write("\n")

      for d in YL_device_dictionary:
         if verbose: print("Device: %s" % d['name'])
         if logging and first_time: log_fid.write("Device: %s\n" % d['name'])
         id_dictionary[d['deviceId']]=d['name']

      if logging and first_time: 
         log_fid.write("\n")
         log_fid.close()

      # ------------------------------------------------------------------------
      # Non-Blocking infinite loop looking for responses
      if verbose: print_nl("%s Starting Loop" % timestamp())
      if first_time: post("Starting Loop\n")
      YL_client.loop_start()
      YL_refresh_time = YL_access_token_timestamp+datetime.timedelta(minutes=(YL_token_valid_minutes-5))
      first_time = False
      while datetime.datetime.now() < YL_refresh_time and dictionary_reload_required == False:
      
         # Write the status table to file once every ten minutes
         if current_decade != get_decade():
            if file_dirty:
               if verbose: print_nl("New Decade - Writing Table")
               write_table()
            current_decade = get_decade()

         # Update hub status once an hour
         if current_hour != get_hour():
            # Poll for hub status since hubs don't broadcast status messages
            for d in YL_device_dictionary:
               if d['type'] == 'Hub':
                  on_line = get_device_status(d)
                  if on_line:
                     longest_update = '0'
                     # Update status dictionary with current time -- creates new record if necessary
                     dev_status_dictionary[d['name']]=['-','??','??',timestamp(),longest_update]
                     file_dirty = True
            current_hour = get_hour()

         # If new day, check status and send warning emails as appropriate
         if current_dow != get_dow():
            display_table()
            check_status()
            current_dow = get_dow()

         print_bs(timestamp())
         time.sleep(1)

      # ------------------------------------------------------------------------
      # Time for refresh.  Go to top of loop, re-establish MQQT connection and reload dictionary
      print(backspaces)
      if first_time: post("Stopping Loop")
      YL_client.loop_stop()
      if first_time: post("Disconnecting")
      YL_client.disconnect()
      print_nl("%s Recycling\n" % timestamp())
      post("\nRecyling\n")

# ==========================================================================
# End of Program
