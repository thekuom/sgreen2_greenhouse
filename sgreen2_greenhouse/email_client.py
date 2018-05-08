import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List


class EmailClient:
    """
    An email client used to send emails. Basically an SMTP client wrapper
    """

    def __init__(self, smtp_server: str, port: int, username: str, password: str):
        """
        The constructor
        :param smtp_server: the smtp server to use
        :param port: the port to use
        :param username: the username to login with
        :param password: the password for the login
        """
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password

    def send_message(self, subject: str, message: str, to_list: List[str]) -> None:
        """
        Sends a message to a list of email addresses
        :param subject: the subject of the email
        :param message: the message to send
        :param to_list: a list of email addresses
        :return: None
        """
        smtp_client = smtplib.SMTP(host=self.smtp_server, port=self.port)

        smtp_client.starttls()
        smtp_client.login(self.username, self.password)

        for recipient in to_list:
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = recipient
            msg["Subject"] = subject

            msg.attach(MIMEText(message, "plain"))
            smtp_client.send_message(msg)
            del msg

        smtp_client.quit()
