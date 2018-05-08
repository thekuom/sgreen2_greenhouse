import json
import threading
import time
from datetime import timedelta
from statistics import mean

from dateutil import parser

from sgreen2_greenhouse.error_notifier import ErrorSeverity, Error
from sgreen2_greenhouse.greenhouse_server import GreenhouseServer
from sgreen2_greenhouse.rest_request import RestGetThread, RestGet


class AutomatedFans(threading.Thread):
    """
    Thread that executes logic for automating the fans
    """

    def __init__(self, greenhouse_server: GreenhouseServer, actuators: list, settings: dict):
        threading.Thread.__init__(self)
        self.gs = greenhouse_server
        self.actuators = actuators
        self.settings = settings

    def run(self):
        ################################################################################################################
        # get data
        ################################################################################################################

        five_minutes_ago = int(time.time() - 5 * 60) * 1000

        temperature_thread = RestGetThread(self.gs.active_url + "/data_readings",
                                           {"type": "temp", "start_time": five_minutes_ago})
        humidity_thread = RestGetThread(self.gs.active_url + "/data_readings",
                                        {"type": "humid", "start_time": five_minutes_ago})

        temperature_thread.start()
        humidity_thread.start()

        temperature_thread.join()
        humidity_thread.join()

        temperature_data = json.loads(temperature_thread.response.text)
        humidity_data = json.loads(humidity_thread.response.text)

        ################################################################################################################
        # check for errors
        ################################################################################################################

        if self.gs.is_error_response("fetch_temp", "Fetching temperature data failed", temperature_thread.response):
            return

        if self.gs.is_error_response("fetch_humid", "Fetching humidity data failed", humidity_thread.response):
            return

        temp_data_by_sensor = self.gs.group_data_by_sensor(temperature_data)
        humidity_data_by_sensor = self.gs.group_data_by_sensor(humidity_data)

        # did all the sensors post data?
        ################################################################################################################
        num_temp_sensors = int(self.gs.config["sensors"]["number_temperature_sensors"])
        num_humid_sensors = num_temp_sensors

        self.gs.detect_missing_sensors(ErrorSeverity.MID, "missing_sensors_temp",
                                       "Not all temperature sensors submitted data in the last 5 minutes",
                                       temp_data_by_sensor, num_temp_sensors)

        self.gs.detect_missing_sensors(ErrorSeverity.MID, "missing_sensors_humid",
                                       "Not all humidity sensors submitted data in the last 5 minutes",
                                       humidity_data_by_sensor, num_humid_sensors)

        ################################################################################################################
        # take action
        ################################################################################################################

        actuator_groups = self.gs.group_actuators(self.actuators)

        db_threads = list()

        if len(temperature_data) > 0:
            avg_temp = mean([reading["reading"] for reading in temperature_data])

            turn_on_fans = float(avg_temp) > int(self.settings["temperature"]["max"])
            turn_on_heater = float(avg_temp) < int(self.settings["temperature"]["min"])

            fans = actuator_groups["fan"]
            heaters = actuator_groups["heater"]

            for fan in fans:
                fan["state"] = turn_on_fans
                db_threads.append(self.gs.set_actuator_state_and_update_db(fan))

            for heater in heaters:
                heater["state"] = turn_on_heater
                db_threads.append(self.gs.set_actuator_state_and_update_db(heater))

            # join threads
            for thread in db_threads:
                thread.join()

        # continue less serious error checks
        # check if fans are doing what it should be doing
        ################################################################################################################
        check_fans_thread = threading.Thread(target=self.gs.check_fans, args=(self.actuators, 3))
        check_fans_thread.start()

        # check if temperature/humidity readings make sense (within expected range, agree within margin)
        ################################################################################################################
        temperature_margin = int(self.gs.config["sensors"]["temperature_margin"])
        min_expected_temp = int(self.gs.config["ranges"]["min_temperature"])
        max_expected_temp = int(self.gs.config["ranges"]["max_temperature"])

        self.gs.check_margin_and_range(temp_data_by_sensor, "temp", min_expected_temp, max_expected_temp,
                                       temperature_margin, sensor_display_type="Temperature",
                                       sensor_display_unit="degrees")

        humidity_margin = int(self.gs.config["sensors"]["humidity_margin"])
        min_expected_humidity = int(self.gs.config["ranges"]["min_humidity"])
        max_expected_humidity = int(self.gs.config["ranges"]["max_humidity"])

        self.gs.check_margin_and_range(humidity_data_by_sensor, "humid", min_expected_humidity, max_expected_humidity,
                                       humidity_margin, sensor_display_type="Humidity", sensor_display_unit="percent")

        check_fans_thread.join()


class ActuatorBatteries(threading.Thread):
    """
    Thread that checks battery health
    """

    def __init__(self, greenhouse_server: GreenhouseServer):
        threading.Thread.__init__(self)
        self.gs = greenhouse_server

    def run(self):
        ################################################################################################################
        # get data
        ################################################################################################################

        one_day_ago = int(time.time() - (24 * 60 * 60)) * 1000

        battery_response = RestGet.send(self.gs.active_url + "/data_readings",
                                        {"type": "batt", "start_time": one_day_ago})

        battery_data = json.loads(battery_response.text)

        ################################################################################################################
        # error checking
        ################################################################################################################

        if self.gs.is_error_response("fetch_batt", "Fetching battery data failed", battery_response):
            return

        battery_data_by_sensor = self.gs.group_data_by_sensor(battery_data)
        num_battery_sensors = int(self.gs.config["sensors"]["number_battery_sensors"])

        self.gs.detect_missing_sensors(ErrorSeverity.MID, "missing_sensors_batt",
                                       "Not all battery sensors submitted data in the last 24 hours",
                                       battery_data_by_sensor, num_battery_sensors)

        for sensor in battery_data_by_sensor:
            error_key = "low_battery_" + sensor
            if battery_data_by_sensor[sensor][0]["health"] == "critical":
                error_message = "Module " + sensor + " needs battery replacement"
                print(error_message)
                self.gs.error_notifier.add_error(Error(ErrorSeverity.MID, error_message, error_key))
            else:
                self.gs.error_notifier.remove_error(error_key)


class AutomatedSolenoids(threading.Thread):
    """
    Thread that handles logic of automating the solenoids
    """

    def __init__(self, greenhouse_server: GreenhouseServer, actuators: list, settings: dict):
        threading.Thread.__init__(self)
        self.gs = greenhouse_server
        self.actuators = actuators
        self.settings = settings

    def run(self):
        ################################################################################################################
        # get data
        ################################################################################################################

        one_day_ago = int(time.time() - (24 * 60 * 60)) * 1000

        soil_moisture_response = RestGet.send(self.gs.active_url + "/data_readings",
                                              {"type": "soil", "start_time": one_day_ago})

        soil_moisture_data = json.loads(soil_moisture_response.text)

        ################################################################################################################
        # error checking
        ################################################################################################################

        if self.gs.is_error_response("fetch_soil", "Fetching soil moisture data failed", soil_moisture_response):
            return

        soil_moisture_data_by_sensor = self.gs.group_data_by_sensor(soil_moisture_data)
        num_soil_sensors = int(self.gs.config["sensors"]["number_soil_sensors"])

        self.gs.detect_missing_sensors(ErrorSeverity.MID, "missing_sensors_soil",
                                       "Not all soil moisture sensors submitted data in the last 24 hours",
                                       soil_moisture_data_by_sensor, num_soil_sensors)

        # are the soil moisture readings within an expected range?
        ################################################################################################################

        min_expected_soil = int(self.gs.config["ranges"]["min_soil_moisture"])
        max_expected_soil = int(self.gs.config["ranges"]["max_soil_moisture"])
        for sensor in soil_moisture_data_by_sensor:
            reading = soil_moisture_data_by_sensor[sensor][0]
            error_key = "exceeds_max_soil_" + sensor
            if reading > self.settings["soil_moisture"]["max"]:
                error_message = "Soil moisture sensor " + sensor + \
                                " reading above configured max\n\tYou may need to check if the water is leaking.\n" + \
                                "\tReading: " + "{0:.2f}".format(reading)

                print(error_message)
                self.gs.error_notifier.add_error(Error(ErrorSeverity.MID, error_message, error_key))
            else:
                self.gs.error_notifier.remove_error(error_key)

        self.gs.check_margin_and_range(soil_moisture_data_by_sensor, "soil", min_expected_soil, max_expected_soil, None,
                                       sensor_display_type="Soil moisture", sensor_display_unit="percent")

        ################################################################################################################
        # take action if it's time to check
        ################################################################################################################

        for i in range(len(self.gs.watering_times)):
            if self.gs.get_current_time() >= self.gs.watering_times[i]:
                self.gs.watering_times[i] += timedelta(days=1)

                solenoid_threads = list()
                if len(soil_moisture_data_by_sensor) > 0:
                    for sensor in soil_moisture_data_by_sensor:
                        # we don't know which solenoid corresponds to this soil moisture sensor
                        if not (sensor + "_solenoid") in self.gs.config["soil_moisture"]:
                            continue

                        reading = soil_moisture_data_by_sensor[sensor][0]
                        if reading < self.settings["soil_moisture"]["min"]:
                            solenoid_name = self.gs.config["soil_moisture"][sensor + "_solenoid"]
                            solenoid = self.gs.find_actuator(self.actuators, solenoid_name)
                            num_seconds = int(self.gs.config["solenoid"][solenoid_name + "_seconds"])
                            solenoid_thread = threading.Thread(target=self.gs.turn_on_actuator_and_update_db_for_time,
                                                               args=(solenoid, num_seconds))
                            solenoid_thread.start()
                            solenoid_threads.append(solenoid_thread)

                # join the solenoid threads
                for thread in solenoid_threads:
                    thread.join()

                break


class AutomatedLights(threading.Thread):
    """
    Thread that handles the logic of automating the lights
    """

    def __init__(self, greenhouse_server: GreenhouseServer, actuators: list, settings: dict):
        threading.Thread.__init__(self)
        self.gs = greenhouse_server
        self.actuators = actuators
        self.settings = settings

    def run(self):
        lights_start_time = parser.parse(self.settings["lights"]["start_time"])
        lights_end_time = parser.parse(self.settings["lights"]["end_time"])

        now = self.gs.get_current_time()

        # make the times during the current day
        lights_start_time = now.replace(hour=lights_start_time.hour, minute=lights_start_time.minute)
        lights_end_time = now.replace(hour=lights_end_time.hour, minute=lights_end_time.minute)

        # I would suggest playing with some examples here
        # the end time is in the next day
        if lights_end_time < lights_start_time:
            # we haven't reached the end time yet, so subtract the start time day to show we are still in that interval
            if now < lights_end_time:
                lights_start_time -= timedelta(days=1)
            # we are past the end time so set up the next interval
            else:
                lights_end_time += timedelta(days=1)

        actuator_groups = self.gs.group_actuators(self.actuators)

        turn_on_lights = lights_start_time <= now <= lights_end_time
        for light in actuator_groups["lights"]:
            light["state"] = turn_on_lights
            self.gs.set_actuator_state_and_update_db(light)
