import logging
import sys

# Terminal escape sequences for colored output
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = (COLOR_SEQ % (30 + i) for i in range(8))
# Mapping of logging levels to colors
LEVEL_COLORS = {
    logging.DEBUG: BLUE,
    logging.INFO: GREEN,
    logging.WARNING: YELLOW,
    logging.ERROR: RED,
    logging.CRITICAL: MAGENTA,
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, msg, use_color=True, custom_colors=None):
        super().__init__(msg)
        self.use_color = use_color and sys.stdout.isatty()
        self.custom_colors = custom_colors or LEVEL_COLORS

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in self.custom_colors:
            levelname_color = self.custom_colors[levelname] + levelname + RESET_SEQ
            record.levelname = levelname_color
        return super().format(record)

    def formatException(self, ei):
        result = super().formatException(ei)
        if self.use_color:
            result = RED + result + RESET_SEQ
        return result

    def formatMessage(self, record):
        result = super().formatMessage(record)
        if self.use_color and record.levelname in self.custom_colors:
            result = self.custom_colors[record.levelname] + result + RESET_SEQ
        return result

    def formatStack(self, stack_info):
        result = super().formatStack(stack_info)
        if self.use_color:
            result = RED + result + RESET_SEQ
        return result

    def formatTime(self, record, datefmt=None):
        result = super().formatTime(record, datefmt)
        if self.use_color:
            result = GREEN + result + RESET_SEQ
        return result


def setup_logger(name, log_file, level=logging.DEBUG, custom_colors=None):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # File handler
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
    except Exception as e:
        print(f"Error creating file handler: {e}")
        file_handler = None

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Formatter
    formatter = ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', custom_colors=custom_colors)
    if file_handler:
        file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    if file_handler:
        logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
