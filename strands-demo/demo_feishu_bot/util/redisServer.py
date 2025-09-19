from typing import *

from exts import cache


# 公共REDIS_CACHE_SERVERS
# 这里套用的 flask_caching 进行处理
class redis:

    def set(*args, **kwargs) -> Optional[bool]:
        """Proxy function for internal cache object."""
        return cache.set(*args, **kwargs)

    def get(*args, **kwargs) -> Any:
        """Proxy function for internal cache object."""
        return cache.get(*args, **kwargs)

    def delete(*args, **kwargs) -> bool:
        """Proxy function for internal cache object."""
        return cache.delete(*args, **kwargs)
