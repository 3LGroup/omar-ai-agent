### How to Run

1. python -m venv .venv
2. .venv\Scripts\activate
3. In another terminal run 
    ``` ngrok http 8000 ````
4. Update the ngrok url in the .env file
5. python app.py
6. Update the new url in the retell dashboard


### Steps to Run Local
1. Run Ngrok in separate terminal using command "ngrok http 8000"
2. Copy the url provided by Ngrok, in Retell Agents (Outbound-Reschedule-Local, Local Web Server)
3. Replace the NGROK_IP_ADDRESS url in .env with ngrok address
4. In the __init__.py file in src folder, uncomment the phone numbers for local, while comment it for 
Azure.
5. In the twilio_client file uncomment self.url to use ngrok ip address and comment azure one
6. In the outbound_router file uncomment local agent id and comment production agent id.
7. In another terminal run python app.py


### Docker Build
1. docker build -t ufd:latest .
2. 
## Contributing

Ashley Alex Jacob

## License

This project is not licenced yet.
