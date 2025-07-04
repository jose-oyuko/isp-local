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
        """
        Remove any active hotspot session associated with the given MAC address.
        
        Args:
            mac (str): The MAC address (e.g., '6A:7C:66:16:85:ED').
        
        Returns:
            bool: True if session was removed or none existed, False if removal failed.
        """
        logger.info(f"Attempting to remove active sessions for MAC: {mac}")
        try:
            api = self.get_mt_api()
            # Query all active sessions and filter by mac-address
            active_sessions = api.get_resource('/ip/hotspot/active').get()
            logger.debug(f"All active sessions: {active_sessions}")
            matching_sessions = [s for s in active_sessions if s.get('mac-address', '').lower() == mac.lower()]
            logger.debug(f"Matching sessions for MAC {mac}: {matching_sessions}")

            if not matching_sessions:
                logger.info(f"No active sessions found for MAC: {mac}")
                return True
            
            for session in matching_sessions:
                session_id = session.get('id')
                if session_id:
                    logger.info(f"Removing active session for MAC: {mac}, Session ID: {session_id}")
                    api.get_resource('/ip/hotspot/active').call('remove', {'id': session_id})
                    logger.success(f"Successfully removed session ID: {session_id}")
                else:
                    logger.warning(f"Session for MAC {mac} has no ID, skipping removal")
            return True
        except routeros_api.exceptions.RouterOsApiCommunicationError as e:
            logger.error(f"Failed to remove active session for MAC {mac}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error removing active session for MAC {mac}: {str(e)}")
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
    
    def remove_existing_user(self, username):
        """
        Remove an existing user if they exist.
        
        Args:
            username (str): The username to remove.
        
        Returns:
            bool: True if user was removed, False if user did not exist.
        """
        logger.info(f"Attempting to remove existing user - Username: {username}")
        try:
            api = self.get_mt_api()
            user_resource = api.get_resource('/ip/hotspot/user')
            existing_users = user_resource.get(name=username)
            logger.debug(f"Existing users found: {existing_users}")
            if existing_users:
                user_resource.call('remove', {'numbers': existing_users[0]['id']})
                logger.success(f"Successfully removed user: {username}")
                return True
            logger.info(f"No existing user found to remove - Username: {username}")
            return False
        except Exception as e:
            logger.error(f"Failed to remove existing user - Username: {username}. Error: {str(e)}")
            raise

    def disconect_active_hotspot_user(self, username):
        """
        Disconnect an active hotspot user by username.
        
        Args:
            username (str): The username of the user to disconnect.
        
        Returns:
            bool: True if user was disconnected, False if user did not exist or was not active.
        """
        logger.info(f"Attempting to disconnect active hotspot user - Username: {username}")
        try:
            api = self.get_mt_api()
            active_users = api.get_resource('/ip/hotspot/active').get(user=username)
            logger.debug(f"Active users found: {active_users}")
            if active_users:
                for user in active_users:
                    api.get_resource('/ip/hotspot/active').call('remove', {'id': user['id']})
                logger.success(f"Successfully disconnected user: {username}")
                return True
            logger.info(f"No active user found to disconnect - Username: {username}")
            return False
        except Exception as e:
            logger.error(f"Failed to disconnect active hotspot user - Username: {username}. Error: {str(e)}")
            raise

    def user_exists(self, username):
        logger.debug(f"Checking if user exists - Username: {username}")
        try:
            api = self.get_mt_api()
            user_resource = api.get_resource('/ip/hotspot/user')
            existing_users = user_resource.get(name=username)
            logger.debug(f"Existing users found: {existing_users}")
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
            self.remove_existing_user(username)  # Ensure no existing user with same name
            
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

    def login_user(self, mac, ip=None):
        """
        Log in a user to the hotspot using their MAC address.
        
        Args:
            mac (str): The MAC address (e.g., '6A:7C:66:16:85:ED').
            IP (str): Optional. IP address to use for login. If None, queries /ip/hotspot/host.
        
        Returns:
            bool: True if login succeeds.
        
        Raises:
            Exception: If login fails.
        """
        logger.info(f"Attempting to login user - MAC: {mac}")
        try:
            # Remove any existing session
            if not self.remove_active_session_by_mac(mac):
                logger.warning(f"Proceeding with login for MAC {mac} despite session removal failure")

            api = self.get_mt_api()
            # Query host list for IP
            active_hosts = api.get_resource('/ip/hotspot/host').get()
            matching_hosts = [h for h in active_hosts if h.get('mac-address', '').lower() == mac.lower()]
            logger.debug(f"Host list for MAC: {mac}: {matching_hosts}")

            if not matching_hosts:
                logger.error(f"Could not find host entry for MAC {mac}, cannot login user")
                raise Exception(f"Host entry not found for MAC {mac}")

            # Use to-address if available, else address
            host = matching_hosts[0]
            login_ip = str(host.get('to-address', host.get('address', '')))
            if not login_ip:
                logger.error(f"No valid IP found for MAC {mac} in host entry: {host}")
                raise Exception(f"No valid IP found for MAC {mac}")
            logger.debug(f"Using IP {login_ip} for login based on host entry for MAC {mac}")

            # # Verify user exists
            # if not self.user_exists(mac):
            #     logger.warning(f"User {mac} not found, attempting to add")
                # self.add_user(mac, mac, '4h')  # Default 4h limit, adjust as per your logic

            api.get_resource('/ip/hotspot/active').call('login', {
                'user': mac,
                'password': mac,
                'mac-address': mac,
                'ip': login_ip
            })
            logger.success(f"User successfully logged in in - MAC {mac}, IP: {login_ip}")
            return True
        except Exception as e:
            error_message = str(e).lower()
            if "your uptime limit reached" in error_message:
                logger.warning(f"User uptime limit reached - MAC: {mac}, IP: {login_ip}")
                raise self.ReAddUserError("Readd user")
            elif "no such user" in error_message:
                logger.warning(f"User not found on on router - - MAC: {mac}, IP: {login_ip}")
                raise Exception(f"User not found: {mac}")
            elif "connection refused" in error_message:
                logger.error(f"Router connection refused - - MAC: {mac}, IP: {error_message}")
                raise
            elif "unknown host" in error_message:
                logger.error(f"Unknown host IP {login_ip} for MAC {mac}: {error_message}")
                raise Exception(f"Unknown host IP: {login_ip}")
            else:
                logger.error(f"Login failed - - MAC: {mac}, IP: {login_ip}, Error: {error_message}")
                raise

# router = Mikrotik()
# router.remove_active_session_by_ip("192.168.78.253")