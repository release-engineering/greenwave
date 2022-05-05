# SPDX-License-Identifier: GPL-2.0+
from greenwave.listeners.waiverdb import WaiverDBListener

listener = WaiverDBListener()
listener.listen()
app = listener.app
