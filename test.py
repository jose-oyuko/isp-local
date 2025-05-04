from mikrotik import Mikrotik
from app import execute_command
def login_test(mac, ip):
    router = Mikrotik()
    try:
        router.get_mt_api()
        print("Login test passed")
        try:
            router.login_user(mac=mac, ip=ip)
            print(f"User {mac} logged in successfully")
        except Exception as e:
            print(f"Login test failed: {e}")
    except Exception as e:
        print(f"Login test failed: {e}")


def add_user_test(username, password, time):
    router = Mikrotik() 
    try:
        router.get_mt_api()
        router.add_user(username=username, password=password, time=time)
        print(f"User {username} added successfully")
    except Exception as e:
        print(f"Add user test failed: {e}")

# add_user_test(username='2E:9C:65:AF:6D:F5', password='2E:9C:65:AF:6D:F5',time='5m')
# login_test(mac='2E:9C:65:AF:6D:F5', ip='192.168.78.254')
login_user_data = {
    "type":"login_user",
    "params": {
        "mac":"2E:9C:65:AF:6D:F5",
        "ip":"192.168.78.254",
        "time": "5m"
    }
}
add_user_data = {
    "type":"add_user",
    "params": {
        "username":"2E:9C:65:AF:6D:F5",
        "password":"2E:9C:65:AF:6D:F5",
        "time_limit": "5m"
    }
}
execute_command(login_user_data)