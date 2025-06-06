from flask import Flask, jsonify
import requests, sys, signal
import time
import threading
from loguru import logger
from logging_config import setup_logging
from mikrotik import Mikrotik
import json
import os
from dotenv import load_dotenv
import traceback

# Load environment variables
load_dotenv()

app = Flask(__name__)
setup_logging(app)

# Configuration
DJANGO_SERVER_URL = os.getenv('DJANGO_SERVER_URL')
DEVICE_ID = os.getenv('DEVICE_ID', 'default_device')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '3'))
DJANGO_USERNAME = os.getenv('DJANGO_USERNAME')
DJANGO_PASSWORD = os.getenv('DJANGO_PASSWORD')

# Initialize Mikrotik connection
router = Mikrotik()

def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def execute_command(command_data):
    """Execute commands received from Django server"""
    try:
        command_type = command_data.get('type')
        command_params = command_data.get('params', {})

        if command_type == 'add_user':
            logger.debug(f"Adding user with params: {command_params}")
            # return
            username = command_params.get('username')
            password = command_params.get('password')
            time_limit = command_params.get('time')
            if all([username, password, time_limit]):

                router=Mikrotik()
                router.add_user(username, password, time_limit)
                logger.info(f"User {username} added successfully")  
                return {"status": "success", "message": f"User {username} added successfully"}
            else:
                return {"status": "error", "message": "Missing required parameters for add_user"}

        elif command_type == 'login_user':
            print("in login user command")
            mac = command_params.get('mac')
            ip = command_params.get('ip')
            time = command_params.get('time')
            if all([mac, ip]):
                logger.info(f"Logging in user with MAC: {mac}, IP: {ip}")
                # return
                # router.login_user(mac, ip)
                router = Mikrotik()
                try:
                    router.login_user(mac=mac, ip=ip)
                except Mikrotik.ReAddUserError:
                    logger.warning(f"User {mac} already exists, re-adding user")
                    router.add_user(username=mac, password=mac, time=time)
                    router.login_user(mac=mac, ip=ip)
                logger.info(f"User {mac} logged in successfully")
               
                return {"status": "success", "message": f"User {mac} logged in successfully"}
            else:
                return {"status": "error", "message": "Missing required parameters for login_user"}

        else:
            return {"status": "error", "message": f"Unknown command type: {command_type}"}

    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

def report_status(command_id, status_data):
    """Report command execution status back to Django server"""
    try:
        response = requests.post(
            f"{DJANGO_SERVER_URL}api/commands/status/",
            json={
                "command_id": command_id,
                "status": status_data
            },
            auth=(DJANGO_USERNAME, DJANGO_PASSWORD)
        )
        response.raise_for_status()
        logger.info(f"Status reported successfully for command {command_id}")
    except Exception as e:
        logger.error(f"Error reporting status: {str(e)}")

def poll_command():
    """Poll Django server for commands and execute them"""
    logger.info("polling thread started")
    if not DJANGO_SERVER_URL or not DJANGO_USERNAME or not DJANGO_PASSWORD:
        logger.error("Django server URL, username, or password not set. Exiting polling thread.")
        return
    while True:
        try:
            # Get commands from Django server
            response = requests.get(
                f"{DJANGO_SERVER_URL}api/commands/", auth=(DJANGO_USERNAME, DJANGO_PASSWORD)
            )
            response.raise_for_status()
            commands = response.json()
            commands = commands.get('commands', [])
            logger.debug(f"Received commands: {commands}")

            # Process each command
            if isinstance(commands, list):  # Check if response is a list

                # Sort the list by 'id'
                commands = sorted(commands, key=lambda x: x.get('id', 0))
                for command in commands:
                    command_id = command.get('id')
                    command_data = command.get('data', {})
                    
                    logger.info(f"Processing command {command_id}: {command_data}")
                    
                    # Execute command
                    result = execute_command(command_data)
                    
                    # Report status back to Django
                    report_status(command_id, result)
            else:
                logger.warning(f"Unexpected response format: {commands}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while polling: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in poll_command: {str(e)}")
        
        time.sleep(POLL_INTERVAL)

# Start the polling thread when the app is created
thread = threading.Thread(target=poll_command)
thread.daemon = True
thread.start()

@app.route('/status', methods=['GET'])
def status():
    """Endpoint to check if the service is running"""
    logger.debug("Status endpoint accessed")
    return jsonify({
        "status": "running",
        "device_id": DEVICE_ID,
        "last_poll": time.time()
    })

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(host='0.0.0.0', port=5000,use_reloader=False)
