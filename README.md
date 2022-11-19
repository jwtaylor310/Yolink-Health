# Yolink-Health
Python program to monitor the availability, battery level and signal strength of YoLink devices.  As an option, the program can
be configured to send an email alert if a device doesn't respond for an extended period, has a low battery, or a weak signal.

Developed on a Raspberry Pi.  May run in other environments that support Python, but only tested on Pi's.

*** NOTE *** 

This program currently supports the followign YoLink device types.  Other devices may or may not display
correctly.  Please contact the program developer if you have other devices which you would like to have
added:

    Hubs
    Door Sensors
    Motion Sensors
    Power Monitors
    Temperature Sensors
    Temp Humidity Sensors
    Leak Sensors
    YoLink Valves

Setup:
   1. Copy yolink_health.py and yolink_health_template.cfg to a folder on your Raspberry Pi.
  
   2. Obtain User Access Credentials for your YoLink account.  This is done by opening the YoLink app on a cell phone, then selecting the 
      'hamburger' icon at the top-left corner and navigating to Settings...Account...Advanced Settings...User Access Credentials.  Record
      the UAID and Secret Key.  These values are unique to your account and should not be shared.
    
   3. Copy the yolink_health_template.cfg file to yolink_health.cfg.  Then edit yolink_health.cfg to replace the dummy values of UAID and SECRET_KEY
      with the values obtained in the previous step.  If you wish to have alerts sent via email, you should also edit yolink.health.cfg to set
      "send_status_emails=True" and provide valid information for the email address list, server, account name and account password.  The other
      values in the configuration file typically do not need to be changed.
     
     
     
Running the program:
   Open a terminal session on the Raspberry Pi.  Navigate to the folder where you have installed the "yolink_health.py" and "yolink_health.cfg" files.
   Start the program with the command: "python yolink_health.py".  (Some Pi's may require specifying "python3" instead of just "python").  The program
   will start and read the configuration information from the "yolink_health.cfg" file.
   
   The program maintains a device status list in a text file named "yolink_health_table.txt".  This file will automatically be created in the same
   folder that the program is started from the first time the program is run. The program subscribes to the YoLink MQTT broker and waits for status
   messages to appear.  As each status message is received, the program checks to see if the device is already in the "yolink_health_table.txt" file.
   If it does, the status for the device is updated.  If the device does not exist in the file, a new entry is created with the current status.  
   
   THe program is intended to be run continuously. 
   
   Devices remain in the status table forever.  If you take a YoLink device out of service you can remove it from the table manually.  To do so, stop
   the program.  THen use a text editor to located the entry in the "yolink_health_table.txt" file and delete it.  Save the edited table and restart
   the program.  As an alternative, you may simply delete the "yolink_health_table.txt" file and the program will rebuild it from scratch with new data.
      
   Status messages from devices that are not recognized by the program are saved in a file named "yolink_health_failed.log".  This file may be reviewed
   to obtain the information needed to add previously unsupported devices to the program.

     
  
   
