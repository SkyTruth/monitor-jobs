from src.utils.db import read_test_subscriptions
import sys

last_arg = ""
test_email = None
for arg in sys.argv:
    if last_arg == "-test":
        test_email = arg
    last_arg = arg
print("test email is ", test_email)
print("I'm running!")
subs = read_test_subscriptions(test_email)
print(subs)
