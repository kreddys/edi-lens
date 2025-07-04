import time
from typing import Dict, Any
from jose import jwt

# --- PASTE YOUR GENERATED KEYS HERE ---
# This is our static private key for signing test JWTs
TEST_PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCwbYHY0Vk2+cpg
hYD0dje5VYwYdkhJcdJloK6DjJlCy0iwpnubTHDNcM9Jn8l/+TUFP5qByof9Gd59
xxyUjHAvhwe59RzwQXrWgQTgWeydMf8MbzRpT32Ie1pc6kjXsyN+d2gEueLqXSWt
33s+g94+QpG8Ga6KW42Y7FIpmPt2+VZ5G56jNOWotzySeAmLHdc4AVYtrQUvxcMw
4LpLuom+J4pI4fRGa2NIY+VBAYru8lsn9BsB/VwgaAwXlXrjPgLYFvHSr93LGEyR
zTZ5vLUL3i7y+QBdm4BCniQz77XOeMJdjsxrNDZDxXFqGnB1grARRLluk22cBvOz
FD2sJGtFAgMBAAECggEAH7tOaZv7nxDtxo70euOBUb7yb9rkVPtZE2jDQotI7HPK
CuWioTOuLTEfQzdvQypkECHYrQPrkgjzVK15dTlOGyo+6EIO9qJcUNTLNvvNfBdo
L0kYBOHkauX+wmvr9om0dlRNG96AEtV2h6+Eh+GpWQrZkdqPozhkvw6wF2W5wrO4
j2xf0GubZjjs/z18jTMcgaXfHbux48lVYlsSNfS3SG0NCQtZgVnGjrEGyZAL9J9n
fd5dObk1zSkN7j56bzR+GpnYHyfq2MkfXLOMzvVerIJMLL8c3DDEI5HW8Y588kTX
7uycTi48l/QrdekLjLywgTihGg3ipLUKdUwcbHMeMQKBgQDnr3yIlbENEKLynEvi
+jCp1yVyGF9GOevzMmyRdJj6kMh989W1V3vDCu2GYFER810K2Z3X9EYIj+Hsi1uq
W5vqLIf8jEgD2bAHAXoghUjvEyCHKDmjdM3EdTwy9ZfFonaRcUzVCdkTkbqPGZG/
xFSjvAZGzMIK5K5uwCDLxEsFMQKBgQDC8XRRRyFTFYG3t5+2l8v7TnHE6kGsW+Ut
p+KfiqVeTstG8rQ960lj14wLx/5kbvh7lxojUjTY5uVHxOblNQjKW2hp+/LjDgyR
bg4K9bPd6G5TNtbOPBipCSWISqz0aCa9Hr25OhEIKY74v3ioUERrFNRpYEcNL+wX
lvHotDJSVQKBgEhBc45JWRFhCeCuHACq1Hhzj8sYjMYjFFIhfLiUa41hkBWv8QuA
QCnhA5jv+vilNHRI0DBkj17mOKiEAc+MiICs6LA7s833my1kKYlw6AEfrvpX8jnn
GLFXerHN5EqP03iipDqguqGexlcQu2LaQSdbYX29KBsrnLcPlmrWSitRAoGAJgJB
9Z7yxmpJEnMA9u793I/c6tHp4BtCwfYb35N+zrZ6N+kWb4QymP7r1Vg3J4njdOVv
OTfMCgZq6eVgR4xhnGLaJt/y6YZRuQFGR6jEWx34dM0acLeS71JTORGmSzkLZJBb
2YOS0o6Xy7Q5aEfOLzqud6VH9TBEzgymOgL4VMkCgYEAqhvT8JIe9tFfnVVUSvZx
SlDPoMlwASZt+mYerjMiAIZCDLOLTb03yIBJlc5ZYO1x8cqy03XAdKsw3uOMja2V
BdrOeA10cjl770HtqhymqqTlgljqDdDw0OyuNtkPNzKhqh45vG3PLCVcE8DgvkN6
OuryrAusyY88sKWinzaMkUE=
-----END PRIVATE KEY-----
"""

# This is the corresponding public key our mock will return
TEST_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsG2B2NFZNvnKYIWA9HY3
uVWMGHZISXHSZaCug4yZQstIsKZ7m0xwzXDPSZ/Jf/k1BT+agcqH/RnefccclIxw
L4cHufUc8EF61oEE4FnsnTH/DG80aU99iHtaXOpI17MjfndoBLni6l0lrd97PoPe
PkKRvBmuiluNmOxSKZj7dvlWeRueozTlqLc8kngJix3XOAFWLa0FL8XDMOC6S7qJ
vieKSOH0RmtjSGPlQQGK7vJbJ/QbAf1cIGgMF5V64z4C2Bbx0q/dyxhMkc02eby1
C94u8vkAXZuAQp4kM++1znjCXY7MazQ2Q8VxahpwdYKwEUS5bpNtnAbzsxQ9rCRr
RQIDAQAB
-----END PUBLIC KEY-----
"""

# This is the public key formatted as a dictionary, similar to how
# Keycloak's JWKS endpoint would provide it. This is what our mock will actually return.
TEST_PUBLIC_KEY_DICT = {
    "kty": "RSA",
    "use": "sig",
    "kid": "test-key-id",
    "alg": "RS256",
    # This part can be generated from the PEM, but for simplicity, we'll
    # assume the jose library can handle the full public key dict. We'll
    # adjust if needed. For now, we will pass the PEM string directly.
}


def forge_jwt(
    payload_override: Dict[str, Any],
    client_id: str = "fastapi-client",
    expires_in: int = 300,
) -> str:
    """Creates a signed JWT for testing purposes."""
    now = int(time.time())
    
    payload = {
        "exp": now + expires_in,
        "iat": now,
        "iss": "http://localhost:8080/realms/test-realm",
        "aud": client_id,
        "sub": "test-user-id",
        "preferred_username": "testuser",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User",
        "realm_access": {
            "roles": ["test_role", "offline_access"]
        }
    }
    
    payload.update(payload_override)
    
    # --- ADD THIS LOGIC ---
    # If an override value is None, remove the key from the payload entirely.
    keys_to_delete = [key for key, value in payload.items() if value is None]
    for key in keys_to_delete:
        del payload[key]
    
    token = jwt.encode(
        claims=payload,
        key=TEST_PRIVATE_KEY,
        algorithm="RS256",
        headers={"kid": "test-key-id"}
    )
    
    return token