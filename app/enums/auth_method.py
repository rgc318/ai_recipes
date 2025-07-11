from enum import Enum

class AuthMethod(str, Enum):
    app = "app"
    oauth = "oauth"
    sms = "sms"
