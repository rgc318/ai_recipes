# app/domain/events.py

class DomainEvent:
    def __init__(self, name: str, payload: dict):
        self.name = name
        self.payload = payload
