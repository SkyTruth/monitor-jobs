from src.utils.db import read_test_subscriptions

print("I'm running!")
subs = read_test_subscriptions("ethan@skytruth.org")
print(subs)
