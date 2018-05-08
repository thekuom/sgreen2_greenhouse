import json

import datetime
import requests
import serial
import configparser


def main(configfile: str) -> None:
    config = configparser.ConfigParser()
    config.read(configfile)

    base_url = config["rest"]["base_url"]
    local_base_url = None

    if "local_base_url" in config["rest"]:
        local_base_url = config["rest"]["local_base_url"]

    arduino_baud_rate = int(config["arduino"]["arduino_baud_rate"])

    arduino_serial_path = "/dev/ttyUSB0"

    with serial.Serial(arduino_serial_path, arduino_baud_rate, timeout=.1) as arduino:
        while True:
            try:
                arduino_data = arduino.readline().strip()
                if arduino_data:
                    print(str(datetime.datetime.now()) + " " + str(arduino_data))
                    json_data = json.loads(arduino_data)

                    if local_base_url:
                        local_post_request = requests.post(local_base_url + "/data_readings",
                                                           data=json.dumps(json_data),
                                                           headers={"content-type": "application/json"})
                        local_post_request.raise_for_status()

                    post_request = requests.post(base_url + "/data_readings", data=json.dumps(json_data),
                                                 headers={"content-type": "application/json"}, timeout=1)
                    post_request.raise_for_status()
            except Exception as e:
                print(str(e))


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: " + sys.argv[0] + " [configfile]")
        exit(1)

    main(sys.argv[1])
