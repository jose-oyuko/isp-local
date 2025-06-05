import routeros_api
import os
import re
from datetime import timedelta
from dotenv import load_dotenv
from loguru import logger
import routeros_api.exceptions

# Load environment variables
load_dotenv()

class MikrotikConfigError(Exception):
    """Custom exception for Mikrotik configuration errors"""
    pass

class Mikrotik:
    class ReAddUserError(Exception):
        pass

    def __init__(self):
        self._validate_config()
        self.mikrotik_ip = os.getenv('MIKROTIK_IP')
        self.mikrotik_user = os.getenv('MIKROTIK_USER')
        self.mikrotik_pass = os.getenv('MIKROTIK_PASS')

    def _validate_config(self):
        """Validate Mikrotik configuration settings"""
        required_settings = ['MIKROTIK_IP', 'MIKROTIK_USER', 'MIKROTIK_PASS']
        missing_settings = [setting for setting in required_settings 
                           if not os.getenv(setting)]
        if missing_settings:
            raise MikrotikConfigError(f"Missing required Mikrotik settings: {', '.join(missing_settings)}")
        logger.debug("Mikrotik configuration validated successfully")

    def remove_active_session_by_mac(self, mac):
        logger.info(f"Attempting to remove active sessions for MAC: {mac}")
        try:
            api = self.get_mt_api()
            active_sessions = api.get_resource('/ip/hotspot/active').get(mac_address=mac)
            logger.debug(f"active sessions found for MAC {mac}: {active_sessions}")
            if not active_sessions:
                logger.info(f"No active sessionns found for MAC: {mac}")
                return True
            
            for session in active_sessions:
                session_id = session.get('id')
                if session_id:
                    logger.info(f"Removing active session for MAC: {mac}, sessions ID: {session_id}")
                    api.get_resource('/ip/hotspot/active').call('remove', {'id': session_id})
                    logger.success(f"Successfully removed active sessions for MAC: {mac}")
                else:
                    logger.warning(f"Session ID not found for MAC: {mac}, skipping removal")
            return True
        except routeros_api.exceptions.RouterOsApiCommunicationError as e:
            logger.error(f"Failed to remove active session for MAC {mac}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"An error occurred while removing active session for MAC {mac}: {str(e)}")
            return False

    def remove_active_session_by_ip(self, ip):
        logger.info(f"Attempting to remove active session for IP: {ip}")
        try:
            api = self.get_mt_api()
            active_sessions = api.get_resource('/ip/hotspot/active').get(address=ip)
            logger.debug(f"Active sessions found for IP {ip}: {active_sessions}")
            if not active_sessions:
                logger.info(f"No active sessions found for IP: {ip}")
                return True
            
            # remove each session
            for session in active_sessions:
                session_id = session.get('id')
                if session_id:
                    logger.info(f"Removing active session for IP: {ip}, Session ID: {session_id}")
                    api.get_resource('/ip/hotspot/active').call('remove', {'id': session_id})
                    logger.success(f"Successfully removed active sessions for IP: {ip}")
                else:
                    logger.warning(f"Session ID not found for IP: {ip}, skipping removal")
            return True
        except routeros_api.exceptions.RouterOsApiCommunicationError as e:
            logger.error(f"Failed to remove active session for IP {ip}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"An error occurred while removing active session for IP {ip}: {str(e)}")
            return False

    def get_mt_api(self):
        logger.debug(f"Attempting to connect to Mikrotik router at {self.mikrotik_ip}")
        try:
            api_pool = routeros_api.RouterOsApiPool(
                self.mikrotik_ip,
                username=self.mikrotik_user,
                password=self.mikrotik_pass,
                plaintext_login=True
            )
            api = api_pool.get_api()
            logger.success(f"Successfully connected to Mikrotik router at {self.mikrotik_ip}")
            return api
        except Exception as e:
            logger.error(f"Failed to connect to Mikrotik router at {self.mikrotik_ip}. Error: {str(e)}")
            raise

    def _parse_mikrotik_time(self, time_str):
        """Convert MikroTik time string (e.g., '2h30m') to seconds"""
        if time_str == '0s':
            return 0
        total_seconds = 0
        time_units = {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}
        matches = re.findall(r'(\d+)([wdhms])', time_str)
        for num, unit in matches:
            total_seconds += int(num) * time_units[unit]
        return total_seconds

    def user_exists(self, username):
        logger.debug(f"Checking if user exists - Username: {username}")
        try:
            api = self.get_mt_api()
            user_resource = api.get_resource('/ip/hotspot/user')
            existing_users = user_resource.get(name=username)
            if existing_users:
                user_details = existing_users[0]  # First matching user
                uptime = self._parse_mikrotik_time(user_details.get('uptime', '0s'))
                limit_uptime = self._parse_mikrotik_time(user_details.get('limit-uptime', '0s'))
                if limit_uptime != 0 and uptime >= limit_uptime:
                    user_resource.call('remove', {'numbers': user_details['id']})
                    logger.info(f"Removed expired user: {username} (uptime: {uptime}s, limit: {limit_uptime}s)")
                    return False
                logger.debug(f"User exists - Username: {username}")
                return True
            logger.debug(f"User does not exist - Username: {username}")
            return False
        except Exception as e:
            logger.error(f"Failed to check user existence - Username: {username}. Error: {str(e)}")
            raise

    def add_user(self, username, password, time):
        logger.info(f"Attempting to add user - Username: {username}, Time limit: {time}")
        try:
            if self.user_exists(username):
                logger.info(f"User already exists and is not expired - Username: {username}")
                return
            
            api = self.get_mt_api()
            api.get_resource('/ip/hotspot/user').call('add', {
                'name': username,
                'password': password,
                'profile': 'default',
                'limit-uptime': time,
            })
            logger.success(f"User successfully added - Username: {username}, Time limit: {time}")
        except Exception as e:
            logger.error(f"Failed to add user - Username: {username}. Error: {str(e)}")
            raise

    def login_user(self, mac, ip):
        # change to login by ip only to solve reassignment of ip issues
        logger.info(f"Attempting to login user - MAC: {mac},")
        try:
            # if not self.remove_active_session_by_ip(ip):
            if not self.remove_active_session_by_mac(mac):
                logger.warning(f"Proceeding with login for MAC {mac} and {ip} despite session removal failure")
        
            api = self.get_mt_api()
            active_list = api.get_resource('/ip/hotspot/host').get(mac_address=mac)
            logger.debug(f"Host list entry for mac {mac}: {active_list}")
            if not active_list:
                logger.error(f"could not find host entry for mac {mac}, cannot login user")
                raise Exception(f"Host entry not found for MAC {mac}")
            
            ip = active_list[0]['address']
            logger.debug(f"Using IP {ip} for login based on active session for MAC {mac}")
            api.get_resource('/ip/hotspot/active').call('login', {
                'user': mac,
                'password': mac,
                'mac-address': mac,
                'ip': ip
            })
            logger.success(f"User successfully logged in - MAC: {mac}, IP: {ip}")
            return True
        except Exception as e:
            error_message = str(e)
            if "your uptime limit is reached" in error_message.lower():
                logger.warning(f"User uptime limit reached - MAC: {mac}, IP: {ip}")
                raise Mikrotik.ReAddUserError(f"Readd user")
            elif "no such user" in error_message.lower():
                logger.warning(f"User not found on router - MAC: {mac}, IP: {ip}")
            elif "connection refused" in error_message.lower():
                logger.error(f"Router connection refused - MAC: {mac}, IP: {ip}")
            else:
                logger.error(f"Login failed - MAC: {mac}, IP: {ip}, Error: {error_message}")
            raise

# router = Mikrotik()
# router.remove_active_session_by_ip("192.168.78.253")