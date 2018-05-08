import RPi.GPIO as GPIO

from sgreen2_pi import _relay_controller


class SolenoidRelayController(_relay_controller.RelayController):
    """
    A class for controlling the solenoids in the greenhouse
    """

    def __init__(self, pi_pins: dict):
        """
        The constructor
        :param pi_pins: a dictionary of (solenoid names: pin number)
        """
        self.solenoid_state = dict()
        for solenoid in pi_pins:
            self.solenoid_state[solenoid] = False

        # keep the state of the solenoids so that we can turn the master off if all the others are off
        if "master" not in pi_pins:
            raise Exception("Master solenoid required for solenoid relay controller")

        _relay_controller.RelayController.__init__(self, pi_pins)

    def all_solenoids_off(self) -> bool:
        """
        Checks if all the non-master solenoids are off
        :return: whether all the non-master solenoids are off
        """
        for solenoid in self.solenoid_state:
            if solenoid != "master" and self.solenoid_state[solenoid]:
                return False

        return True

    def turn_on(self, name: str) -> None:
        """
        Turns on a solenoid
        :param name: the name of the solenoid
        :return: None
        """
        if name in self.pi_pins:
            GPIO.output(self.pi_pins["master"], GPIO.LOW)
            GPIO.output(self.pi_pins[name], GPIO.LOW)
            self.solenoid_state["master"] = True
            self.solenoid_state[name] = True

    def turn_off(self, name: str) -> None:
        """
        Turns off a solenoid
        :param name: the name of the solenoid
        :return: None
        """
        if name in self.pi_pins:
            GPIO.output(self.pi_pins[name], GPIO.HIGH)
            self.solenoid_state[name] = False

        if self.all_solenoids_off():
            GPIO.output(self.pi_pins["master"], GPIO.HIGH)
            self.solenoid_state["master"] = False
