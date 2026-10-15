import requests

class KrakenBroker:
    def __init__(self, is_demo=False):
        self.is_demo = is_demo

    def get_portfolio(self):
        # Public fallback query for active demo/monitoring balances
        return 0.0, []
