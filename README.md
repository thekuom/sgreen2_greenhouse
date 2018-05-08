sgreen2_greenhouse README
=========================
I highly recommend using PyCharm with this project. This also helps you stick to PEP8 and avoid spaghetti code nonsense.

Dependencies
------------
### Python3.6 and Virtual Environment
Virtual environment can either be `virtualenv` or `venv`.

### Python development package
Ubuntu:
```
sudo apt-get install python3-dev
```

Getting Started
---------------
### Cloning
```
git clone https://github.com/thekuom/sgreen2_greenhouse
```
### Setting up virtual environment
Using `venv`
```
cd sgreen2_greenhouse
python3 -m venv venv
```
Using `virtualenv`
```
cd sgreen2_greenhouse
python3 -m virtualenv venv
```

### Installing on the Greenhouse
```
venv/bin/pip install -e ".[greenhouse]"
```

### Installing on the Pis
```
venv/bin/pip install -e ".[pis]"
```

### Running on the Greenhouse
```
venv/bin/python sgreen2_greenhouse/greenhouse_server.py [configfile]
```

### Running ActuatorStateListener on the Pis
```
venv/bin/python sgreen2_pi/actuator_state_listener.py [configfile]
```

### Running DataReadingListener on the Pis
```
venv/bin/python sgreen2_pi/data_reading_listener.py [configfile]
```

File Tree
---------
```
sgreen2_arduino/                : code for the arduinos - these aren't actually in Python
    data_sensor_module/         : code for the temperature/humidity sensor and fanspeed sensor arduino
    soil_module/                : code for the soil module arduinos
sgreen2_greenhouse/             : code for the greenhouse server
    __init__.py                 : recognizes this folder as a python package
    automated_actuators.py      : a bunch of thread classes that perform the automated functionality
    email_client.py             : easily send emails with this class
    error_notifier.py           : error notification system (see Explanations section)
    greenhouse_server.py        : the main program for the greenhouse
    rest_request.py             : easily send requests to the REST API with this module
    tplink_smartplug.py         : easily connect and send commands to a TP Link Smartplug with this class
sgreen2_pi/                     : code for the Pis
    __init__.py                 : recognizes this folder as a python package
    _relay_controller.py        : base class for relay controller classes
    actuator_state_listener.py  : main program for pis that control actuators
    data_reading_listener.py    : main program for pis that get sensor data from arduinos
    fan_relay_controller.py     : controls fans
    light_relay_controller      : controls lights
    solenoid_relay_controller   : controls solenoids
venv/                           : your Python virtual environment
.gitignore                      : the gitignore
development.ini                 : configuration file for development mode
production.ini                  : configuration file for prod
README.md                       : this file
setup.py                        : defines dependencies and other first time setup things
```

### .ini File Layout

```
[rest]
base_url = the base url for the rest api
local_base_url = the base url for the locally running rest api (optional)

[ranges]
min_soil_moisture = the minimum expected soil moisture percentage
max_soil_moisture = the maximum expected soil moisture percentage
min_temperature = the minimum expected temperature reading
max_temperature = the maximum expected temperature reading
min_humidity = the minimum expected humidity reading
max_humidity = the maximum expected humidity reading
max_off_fanspeed = the highest a fanspeed sensor can read and still be considered off
min_on_fanspeed = the lowest a fanspeed sensor can read and still be considered on

[sensors]
number_soil_sensors = how many soil moisture sensors are expected to post data
number_temperature_sensors = how many temperature sensors are expected to post data
number_fanspeed_sensors = how many fanspeed sensors are expected to post data
number_battery_sensors = how many battery sensors are expected to post data
temperature_margin = how far apart can different temperature sensor readings be before it's a warning
humidity_margin = how far apart can different humidity sensor readings be before it's a warning

[email]
smtp_server = the url for the smtp server
tls_port = the tls port for the smtp server
username = the email address to log in to the smtp server
password = the password for the smtp server
admin_email = the admin email to send errors to if the system cannot fetch settings
error_stages = how many stages must an error go through before being sent? (lower is more frequent emails)

[greenhouse]
greenhouse_ip = the static ip of the computer running greenhouse_server.py

[smartplug]
bigfan_smartplug_ip = the static ip of the tp link smartplug which controls the big fan
bigfan_smartplug_port = the port of the tp link smartplug which controls the big fan
heater_smartplug_ip = the static ip of the tp link smartplug which controls the heater
heater_smartplug_port = the port of the tp link smartplug which controls the heater

[pi]
solenoid_pi_ip = the static ip of the raspberry pi which controls the solenoids
fan_pi_ip = the static ip of the raspberry pi which controls the fans
lights_pi_ip = the static ip of the raspberry pi which controls the lights
socket_port = the port that the pis will use to listen on

[arduino]
arduino_baud_rate = the baud rate to communicate with the arduino serial

[fan] the GPIO pins for the fans
fan01_pin = 
fan02_pin = 
fan03_pin = 
fan04_pin = 

[lights] the GPIO pins for the lights
lights01_pin = 
lights02_pin = 

[soil_moisture] the solenoid name corresponding to each soil sensor
soil01_solenoid = 
soil02_solenoid = 
soil03_solenoid = 
soil04_solenoid = 
soil05_solenoid = 

[solenoid] the GPIO pins for the solenoids
master_solenoid_pin = 
solenoid01_pin = 
solenoid02_pin = 
solenoid03_pin = 
solenoid04_pin = 
solenoid05_pin = 
solenoid06_pin = 
solenoid07_pin = 
# how long for which to turn each solenoid on (water pressure could be different)
solenoid01_seconds = 10
solenoid02_seconds = 10
solenoid03_seconds = 10
solenoid04_seconds = 10
solenoid05_seconds = 10
solenoid06_seconds = 1
solenoid07_seconds = 10
```

Explanations
------------

## ErrorNotifier System

The error notifier system is admittedly weird. To help understand why I did what I did, it helps to outline some
of the problems I faced when designing it.

1. I did not want to send an email every 10 seconds. This is why it has a severity threshold and we only send an email
if the severity is past that threshold or if we are flushing the message buffer. In addition, the staging system
reduces email frequency.

2. I did not want duplicate errors contributing to the severity. This is what active_errors and the error_keys are all
about. Each error that could occur is given an error_key by the programmer. If we add an error with an error_key that
is already an active_error, then we ignore it, because then we assume the error is ongoing and hasn't been resolved yet.
Once the error has been resolved, we can remove the error from the active_errors.

3. I did not want the entire system to halt while sending out an email notification. This is why I use a custom thread
class to send the email and this is why I never join that email sending thread until I need to send another email.

## TP Link Smartplug

The TP Link Smartplug code is adapted from this github: https://github.com/softScheck/tplink-smartplug.
Please do not update the firmware! Keep it at 1.2.9. TP Link added security features to it that will prevent us from
being able to send commands to it in the current way.

Known Bugs
----------

1. Sometimes has connection errors
2. Delays. This is probably because of the overhead in opening sockets and all the requests that are being made. I think
the delays are acceptable because we are not dealing with quickly moving parts. Temperature does not change in a
matter of seconds.

Future Development
------------------

1. Auto-tuning the amount of time for which each solenoid gets turned on
