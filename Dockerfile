# Use the specified Python image as the base
FROM python:3.12.5

# Set the working directory inside the container
WORKDIR /app

# Copy the source code and dependencies into the container
COPY ./src ./src
COPY ./app.py ./app.py
COPY ./requirements.txt ./requirements.txt

# Download and run the custom installation script for 'uv'
ADD https://astral.sh/uv/install.sh /install.sh

# Make the installation script executable and run it
RUN chmod 755 /install.sh && /install.sh && echo "uv installation completed" && ls -l /root/.local/bin/

# Add '/root/.local/bin' to the PATH
ENV PATH="/root/.local/bin:${PATH}"

# Install Python dependencies using 'uv'
RUN /root/.local/bin/uv pip install --no-cache-dir --system -r requirements.txt

# Command to run the application
CMD ["python", "app.py"]
