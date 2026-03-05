"""mitmproxy addon loader.

This module is loaded by mitmproxy via ``--scripts /app/proxy/addons/loader.py``.
The ``addons`` list at module level is the mitmproxy convention for registering
addon instances.
"""

from proxy.addons.credential_extractor import CredentialExtractor
from proxy.addons.endpoint_logger import EndpointLogger
from proxy.addons.header_capture import HeaderCapture

addons: list = [
    CredentialExtractor(),
    HeaderCapture(),
    EndpointLogger(),
]
