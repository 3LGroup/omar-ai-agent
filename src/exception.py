"""
It contains all the code related to exceptions
"""

import sys


def error_message_details(error, error_detail: sys):
    _, _, exc_tb = error_detail.exc_info()
    file_name = exc_tb.tb_frame.f_code.co_filename
    return "Error occured in Python Script name [{0}] Line Number [{1}] Error Message[{2}]".format(
        file_name, exc_tb.tb_lineno, str(error)
    )


# creating custom exception class


class CustomException(Exception):
    def __init__(self, error_message, error_detail: sys) -> None:
        super().__init__(error_message)
        self.error_message = error_message_details(
            error=error_message, error_detail=error_detail
        )

    # returns string error message
    def __str__(self) -> str:
        return self.error_message
