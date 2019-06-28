import requests

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from greenwave import __version__


def get_requests_session():
    """ Get http(s) session for request processing.  """

    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=1,
        status_forcelist=(500, 502, 503, 504),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers["User-Agent"] = f"greenwave {__version__}"
    return session
