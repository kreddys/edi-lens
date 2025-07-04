import random
import string

# We no longer need the create_test_tenant helper, as it will be done in the tests.
def random_lower_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))

def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"