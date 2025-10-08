from enum import Enum

class AuthType(Enum):
    '''
    Respresents Auth Types
    '''
    S3 = "s3",
    NO_AUTH = "none"
