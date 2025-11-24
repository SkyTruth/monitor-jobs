from src.utils import config
from src.utils.db import read_test_subscriptions

print(config.DB_HOST)
print(config.ENVIRONMENT)
test_email = "ethan@skytruth.org"
subs = read_test_subscriptions(test_email)
print(subs[0][1])
print("I'm running!")
