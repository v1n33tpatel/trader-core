import time

class RateThrottler:
    def __init__(self, min_interval_seconds: float = 1.2):
        self.min_interval = min_interval_seconds
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
