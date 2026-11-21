import smtplib
import ssl
from email.message import EmailMessage
from libraries.util import LoggerSH
import keyring


class Email:
    def __init__(self, username, from_user, password=None):
        print(f"Init: {self.__class__.__name__}")
        self.__log_err = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.username = username
        self.__password = password
        self.from_user = from_user

    def send(self, to, subject, body):
        message = EmailMessage()
        message["From"] = self.from_user
        message["To"] = to
        message["Subject"] = subject

        html_body = '<html><body><font face="Courier New"><div><PRE>{}</PRE></div></font></body></html>'.format(
            body.replace("\n", "<br>"))
        message.set_content(html_body, subtype='html')

        # Create secure connection with server and send email
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(self.username,
                             self.__password if self.__password else keyring.get_password('gmail', self.username))
                server.send_message(message)
        except Exception as err:
            error_message = f"{Exception=}, {err=}"
            self.__log_err.log_message(error_message)
        return


def main():
    email = Email("stockchecker69@gmail.com", "Smart Stef")
    email.send("stephanetrudelle@videotron.ca", "Test email", "Email From python class Email")


if __name__ == '__main__':
    main()
