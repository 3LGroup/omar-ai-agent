import logging
import os

# Create a logger
logger = logging.getLogger("UFD-Logger")
logger.setLevel(logging.DEBUG)  # This could be more dynamic based on your needs

os.makedirs("logs", exist_ok=True)
# Create handlers: one for the regular logs and one for the error logs
file_handler = logging.FileHandler("logs/running_logs.log")
file_handler.setLevel(logging.INFO)

error_file_handler = logging.FileHandler("logs/error_logs.log")
error_file_handler.setLevel(logging.ERROR)

# Create console handler
console_handler = logging.StreamHandler()  # Console handler
# console_handler.setLevel(logging.DEBUG)  # Console handler level

# Create formatters and add them to the handlers
formatter = logging.Formatter("%(asctime)s - p%(process)s - {%(pathname)s:%(lineno)d} - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
error_file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)  # Setting formatter to console handler

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(error_file_handler)
logger.addHandler(console_handler)  # Add console handler to logger
