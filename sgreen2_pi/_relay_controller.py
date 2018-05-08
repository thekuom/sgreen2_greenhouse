import RPi.GPIO as GPIO


class RelayController(object):
    """
    A base class for relay controllers
    """

    def __init__(self, pi_pins: dict, *args, **kwargs):
        """
        Constructor. Sets up the specified pins as output pins and turns them
        off
        :param pi_pins: the dictionary of actuator name and pin numbers
        :param kwargs: additional arguments if overriding the constructor
        """
        self.pi_pins = pi_pins
        for name, channel in self.pi_pins.items():
            GPIO.setup(channel, GPIO.OUT)
            self.turn_off(name)

    def __del__(self, *args, **kwargs):  # real signature unknown
        for name, channel in self.pi_pins.items():
            self.turn_off(name)

    def turn_on(self, name: str) -> None:
        """
        Turns on the actuator specified by name
        :param name: the name of the actuator to turn on
        :return: None
        """
        pass

    def turn_off(self, name: str) -> None:
        """
        Turns off the actuator specified by name
        :param name: the name of the actuator to turn on
        :return: None
        """
        pass
