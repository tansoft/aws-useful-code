from abc import ABC, abstractmethod

class CloudProvider(ABC):
    @abstractmethod
    def get_price(self, resource_type, specifications):
        pass
