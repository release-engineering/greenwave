# SPDX-License-Identifier: GPL-2.0+
from greenwave.listeners.resultsdb import ResultsDBListener

listener = ResultsDBListener()
listener.listen()
app = listener.app
