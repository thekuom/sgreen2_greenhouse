import RPi.GPIO as GPIO

from sgreen2_pi import _relay_controller


class FanRelayController(_relay_controller.RelayController):
    """
    A class for controlling the small fans in the greenhouse
    """

    def __init__(self, pi_pins: dict):
        """
        The constructor
        :param pi_pins: a dictionary of (fan names: pin number)
        """
        _relay_controller.RelayController.__init__(self, pi_pins)

    def turn_on(self, name: str) -> None:
        """
        Turns on a fan
        :param name: the name of the fan
        :return: None
        """
        if name in self.pi_pins:
            GPIO.output(self.pi_pins[name], GPIO.LOW)

    def turn_off(self, name: str) -> None:
        """
        Turns off a fan
        :param name: the name of the fan
        :return: None
        """
        if name in self.pi_pins:
            GPIO.output(self.pi_pins[name], GPIO.HIGH)
