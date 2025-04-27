from flask import Flask, jsonify
import requests
import time
import threading
from loguru import logger
from logging_config import setup_logging
from mikrotik import Mikrotik
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
setup_logging(app)

# Configuration
DJANGO_SERVER_URL = os.getenv('DJANGO_SERVER_URL')
DEVICE_ID = os.getenv('DEVICE_ID', 'default_device')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '30'))

# Initialize Mikrotik connection
router = Mikrotik()

def execute_command(command_data):
    """Execute commands received from Django server"""
    try:
        command_type = command_data.get('type')
        command_params = command_data.get('params', {})

        if command_type == 'add_user':
            username = command_params.get('username')
            password = command_params.get('password')
            time_limit = command_params.get('time_limit')
            if all([username, password, time_limit]):
                router.add_user(username, password, time_limit)
                return {"status": "success", "message": f"User {username} added successfully"}
            else:
                return {"status": "error", "message": "Missing required parameters for add_user"}

        elif command_type == 'login_user':
            mac = command_params.get('mac')
            ip = command_params.get('ip')
            if all([mac, ip]):
                router.login_user(mac, ip)
                return {"status": "success", "message": f"User {mac} logged in successfully"}
            else:
                return {"status": "error", "message": "Missing required parameters for login_user"}

        else:
            return {"status": "error", "message": f"Unknown command type: {command_type}"}

    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return {"status": "error", "message": str(e)}

def report_status(command_id, status_data):
    """Report command execution status back to Django server"""
    try:
        response = requests.post(
            f"{DJANGO_SERVER_URL}report_status/",
            json={
                "device_id": DEVICE_ID,
                "command_id": command_id,
                "status": status_data
            }
        )
        response.raise_for_status()
        logger.info(f"Status reported successfully for command {command_id}")
    except Exception as e:
        logger.error(f"Error reporting status: {str(e)}")

def poll_command():
    """Poll Django server for commands and execute them"""
    while True:
        try:
            # Get commands from Django server
            response = requests.get(
                f"{DJANGO_SERVER_URL}get_commands/",
                params={"device_id": DEVICE_ID}
            )
            response.raise_for_status()
            commands = response.json()

            # Process each command
            for command in commands:
                command_id = command.get('id')
                command_data = command.get('data', {})
                
                logger.info(f"Processing command {command_id}: {command_data}")
                
                # Execute command
                result = execute_command(command_data)
                
                # Report status back to Django
                report_status(command_id, result)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while polling: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in poll_command: {str(e)}")
        
        time.sleep(POLL_INTERVAL)

@app.before_first_request
def start_polling():
    """Start the polling thread when the Flask app starts"""
    logger.info(f"Starting polling thread for device: {DEVICE_ID}")
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
    app.run(host='0.0.0.0', port=5000)
