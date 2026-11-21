import logging
import sys
import warnings

warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)  # silence basic-pitch backend notices

from .cli import main

sys.exit(main())
