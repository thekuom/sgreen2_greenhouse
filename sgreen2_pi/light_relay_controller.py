import RPi.GPIO as GPIO

from sgreen2_pi import _relay_controller


class LightsRelayController(_relay_controller.RelayController):
    def __init__(self, pi_pins: dict):
        _relay_controller.RelayController.__init__(self, pi_pins)

    def turn_on(self, name: str) -> None:
        if name in self.pi_pins:
            GPIO.output(self.pi_pins[name], GPIO.LOW)

    def turn_off(self, name: str) -> None:
        if name in self.pi_pins:
            GPIO.output(self.pi_pins[name], GPIO.HIGH)
