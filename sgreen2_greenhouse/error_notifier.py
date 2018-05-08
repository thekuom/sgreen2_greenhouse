import threading

from datetime import datetime, timezone
from enum import Enum

from sgreen2_greenhouse.email_client import EmailClient


class ErrorSeverity(Enum):
    """
    Defines the levels of severity for errors
    CRITICAL is used to bypass the stage system
    """
    LOW = 2
    MID = 3
    HIGH = 6
    CRITICAL = 7


class Error:
    """
    A custom error class
    """

    def __init__(self, severity: ErrorSeverity, message: str, error_key):
        """
        The constructor
        :param severity: the severity of the error
        :param message: the message associated with the error
        :param error_key: the key of the error, which can be used to classify error types to prevent duplicates. If
        you want to send all emails, you can randomize the error_key
        """
        self.severity = severity
        self.message = message
        self.error_key = error_key


class ErrorNotifier:
    """
    Handles the logic of when to send emails for errors, duplicate errors, etc.
    """

    def __init__(self, email_client: EmailClient, stages: int):
        """
        The constructor
        :param email_client: The EmailClient used to send emails
        :param stages: How many stages do the errors need to go through to be active (lower = more frequent emails)
        """
        self.email_client = email_client
        self.total_stages = stages

        """
        active_errors = [
            # stage 1 errors
            {
                error_key1: message1,
                error_key2: message2
                ...
            },
            # stage 2 errors
            {
                error_key1: message1
            }
        ]
        
        All the ongoing errors in stages. An error is added to the next stage if it
        appears again. Once the error is resolved, it is eliminated from all stages.
        This is to prevent too many error notifications. Sometimes an error will
        present itself but then immediately resolve. This stage structure is designed
        to prevent that.
        """
        self.active_errors = list()
        for i in range(self.total_stages):
            self.active_errors.append({})

        """
        message_buffer = {
            error_key1: Error,
            ...
        }
        
        All the errors that have not been sent yet. I use this because if I add
        an error that doesn't send and then remove that error, the total_severity
        remains the same, and I could get an unnecessary email
        """
        self.message_buffer = dict()
        self.total_severity = 0

        self.__current_email_thread = None

    def add_error(self, error: Error) -> None:
        """
        Adds an error to the notifier
        :param error: the Error to add
        :return: None
        """

        # add the error to the first available stage
        for stage in range(self.total_stages):
            if error.error_key not in self.active_errors[stage] or error.severity == ErrorSeverity.CRITICAL:
                self.active_errors[stage][error.error_key] = \
                    datetime.now(timezone.utc).astimezone().strftime("%x %X ") + str(error.severity) + ": " + \
                    error.message

                # if the error was inserted into the last stage, add the error to the buffer
                if stage == self.total_stages - 1 or error.severity == ErrorSeverity.CRITICAL:
                    self.total_severity += error.severity.value
                    self.message_buffer[error.error_key] = error

                # as soon as we hit a stage where the error is not, break
                if error.severity != ErrorSeverity.CRITICAL:
                    break

    def remove_error(self, error_key) -> None:
        """
        Removes an error by error_key
        :param error_key: the error key
        :return: None
        """

        for stage in range(self.total_stages):
            self.active_errors[stage].pop(error_key, None)

        if error_key in self.message_buffer:
            self.total_severity -= self.message_buffer[error_key].severity.value
            self.message_buffer.pop(error_key)

    def send_message(self, email_addresses: list, flush: bool = False) -> None:
        """
        Asynchronously send an email with the error report if the errors
        :param email_addresses: a list of email addresses to send to
        :param flush: bypass total severity check
        :return: None
        """
        if self.__current_email_thread:
            self.__current_email_thread.join()
            self.__current_email_thread = None

        if self.total_severity >= ErrorSeverity.HIGH.value or (flush and self.total_severity > 0):
            self.total_severity = 0
            self.message_buffer.clear()

            subject = "sGreen Errors"

            # only get final stage errors
            message = "\n\n".join(list(self.active_errors[self.total_stages - 1].values()))

            self.__current_email_thread = threading.Thread(target=self.email_client.send_message,
                                                           args=(subject, message, email_addresses))
            self.__current_email_thread.start()

    def quit(self):
        if self.__current_email_thread:
            self.__current_email_thread.join()
