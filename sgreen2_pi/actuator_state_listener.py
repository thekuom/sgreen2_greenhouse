import configparser
import socket
import threading

import RPi.GPIO as GPIO

from sgreen2_pi.fan_relay_controller import FanRelayController
from sgreen2_pi.light_relay_controller import LightsRelayController
from sgreen2_pi.solenoid_relay_controller import SolenoidRelayController


class RelayListener:
    """
    A class for Pis that control relay modules. It waits for commands from the greenhouse
    by creating a server socket and accepting connections from the greenhouse.
    """

    def __init__(self, configfile: str):
        """
        The constructor. It sets up the server socket and initializes a FanRelayController
        :param configfile: the file used to be read for configuration
        """
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        self.config = configparser.ConfigParser()
        self.config.read(configfile)

        socket_port = int(self.config["pi"]["socket_port"])

        self.greenhouse_ip = self.config["greenhouse"]["greenhouse_ip"]

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", socket_port))

        fan_pi_pins = dict(fan01=int(self.config["fan"]["fan01_pin"]),
                           fan02=int(self.config["fan"]["fan02_pin"]),
                           fan03=int(self.config["fan"]["fan03_pin"]),
                           fan04=int(self.config["fan"]["fan04_pin"]))

        self.fan_relay_controller = FanRelayController(fan_pi_pins)

        solenoid_pi_pins = dict(master=int(self.config["solenoid"]["master_solenoid_pin"]),
                                solenoid01=int(self.config["solenoid"]["solenoid01_pin"]),
                                solenoid02=int(self.config["solenoid"]["solenoid02_pin"]),
                                solenoid03=int(self.config["solenoid"]["solenoid03_pin"]),
                                solenoid04=int(self.config["solenoid"]["solenoid04_pin"]),
                                solenoid05=int(self.config["solenoid"]["solenoid05_pin"]),
                                solenoid06=int(self.config["solenoid"]["solenoid06_pin"]),
                                solenoid07=int(self.config["solenoid"]["solenoid07_pin"]))

        self.solenoid_relay_controller = SolenoidRelayController(solenoid_pi_pins)

        lights_pi_pins = dict(lights01=int(self.config["lights"]["lights01_pin"]),
                              lights02=int(self.config["lights"]["lights02_pin"]))

        self.lights_relay_controller = LightsRelayController(lights_pi_pins)

    def __del__(self):
        """
        The destructor. Does necessary cleanup such as closing the server socket and Raspberry
        Pi GPIO cleanup
        :return:
        """
        del self.fan_relay_controller
        del self.solenoid_relay_controller
        del self.lights_relay_controller
        self.server_socket.close()
        GPIO.cleanup()

    def run(self):
        """
        Continuously waits for incoming socket connections and sends those client sockets
        to a client thread.
        :return:
        """
        try:
            self.server_socket.listen()

            while True:
                client_socket, address = self.server_socket.accept()
                if address[0] == self.greenhouse_ip:
                    client_thread = _ClientThread(client_socket, self)
                    client_thread.run()

        except KeyboardInterrupt:
            print("Received keyboard interrupt. Stopping...")
        finally:
            del self


class _ClientThread(threading.Thread):
    """
    A threading class to read a message from a client socket and execute
    an action based on the message.
    """

    def __init__(self, client_socket: socket, rl: RelayListener):
        """
        The constructor
        :param client_socket: a client socket
        :param rl: a RelayListener
        """
        threading.Thread.__init__(self)
        self.client_socket = client_socket
        self.relay_listener = rl

    def run(self):
        """
        Runs the client thread. Accepts a message from the client socket and
        determines what action to take. Messages received will be in this
        format:

        ACTUATOR_NAME:[on|off]
        :return: None
        """
        message = self.client_socket.recv(2048).decode()
        print("RECEIVED: " + message)
        name, actuator_type, state = message.split(":")

        relay_controller = None

        if actuator_type == "fan":
            relay_controller = self.relay_listener.fan_relay_controller
        elif actuator_type == "water":
            relay_controller = self.relay_listener.solenoid_relay_controller
        elif actuator_type == "lights":
            relay_controller = self.relay_listener.lights_relay_controller

        if relay_controller is not None:
            if state.lower() == "on":
                relay_controller.turn_on(name)
            elif state.lower() == "off":
                relay_controller.turn_off(name)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: " + sys.argv[0] + " [configfile]")
        exit(1)

    relay_listener = RelayListener(sys.argv[1])
    relay_listener.run()
