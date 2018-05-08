import configparser
import http.client as httplib
import json
import socket
import threading
import time
import traceback

from datetime import datetime, timedelta
from dateutil import parser
from statistics import mean
from typing import Optional

from requests import Response

from sgreen2_greenhouse.email_client import EmailClient
from sgreen2_greenhouse.error_notifier import ErrorNotifier, Error, ErrorSeverity
from sgreen2_greenhouse.rest_request import RestPutThread, RestDeleteThread, RestThread, RestGet, RestPost
from sgreen2_greenhouse.tplink_smartplug import TpLinkSmartplug


class GreenhouseServer:
    """
    The main class for the greenhouse server
    """

    def __init__(self, configfile: str):
        """
        The constructor. Initializes an email client and TP-Link smartplug
        :param configfile: a configuration file
        """
        self.config = configparser.ConfigParser()
        self.config.read(configfile)

        self.base_url = self.config["rest"]["base_url"]
        self.local_base_url = None

        if "local_base_url" in self.config["rest"]:
            self.local_base_url = self.config["rest"]["local_base_url"]

        self.active_url = self.base_url

        email_server = self.config["email"]["smtp_server"]
        email_port = int(self.config["email"]["tls_port"])
        email_username = self.config["email"]["username"]
        email_password = self.config["email"]["password"]

        self.email_client = EmailClient(email_server, email_port, email_username, email_password)

        bigfan_tp_link_ip = self.config["smartplug"]["bigfan_smartplug_ip"]
        bigfan_tp_link_port = int(self.config["smartplug"]["bigfan_smartplug_port"])

        self.bigfan_tp_link_smartplug = TpLinkSmartplug(bigfan_tp_link_ip, bigfan_tp_link_port)

        heater_tp_link_ip = self.config["smartplug"]["heater_smartplug_ip"]
        heater_tp_link_port = int(self.config["smartplug"]["heater_smartplug_port"])

        self.heater_tp_link_smartplug = TpLinkSmartplug(heater_tp_link_ip, heater_tp_link_port)

        # how many consecutive times does an error have to be detected before being ready for an email notification
        error_stages = int(self.config["email"]["error_stages"])
        self.error_notifier = ErrorNotifier(self.email_client, error_stages)

        self.backup_emails = [self.config["email"]["admin_email"]]
        self.email_addresses = list()

        self.watering_times = list()
        self.error_flush_times = list()

    def __timestring_list_to_datetime_list(self, timelist: list) -> list:
        for i in range(len(timelist)):
            timelist[i] = parser.parse(timelist[i])
            if timelist[i] < self.get_current_time():
                timelist[i] += timedelta(days=1)

        return timelist

    @staticmethod
    def have_internet():
        conn = httplib.HTTPConnection("www.google.com", timeout=1)
        try:
            conn.request("HEAD", "/")
            conn.close()
            return True
        except OSError:
            conn.close()
            return False

    def run(self):
        """
        Runs the main program
        """
        try:
            connection_error_key = "connection_refused"

            while True:
                try:
                    if self.have_internet() or self.local_base_url is None:
                        self.active_url = self.base_url
                    else:
                        self.active_url = self.local_base_url

                    # greenhouse is up and running
                    RestPost.send(self.active_url + "/greenhouse_server_state", None)

                    settings_response = RestGet.send(self.active_url + "/settings", None)

                    if self.is_error_response("fetch_settings", "Fetching settings failed", settings_response,
                                              ErrorSeverity.HIGH):
                        continue

                    settings = json.loads(settings_response.text)

                    # set watering and flush times if not already set
                    if not self.watering_times:
                        self.watering_times = self.__timestring_list_to_datetime_list(settings["watering_times"])

                    if not self.error_flush_times:
                        self.error_flush_times = self.__timestring_list_to_datetime_list(settings["error_flush_times"])

                    self.email_addresses = settings["email_addresses"]

                    if settings["is_manual_mode"]:
                        print("going to manual mode")
                        self.__perform_manual_mode()
                    else:
                        print("going to automated mode")
                        self.__perform_automated_mode(settings)

                    # flush errors
                    for i in range(len(self.error_flush_times)):
                        if self.get_current_time() >= self.error_flush_times[i]:
                            self.error_flush_times[i] += timedelta(days=1)
                            self.error_notifier.send_message(self.email_addresses, True)
                            break

                    self.error_notifier.remove_error(connection_error_key)
                except OSError as err:
                    error_message = \
                        "Connection refused error. Rest API server may be down. Exception message: " + str(err)
                    print(error_message)
                    traceback.print_exc()
                    self.error_notifier.add_error(Error(ErrorSeverity.HIGH, error_message, connection_error_key))
                    self.error_notifier.send_message(
                        self.email_addresses if self.email_addresses else self.backup_emails)
        except KeyboardInterrupt:
            print("Received keyboard interrupt. Stopping...")
        except Exception as err:
            error_message = "An error occurred and now the greenhouse server is dead. Error message: " + str(err) + \
                            ". See terminal output for traceback"
            self.error_notifier.add_error(Error(ErrorSeverity.CRITICAL, error_message, "greenhouse_killer"))
            print(error_message)
            self.error_notifier.send_message(self.email_addresses if self.email_addresses else self.backup_emails)

            traceback.print_exc()
        finally:
            self.error_notifier.quit()

    @staticmethod
    def get_current_time():
        return datetime.now()

    @staticmethod
    def create_error_message(message: str, response: Response) -> str:
        """
        Creates an error message for a response error
        :param message: The custom message before the details
        :param response: The response object
        :return: a formatted error message
        """

        body = response.text if "text" in response else ""
        return message + "\nStatus code: " + response.status_code + "\nResponse body: " + body + "\n"

    @staticmethod
    def group_data_by_sensor(raw_data: dict) -> dict:
        """
        Groups data by sensor
        :param raw_data: the raw json data from the database
        :return: a dict of sensor and its readings
        """
        result = dict()
        for reading in raw_data:
            sensor = reading["sensor"]["name"]
            if sensor not in result:
                result[sensor] = list()

            if "health" in reading:
                result[reading["sensor"]["name"]].append({"reading": reading["reading"], "health": reading["health"]})
            else:
                result[reading["sensor"]["name"]].append(reading["reading"])

        return result

    @staticmethod
    def group_actuators(actuators: list) -> dict:
        """
        Groups the actuators by type. Assumes the actuators are sorted by type.
        :param actuators: a list of actuators sorted by type
        :return: a dictionary of actuators with key = type, value = actuator
        """
        result = dict()
        previous_type = None
        for actuator in actuators:
            if actuator["type"] != previous_type:
                result[actuator["type"]] = list()

            result[actuator["type"]].append(actuator)
            previous_type = actuator["type"]

        return result

    @staticmethod
    def find_actuator(actuators: list, name: str) -> dict:
        """
        Returns actuator with name actuator from a list of actuators
        :param actuators: the list of actuators
        :param name: the name of the actuator to get
        :return: a dict representing the actuator
        """
        for actuator in actuators:
            if actuator["name"] == name:
                return actuator

    def set_actuator_state_and_update_db(self, actuator: dict) -> RestThread:
        """
        Sets the actuator state and updates the database with the new state
        :param actuator: the actuator
        :return: a RestThread
        """
        state = actuator["state"]
        thread = RestPutThread(self.active_url + "/actuators/" + actuator["name"] + "/state") if state else \
            RestDeleteThread(self.active_url + "/actuators/" + actuator["name"] + "/state")
        thread.start()
        self.set_actuator_state(actuator)

        return thread

    def set_actuator_state(self, actuator: dict) -> None:
        """
        Turns on/off an actuator
        :param actuator: the actuator object
        :return: None
        """

        # actuators controlled by a smartplug
        smart_plug = None
        if actuator["name"] == "bigfan":
            smart_plug = self.bigfan_tp_link_smartplug
        elif actuator["name"] == "heater01":
            smart_plug = self.heater_tp_link_smartplug

        if smart_plug is not None:
            connect_error_key = "smartplug_connection_" + actuator["name"]
            except_error_key = "smartplug_exception_" + actuator["name"]
            try:
                smart_plug.set_state(actuator["state"])
                self.error_notifier.remove_error(connect_error_key)
                self.error_notifier.remove_error(except_error_key)
            except OSError:
                error_message = "Unable to connect to " + actuator["name"] + " TP-Link Smartplug"
                print(error_message)
                self.error_notifier.add_error(Error(ErrorSeverity.HIGH, error_message, connect_error_key))
                return
            except Exception as err:
                error_message = str(err)
                print(error_message)
                self.error_notifier.add_error(Error(ErrorSeverity.MID, error_message, except_error_key))
        # actuators controlled by raspberry pis
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            on_off_state = "on" if actuator["state"] else "off"

            pi_ip = None
            pi_port = int(self.config["pi"]["socket_port"])

            if actuator["type"] == "fan":
                pi_ip = self.config["pi"]["fan_pi_ip"]
            elif actuator["type"] == "lights":
                pi_ip = self.config["pi"]["lights_pi_ip"]
            elif actuator["type"] == "water":
                pi_ip = self.config["pi"]["solenoid_pi_ip"]

            if pi_ip is not None:
                error_code = sock.connect_ex((pi_ip, pi_port))

                error_key = actuator["type"] + "_pi_connection"
                if error_code != 0:
                    error_message = "Unable to connect to " + actuator["type"] + " pi"
                    print(error_message)
                    self.error_notifier.add_error(Error(ErrorSeverity.HIGH, error_message, error_key))
                    return
                else:
                    self.error_notifier.remove_error(error_key)

                msg = ":".join((actuator["name"], actuator["type"], on_off_state))
                sock.send(msg.encode())
                print("SENDING: " + msg)
                sock.close()

    def is_error_response(self, error_key: str, error_message: str, response: Response,
                          severity: ErrorSeverity = ErrorSeverity.MID) -> bool:
        """
        Checks if a response came back with an error code
        :param error_key: the error key for the error to raise
        :param error_message: the message for the error
        :param response: the response to analyze
        :param severity: the error severity
        :return: True if the response is bad
        """
        if not response.ok:
            error_message = self.create_error_message(error_message, response)
            print(error_message)
            self.error_notifier.add_error(Error(severity, error_message, error_key))
            return True
        else:
            self.error_notifier.remove_error(error_key)
            return False

    def detect_missing_sensors(self, severity: ErrorSeverity, error_key: str, error_message: str,
                               sensor_data_by_sensor: dict, num_expected_sensors: int) -> None:
        """
        Detects whether any sensors failed to post data
        :param severity: the severity of the error for the error notifier
        :param error_key: the error key for the error notifier
        :param error_message: the message for the error notifier
        :param sensor_data_by_sensor: the data readings grouped by sensor
        :param num_expected_sensors: how many sensors did we expect to get data from?
        :return: None
        """
        if len(sensor_data_by_sensor) < num_expected_sensors:
            error_message += "\n\tReceived data from: " + ",".join(sensor_data_by_sensor.keys())
            print(error_message)
            self.error_notifier.add_error(Error(severity, error_message, error_key))
        else:
            self.error_notifier.remove_error(error_key)

    def check_if_actuator_state_is_correct(self, actuator_data_by_sensor: dict, actuators: list, on_threshold: float,
                                           off_threshold: float) -> None:
        """
        Checks if an actuator's state is consistent with data readings
        :param actuator_data_by_sensor: the data readings that can determine if an actuator is on or not
        :param actuators: the list of actuators
        :param on_threshold: the minimum threshold for being on
        :param off_threshold: the maximum threshold for being off
        :return: None
        """
        for actuator_name in actuator_data_by_sensor:
            error_key = "state_" + actuator_name
            error_message = None
            actuator = self.find_actuator(actuators, actuator_name)
            if actuator["state"] and actuator_data_by_sensor[actuator_name][0] < on_threshold:
                error_message = "Actuator " + actuator_name + " is supposed to be on, but is off."
            elif not actuator["state"] and actuator_data_by_sensor[actuator_name][0] > off_threshold:
                error_message = "Actuator " + actuator_name + " is supposed to be off, but is on."
            else:
                self.error_notifier.remove_error(error_key)

            if error_message:
                print(error_message)
                self.error_notifier.add_error(Error(ErrorSeverity.MID, error_message, error_key))

    def turn_on_actuator_and_update_db_for_time(self, actuator: dict, num_seconds: int) -> None:
        """
        Turns on an actuator. Waits for num_seconds. And then turns off the actuator. This includes
        updating the db with the actuator state
        :param actuator: the actuator to turn on then off
        :param num_seconds: how many seconds for which the actuator should be on
        :return: None
        """
        actuator["state"] = True
        db_thread = self.set_actuator_state_and_update_db(actuator)
        db_thread.join()

        time.sleep(num_seconds)

        db_thread.join()

        actuator["state"] = False
        db_thread = self.set_actuator_state_and_update_db(actuator)
        db_thread.join()

    def check_margin_and_range(self, data_by_sensor: dict, sensor_type: str, min_expected: float, max_expected: float,
                               difference_margin: Optional[float], **kwargs) -> None:
        """
        Checks whether the data is within a specified margin and a specified range
        :param data_by_sensor: the data grouped by sensor
        :param sensor_type: the type of the sensors
        :param min_expected: the minimum expected value
        :param max_expected: the maximum expected value
        :param difference_margin: the difference margin to consider when measuring values between sensors
        :param kwargs: sensor_display_type, sensor_display_unit
        :return: None
        """
        min_avg = None
        max_avg = None

        sensor_display_type = sensor_type
        sensor_display_unit = "units"

        if "sensor_display_type" in kwargs:
            sensor_display_type = kwargs["sensor_display_type"]

        if "sensor_display_unit" in kwargs:
            sensor_display_unit = kwargs["sensor_display_unit"]

        for sensor in data_by_sensor:
            avg_reading = mean(data_by_sensor[sensor])
            if min_avg is None or avg_reading < min_avg["reading"]:
                min_avg = {"sensor": sensor, "reading": avg_reading}

            if max_avg is None or avg_reading > max_avg["reading"]:
                max_avg = {"sensor": sensor, "reading": avg_reading}

            # is the temperature in an expected range?
            error_key = "range_error_" + sensor

            if not min_expected <= avg_reading <= max_expected:
                error_message = "Sensor " + sensor + " reading outside of expected range\n" + \
                                "\tReading: " + "{0:.2f}".format(avg_reading)
                print(error_message)
                self.error_notifier.add_error(Error(ErrorSeverity.LOW, error_message, error_key))
            else:
                self.error_notifier.remove_error(error_key)

        if difference_margin is not None and max_avg is not None and min_avg is not None:
            error_key = "margin_error_" + sensor_type
            if max_avg["reading"] - min_avg["reading"] > difference_margin:
                error_message = \
                    sensor_display_type + " sensors disagree by more than " + str(difference_margin) + " " + \
                    sensor_display_unit + " \n" + \
                    "\tMax Sensor: " + max_avg["sensor"] + ", Reading: " + "{0:.2f}".format(max_avg["reading"]) + \
                    "\n\tMin Sensor: " + min_avg["sensor"] + ", Reading: " + "{0:.2f}".format(min_avg["reading"])
                print(error_message)
                self.error_notifier.add_error(Error(ErrorSeverity.LOW, error_message, error_key))
            else:
                self.error_notifier.remove_error(error_key)

    def check_fans(self, actuators: list, initial_delay: Optional[int]) -> None:
        """
        Checks if the fans are doing what they are supposed to be doing
        :param actuators: the list of actuators
        :param initial_delay: if you want to delay the check first to allow time for the sensors to post data
        :return: None
        """
        if initial_delay:
            time.sleep(initial_delay)

        one_minute_ago = int(time.time() - 1 * 60) * 1000
        fanspeed_response = RestGet.send(self.active_url + "/data_readings",
                                         {"type": "fanspeed", "start_time": one_minute_ago})

        # check for bad request
        if self.is_error_response("fetch_fanspeed", "Fetching fan speed data failed", fanspeed_response):
            return
        fanspeed_data_by_sensor = self.group_data_by_sensor(json.loads(fanspeed_response.text))

        # check for missing sensors
        num_fanspeed_sensors = int(self.config["sensors"]["number_fanspeed_sensors"])
        self.detect_missing_sensors(ErrorSeverity.LOW, "missing_sensors_fanspeed",
                                    "Not all fan speed sensors submitted data in the last minute",
                                    fanspeed_data_by_sensor, num_fanspeed_sensors)

        # perform fan check
        self.check_if_actuator_state_is_correct(fanspeed_data_by_sensor, actuators,
                                                int(self.config["ranges"]["min_on_fanspeed"]),
                                                int(self.config["ranges"]["max_off_fanspeed"]))

    def __perform_manual_mode(self) -> None:
        """
        Runs manual mode, which is just polling database and checking the state of the actuators
        :return: None
        """
        # grab actuators
        actuators_response = RestGet.send(self.active_url + "/actuators", None)
        actuators = json.loads(actuators_response.text)

        # turn on/off actuators
        for actuator in actuators:
            self.set_actuator_state(actuator)

        check_fans_thread = threading.Thread(target=self.check_fans(actuators, 1))
        check_fans_thread.start()

        time.sleep(1)
        check_fans_thread.join()

        self.error_notifier.send_message(self.email_addresses)

    def __perform_automated_mode(self, settings: dict) -> None:
        """
        Runs automated mode, which performs data reading checks and responses
        :param settings: the settings
        :return: None
        """

        # get actuators
        actuators_response = RestGet.send(self.active_url + "/actuators", None)

        if self.is_error_response("fetch_actuators", "Fetching actuators data failed", actuators_response):
            return

        actuators = json.loads(actuators_response.text)

        # local import because else there'd be a circular dependency
        from sgreen2_greenhouse.automated_actuators import AutomatedSolenoids, AutomatedFans, AutomatedLights, \
            ActuatorBatteries

        # perform all automated stuff
        actuator_threads = list()
        actuator_threads.extend([
            AutomatedFans(self, actuators, settings),
            AutomatedSolenoids(self, actuators, settings),
            AutomatedLights(self, actuators, settings),
            ActuatorBatteries(self)
        ])

        for thread in actuator_threads:
            thread.start()

        time.sleep(5)

        for thread in actuator_threads:
            thread.join()

        # send an error notification if needed
        self.error_notifier.send_message(self.email_addresses)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: " + sys.argv[0] + " [configfile]")
        exit(1)

    server = GreenhouseServer(sys.argv[1])
    server.run()
