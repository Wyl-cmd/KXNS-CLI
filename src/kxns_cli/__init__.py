from loguru import logger

# Disable logging by default for library usage.
# Application entry points (e.g., kxns_cli.cli) should call logger.enable("kxns_cli")
# to enable logging.
logger.disable("kxns_cli")
